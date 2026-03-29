"""
agents/nutrition/agent.py
Nutrition agent — calculates macro targets, builds meal plans, logs food,
and coordinates with the workout planner when training load changes.
"""

import os
import logging
from datetime import date
from typing import Optional

from google.adk import Agent
from google.adk.models import Gemini
from google.adk.tools.tool_context import ToolContext

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.config import GEMINI_MODEL, RETRY_OPTIONS
from shared.utils import log_query_to_model, log_model_response

logger = logging.getLogger(__name__)


# ── Tools ──────────────────────────────────────────────────────────────────────

def calculate_macro_targets(
    tool_context: ToolContext,
    goal_override: Optional[str] = None,
) -> dict:
    """
    Calculate personalized daily macro targets using the Mifflin-St Jeor equation
    for TDEE, then adjusts based on the user's primary goal.

    Args:
        goal_override: Optional goal to use instead of the profile's primary goal.
                       One of: "fat_loss", "maintenance", "muscle_gain".

    Returns:
        dict with keys: calories, protein_g, carbs_g, fat_g, tdee, explanation.
    """
    profile = tool_context.state.get("user_profile", {})
    weight  = profile.get("weight_kg", 75)
    height  = profile.get("height_cm", 175)
    age     = profile.get("age", 30)
    sex     = profile.get("sex", "male")
    goals   = profile.get("goals", ["general_health"])
    primary_goal = goal_override or (goals[0] if goals else "general_health")

    # Mifflin-St Jeor BMR
    if sex == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Assume moderately active (training 3-5 days/week)
    tdee = bmr * 1.55

    # Adjust calories by goal
    calorie_adjustments = {
        "fat_loss": -400,
        "general_health": 0,
        "endurance": 200,
        "hypertrophy": 300,
        "strength": 200,
        "muscle_gain": 300,
    }
    target_calories = round(tdee + calorie_adjustments.get(primary_goal, 0))

    # Macro split
    # Protein: 2.2g/kg for strength/hypertrophy, 1.8g/kg otherwise
    protein_per_kg = 2.2 if primary_goal in ("strength", "hypertrophy", "muscle_gain") else 1.8
    protein_g = round(weight * protein_per_kg)
    fat_g = round(target_calories * 0.25 / 9)       # 25% calories from fat
    carb_calories = target_calories - (protein_g * 4) - (fat_g * 9)
    carbs_g = round(max(carb_calories / 4, 50))      # Floor at 50g carbs

    macros = {
        "calories": target_calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "tdee": round(tdee),
        "goal": primary_goal,
        "explanation": (
            f"Based on TDEE of {round(tdee)} kcal. "
            f"Adjusted {calorie_adjustments.get(primary_goal, 0):+d} kcal for {primary_goal}. "
            f"Protein set at {protein_per_kg}g/kg bodyweight."
        ),
    }

    # Save to state so other agents can reference macro targets
    tool_context.state["macro_targets"] = macros
    logger.info(f"[nutrition] Macros calculated: {target_calories} kcal, {protein_g}g protein")
    return macros


def log_food_entry(
    tool_context: ToolContext,
    food_name: str,
    calories: int,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    meal_type: str = "snack",
) -> dict:
    """
    Log a food entry to the user's daily food log in session state.

    Args:
        food_name: Name of the food or meal.
        calories: Calorie count.
        protein_g: Grams of protein.
        carbs_g: Grams of carbohydrates.
        fat_g: Grams of fat.
        meal_type: One of "breakfast", "lunch", "dinner", "snack".

    Returns:
        dict with today's running totals vs. targets.
    """
    log = tool_context.state.get("food_log_today", [])
    log.append({
        "food": food_name,
        "meal_type": meal_type,
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
    })
    tool_context.state["food_log_today"] = log

    # Running totals
    totals = {
        "calories": sum(e["calories"] for e in log),
        "protein_g": round(sum(e["protein_g"] for e in log), 1),
        "carbs_g": round(sum(e["carbs_g"] for e in log), 1),
        "fat_g": round(sum(e["fat_g"] for e in log), 1),
    }

    targets = tool_context.state.get("macro_targets", {})
    remaining = {
        k: round(targets.get(k, 0) - totals.get(k, 0), 1)
        for k in ["calories", "protein_g", "carbs_g", "fat_g"]
    }

    return {
        "status": "logged",
        "entry_count_today": len(log),
        "totals_today": totals,
        "remaining": remaining,
    }


def get_meal_suggestions(
    tool_context: ToolContext,
    meal_type: str,
    remaining_calories: Optional[int] = None,
) -> dict:
    """
    Get meal suggestions tailored to the user's dietary restrictions,
    remaining macro budget, and current goal.

    Args:
        meal_type: One of "breakfast", "lunch", "dinner", "snack".
        remaining_calories: If provided, suggestions will fit within this budget.

    Returns:
        dict with key 'suggestions': list of meal ideas with approximate macros.
    """
    profile = tool_context.state.get("user_profile", {})
    restrictions = profile.get("dietary_restrictions", [])
    targets = tool_context.state.get("macro_targets", {})
    goal = targets.get("goal", "general_health")

    # Budget-based calorie target per meal
    budget_map = {"breakfast": 0.25, "lunch": 0.30, "dinner": 0.35, "snack": 0.10}
    meal_budget = remaining_calories or int(targets.get("calories", 2000) * budget_map.get(meal_type, 0.25))

    restriction_note = f" (avoiding: {', '.join(restrictions)})" if restrictions else ""

    suggestions = {
        "meal_type": meal_type,
        "calorie_budget": meal_budget,
        "goal": goal,
        "dietary_restrictions": restrictions,
    }
    tool_context.state["last_meal_suggestion_context"] = suggestions
    return suggestions


def check_nutrition_vs_training(tool_context: ToolContext) -> dict:
    """
    Cross-reference today's nutrition log against the scheduled training session.
    Returns fueling recommendations (pre/post workout nutrition).

    Returns:
        dict with pre_workout and post_workout nutrition guidance.
    """
    food_log = tool_context.state.get("food_log_today", [])
    workout_today = tool_context.state.get("workout_today", None)
    macro_targets = tool_context.state.get("macro_targets", {})

    total_calories_consumed = sum(e["calories"] for e in food_log)
    total_protein_consumed = sum(e["protein_g"] for e in food_log)

    result = {
        "calories_consumed": total_calories_consumed,
        "protein_consumed": round(total_protein_consumed, 1),
        "workout_scheduled": workout_today is not None,
        "workout_focus": workout_today.get("focus", "general") if workout_today else None,
        "recommendations": [],
    }

    if workout_today:
        result["recommendations"].append(
            "Pre-workout: aim for 30-40g carbs + 20g protein ~1hr before training."
        )
        result["recommendations"].append(
            "Post-workout: 40-50g carbs + 25-30g protein within 30 mins after training."
        )

    if total_protein_consumed < (macro_targets.get("protein_g", 150) * 0.5):
        result["recommendations"].append(
            "You're behind on protein for the day. Prioritize protein in your next meal."
        )

    return result


# ── Agent definition ───────────────────────────────────────────────────────────

nutrition_agent = Agent(
    name="nutrition",
    model=Gemini(model=GEMINI_MODEL, retry_options=RETRY_OPTIONS),
    description=(
        "Registered dietitian-level nutrition agent. Calculates personalized "
        "macro targets, logs food intake, generates meal plans, and coordinates "
        "pre/post-workout nutrition with the workout planner."
    ),
    instruction="""
You are a knowledgeable nutrition coach acting as a registered dietitian.
You help users achieve their health and fitness goals through evidence-based nutrition guidance.

## Your responsibilities

1. **Macro calculation**: When a user wants to know their calorie or macro targets,
   call `calculate_macro_targets`. Always explain the reasoning behind the numbers.

2. **Food logging**: When a user tells you what they ate, extract the food item and
   estimated macros, then call `log_food_entry`. Give them their running totals
   and remaining budget for the day after each log.

3. **Meal suggestions**: Use `get_meal_suggestions` to provide tailored meal ideas.
   The tool returns context — use that context to generate EXACTLY 3 specific meal suggestions
   with approximate macros in your response. DO NOT generate more than 3. STOP generating once you list the 3 options.

4. **Training coordination**: Call `check_nutrition_vs_training` when the user asks
   about pre/post-workout nutrition, or when their energy levels are low.

## Important guidelines

- You are NOT a medical doctor. For medical nutrition therapy (e.g., diabetes,
  eating disorders, kidney disease), always recommend consulting a registered
  dietitian or physician.
- Always acknowledge dietary restrictions from the user's profile.
- Be specific with portion sizes — "a chicken breast" is vague, "150g cooked
  chicken breast" is helpful.
- If the user reports low energy or mood issues, note this in state and suggest
  the orchestrator check in with the mental health agent.

## State you have access to
- `user_profile`: weight, height, age, sex, goals, dietary restrictions
- `macro_targets`: calculated daily targets
- `food_log_today`: all food entries logged this session
- `workout_today`: today's scheduled training session (from workout planner)
""",
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    tools=[
        calculate_macro_targets,
        log_food_entry,
        get_meal_suggestions,
        check_nutrition_vs_training,
    ],
)