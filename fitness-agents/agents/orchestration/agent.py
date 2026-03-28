"""
agents/orchestrator/agent.py
Root orchestrator — the entry point for every user interaction.
Routes between specialist sub-agents, synthesizes cross-agent signals,
and autonomously triggers agent collaboration (e.g., form issue → medical flag
→ workout adjustment). This is the "workforce conductor".
"""

import os
import logging
from typing import Optional

from google.adk import Agent
from google.adk.models import Gemini
from google.adk.tools.tool_context import ToolContext
from google.adk.apps.app import App
from google.genai import types

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.config import GEMINI_MODEL, RETRY_OPTIONS
from shared.utils import log_query_to_model, log_model_response

# Import sub-agents
from agents.form_coach.agent import form_coach_agent
from agents.nutrition.agent import nutrition_agent
from agents.workout_planner.agent import workout_planner_agent

logger = logging.getLogger(__name__)


# ── Orchestrator tools (cross-cutting concerns) ────────────────────────────────

def save_user_profile(
    tool_context: ToolContext,
    user_id: str,
    name: str,
    age: int,
    weight_kg: float,
    height_cm: float,
    sex: str,
    experience_level: str,
    goals: list[str],
    injuries: Optional[list[str]] = None,
    dietary_restrictions: Optional[list[str]] = None,
) -> dict:
    """
    Save or update the user's profile to session state.
    All sub-agents read from this shared profile for personalization.

    Args:
        user_id: Unique user identifier.
        name: User's first name.
        age: Age in years.
        weight_kg: Body weight in kilograms.
        height_cm: Height in centimetres.
        sex: "male", "female", or "other".
        experience_level: "beginner", "intermediate", or "advanced".
        goals: List of goals — any of: strength, hypertrophy, fat_loss,
               endurance, general_health.
        injuries: Optional list of current or past injuries.
        dietary_restrictions: Optional dietary restrictions (e.g. "vegan", "gluten-free").

    Returns:
        dict with status and profile summary.
    """
    profile = {
        "user_id": user_id,
        "name": name,
        "age": age,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "sex": sex,
        "experience_level": experience_level,
        "goals": goals,
        "injuries": injuries or [],
        "dietary_restrictions": dietary_restrictions or [],
    }
    tool_context.state["user_profile"] = profile
    logger.info(f"[orchestrator] Profile saved for user: {name} ({user_id})")
    return {"status": "profile_saved", "name": name, "goals": goals}


def log_mood_and_energy(
    tool_context: ToolContext,
    mood_score: int,
    energy_level: int,
    notes: Optional[str] = None,
) -> dict:
    """
    Record the user's daily mood and energy check-in. These signals are read
    autonomously by the workout planner and nutrition agents to adapt their
    recommendations without the user needing to re-explain their state.

    Args:
        mood_score: 1-10 (1 = very low, 10 = excellent).
        energy_level: 1-10 (1 = exhausted, 10 = energized).
        notes: Optional free-text from the user about how they're feeling.

    Returns:
        dict with the scores saved and any automatic recommendations triggered.
    """
    tool_context.state["mood_score"] = mood_score
    tool_context.state["energy_level"] = energy_level

    if notes:
        existing = tool_context.state.get("session_notes", [])
        existing.append(f"[Mood check-in] {notes}")
        tool_context.state["session_notes"] = existing

    triggers = []
    if mood_score <= 4:
        triggers.append("low_mood_flag")
        tool_context.state["low_mood_flag"] = True
    if energy_level <= 4:
        triggers.append("low_energy_flag")
        tool_context.state["low_energy_flag"] = True

    logger.info(f"[orchestrator] Mood={mood_score}/10, Energy={energy_level}/10, triggers={triggers}")

    return {
        "mood_score": mood_score,
        "energy_level": energy_level,
        "flags_triggered": triggers,
        "message": (
            "Noted. I'm adjusting today's recommendations based on how you're feeling."
            if triggers else
            "Great — logging your check-in. Your plan for today is ready when you are."
        ),
    }


def get_system_summary(tool_context: ToolContext) -> dict:
    """
    Return a holistic snapshot of the user's current state across all agents.
    Used to generate the daily briefing or answer "how am I doing?" questions.

    Returns:
        dict containing profile summary, plan status, nutrition status,
        recent form results, and any active flags.
    """
    profile = tool_context.state.get("user_profile", {})
    macro_targets = tool_context.state.get("macro_targets", {})
    food_log = tool_context.state.get("food_log_today", [])
    form_analyses = tool_context.state.get("recent_form_analyses", [])
    session_history = tool_context.state.get("session_history", [])
    plan_adjustment = tool_context.state.get("plan_adjustment", None)
    medical_flag = tool_context.state.get("medical_review_requested", False)

    calories_logged = sum(e.get("calories", 0) for e in food_log)
    calorie_target = macro_targets.get("calories", 0)

    latest_form = form_analyses[-1] if form_analyses else None

    summary = {
        "user": profile.get("name", "User"),
        "goals": profile.get("goals", []),
        "nutrition": {
            "calories_logged_today": calories_logged,
            "calorie_target": calorie_target,
            "percent_hit": round(calories_logged / calorie_target * 100) if calorie_target else 0,
            "food_entries_today": len(food_log),
        },
        "training": {
            "sessions_completed": len(session_history),
            "plan_adjustment_active": plan_adjustment is not None,
            "adjustment_reason": plan_adjustment.get("reason") if plan_adjustment else None,
        },
        "form": {
            "latest_score": latest_form.get("score") if latest_form else None,
            "latest_exercise": latest_form.get("exercise") if latest_form else None,
            "safe_to_continue": latest_form.get("safe_to_continue") if latest_form else None,
        },
        "flags": {
            "medical_review_requested": medical_flag,
            "low_mood": tool_context.state.get("low_mood_flag", False),
            "low_energy": tool_context.state.get("low_energy_flag", False),
        },
    }
    return summary


# ── Root orchestrator agent ────────────────────────────────────────────────────

orchestrator_agent = Agent(
    name="orchestrator",
    model=Gemini(model=GEMINI_MODEL, retry_options=RETRY_OPTIONS),
    description="Master coordinator for the FormCoach AI fitness system.",
    instruction="""
You are the central coordinator of FormCoach — an AI-powered personal health
and fitness system. You are the first point of contact for every user message.

## Your four specialist agents

- **form_coach**: Analyzes exercise form from images/video using computer vision.
  Send users here when they upload a photo or ask about their technique.

- **nutrition**: Calculates macros, logs food, and builds meal plans.
  Send users here for anything diet, food, or nutrition related.

- **workout_planner**: Builds and adjusts training programs, tracks progression.
  Send users here for workout plans, session logging, or training questions.

## Routing rules

1. If the user uploads an image or mentions their form → **form_coach**
2. If the user mentions food, eating, macros, or meal planning → **nutrition**
3. If the user asks about workouts, training plans, or exercises → **workout_planner**
4. If the user mentions mood, stress, sleep, or mental state → log it with
   `log_mood_and_energy`, then route to the appropriate specialist based on
   what else they've asked.
5. If no agent is needed yet (first message, onboarding) → collect their
   profile using `save_user_profile` before routing.

## Autonomous cross-agent coordination

You must proactively connect agent signals WITHOUT the user asking:

- If `medical_review_requested` is True in state (set by form_coach when it
  detects a major form issue): tell the user clearly, recommend they rest the
  affected movement, and automatically route to workout_planner to adjust.

- If `low_mood_flag` or `low_energy_flag` is True: route to workout_planner
  to adjust the training plan before sending today's session, and suggest
  the nutrition agent adjusts to comfort foods/more carbs.

- If form_coach gives a poor score on a compound lift: proactively suggest
  to workout_planner to regress the exercise, without waiting for the user to ask.

This proactive, autonomous behavior is what makes this a workforce — not a chatbot.

## Onboarding (first interaction)

If `user_profile` is not in state, greet the user warmly and collect:
  name, age, weight, height, sex, experience level, goals, injuries,
  dietary restrictions — then call `save_user_profile`.

## Daily briefing

If the user says "good morning", "what's my plan today", or similar,
call `get_system_summary` and give them a concise daily briefing covering:
training today, nutrition targets, and any flags to address.

## Tone
Warm, motivating, and empathetic. You are their coach and health partner.
Be direct about concerns but always solution-focused.
""",
    generate_content_config=types.GenerateContentConfig(temperature=0.3),
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    tools=[save_user_profile, log_mood_and_energy, get_system_summary],
    sub_agents=[form_coach_agent, nutrition_agent, workout_planner_agent],
)


# ── ADK App (entry point) ──────────────────────────────────────────────────────

app = App(
    name="formcoach_fitness_system",
    root_agent=orchestrator_agent,
)