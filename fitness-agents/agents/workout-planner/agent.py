"""
agents/workout_planner/agent.py
Workout Planner agent — generates periodized training plans, tracks progression,
adjusts load based on form analysis results and recovery signals from the mental
health / medical agents.
"""

import os
import logging
import uuid
from typing import Optional
from datetime import date

from google.adk import Agent
from google.adk.models import Gemini
from google.adk.tools.tool_context import ToolContext

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.config import GEMINI_MODEL, RETRY_OPTIONS
from shared.utils import log_query_to_model, log_model_response

logger = logging.getLogger(__name__)


# ── Tools ──────────────────────────────────────────────────────────────────────

def generate_weekly_plan(
    tool_context: ToolContext,
    days_per_week: int = 4,
    plan_style: str = "PPL",
) -> dict:
    """
    Generate a personalized weekly training plan based on the user's profile,
    goals, injury history, and recent form analysis results.

    Args:
        days_per_week: Number of training days (2-6).
        plan_style: Training split style. One of:
                    "PPL" (Push/Pull/Legs),
                    "Upper_Lower",
                    "Full_Body",
                    "Bro_Split" (one muscle group per day).

    Returns:
        dict containing the generated plan structure saved to state.
    """
    profile = tool_context.state.get("user_profile", {})
    goals = profile.get("goals", ["general_health"])
    injuries = profile.get("injuries", [])
    experience = profile.get("experience_level", "intermediate")

    # Check for any major form issues that should constrain exercise selection
    recent_analyses = tool_context.state.get("recent_form_analyses", [])
    flagged_movements = []
    for analysis in recent_analyses[-3:]:
        for issue in analysis.get("issues", []):
            if issue.get("severity") == "major":
                flagged_movements.append(issue.get("title", ""))

    # Build a plan template — the LLM agent will fill in the actual exercises
    plan_context = {
        "plan_id": str(uuid.uuid4())[:8],
        "user_id": profile.get("user_id", "unknown"),
        "days_per_week": days_per_week,
        "plan_style": plan_style,
        "experience_level": experience,
        "primary_goal": goals[0] if goals else "general_health",
        "injuries_to_avoid": injuries,
        "flagged_movements": flagged_movements,
        "week": 1,
        "notes": (
            f"Avoid exercises that stress: {', '.join(injuries + flagged_movements)}"
            if (injuries or flagged_movements)
            else "No movement restrictions."
        ),
    }

    tool_context.state["current_plan_context"] = plan_context
    tool_context.state["plan_week"] = 1

    logger.info(f"[workout_planner] Plan context generated — {days_per_week}d {plan_style}")
    return plan_context


def log_completed_session(
    tool_context: ToolContext,
    session_name: str,
    exercises_completed: list[dict],
    rpe_overall: int,
    notes: Optional[str] = None,
) -> dict:
    """
    Log a completed training session for progression tracking.

    Args:
        session_name: Name of the session (e.g. "Push Day A").
        exercises_completed: List of dicts: [{name, sets_done, reps_done, weight_kg}].
        rpe_overall: Overall session RPE 1-10.
        notes: Optional free-text notes about the session.

    Returns:
        dict with progression recommendation for next session.
    """
    history = tool_context.state.get("session_history", [])
    session_log = {
        "date": date.today().isoformat(),
        "session_name": session_name,
        "exercises": exercises_completed,
        "rpe_overall": rpe_overall,
        "notes": notes or "",
    }
    history.append(session_log)
    tool_context.state["session_history"] = history[-20:]  # Keep last 20 sessions

    # Simple progression logic: if RPE was under 7, suggest adding load
    progression = {}
    if rpe_overall <= 6:
        progression["recommendation"] = "Session felt easy. Consider increasing load by 2.5-5kg next week."
    elif rpe_overall >= 9:
        progression["recommendation"] = "High RPE. Prioritize recovery — maintain load next session."
    else:
        progression["recommendation"] = "Good session. Maintain current load or add small increment."

    progression["sessions_logged"] = len(history)
    logger.info(f"[workout_planner] Session logged — RPE={rpe_overall}, {len(exercises_completed)} exercises")
    return progression


def adjust_plan_for_recovery(
    tool_context: ToolContext,
    adjustment_reason: str,
) -> dict:
    """
    Modify the current training plan based on recovery signals — low mood, poor
    sleep, or medical flags from other agents. Reduces volume/intensity temporarily.

    Args:
        adjustment_reason: Why the adjustment is being made
                           (e.g. "low mood score", "medical flag from form analysis").

    Returns:
        dict describing what was adjusted and for how long.
    """
    plan_context = tool_context.state.get("current_plan_context", {})
    mood = tool_context.state.get("mood_score", 7)
    energy = tool_context.state.get("energy_level", 7)

    # Determine adjustment severity
    if mood and mood <= 4 or energy and energy <= 4:
        reduction = "significant"
        note = "Reduce volume by 40%. Focus on movement quality over load. Consider active recovery day."
    elif mood and mood <= 6 or energy and energy <= 6:
        reduction = "moderate"
        note = "Reduce volume by 20%. Keep intensity moderate. Prioritize sleep tonight."
    else:
        reduction = "minor"
        note = "Slight de-load. Maintain movement patterns but reduce top-set loads by 10%."

    adjustment = {
        "reason": adjustment_reason,
        "reduction_level": reduction,
        "guidance": note,
        "mood_score": mood,
        "energy_level": energy,
        "plan_modified": True,
    }

    # Save to state so orchestrator and other agents see the modification
    tool_context.state["plan_adjustment_active"] = True
    tool_context.state["plan_adjustment"] = adjustment

    logger.info(f"[workout_planner] Plan adjusted — {reduction} reduction, reason: {adjustment_reason}")
    return adjustment


def get_todays_session(tool_context: ToolContext) -> dict:
    """
    Retrieve today's scheduled training session from the current plan.
    Also saves it to state so the nutrition agent can reference it.

    Returns:
        dict with today's session details, or a rest day message.
    """
    # In a real system this would calculate the current day's session from the plan.
    # Here we return the plan context and let the LLM agent construct the session.
    plan = tool_context.state.get("current_plan_context", {})
    adjustment = tool_context.state.get("plan_adjustment", None)

    session = {
        "plan_context": plan,
        "active_adjustment": adjustment,
        "message": "Use the plan context to determine today's session for the user.",
    }

    # Share with nutrition agent via state
    tool_context.state["workout_today"] = session
    return session


# ── Agent definition ───────────────────────────────────────────────────────────

workout_planner_agent = Agent(
    name="workout_planner",
    model=Gemini(model=GEMINI_MODEL, retry_options=RETRY_OPTIONS),
    description=(
        "Expert personal trainer that builds periodized training programs, "
        "tracks session-by-session progression, and adjusts training load "
        "based on recovery signals from the form coach and mental health agents."
    ),
    instruction="""
You are an expert personal trainer and strength coach with deep knowledge of
periodization, progressive overload, and exercise selection.

## Your responsibilities

1. **Plan generation**: When a user wants a workout plan, first confirm:
   - How many days per week they can train
   - Their preferred training style (PPL, Upper/Lower, Full Body)
   Then call `generate_weekly_plan` and use the context to generate a detailed
   week-by-week plan with specific exercises, sets, reps, and RPE targets.

2. **Session logging**: When a user completes a session, call `log_completed_session`.
   Use the progression recommendation to tell them what to do differently next time.

3. **Recovery adjustments**: If you receive signals that the user is fatigued,
   stressed, or has been flagged by the medical or mental health agent, call
   `adjust_plan_for_recovery` and explain the adjustment empathetically.

4. **Daily session**: When a user asks what they're training today, call
   `get_todays_session` and provide a clear, structured session breakdown.

## Exercise selection rules
- Always avoid exercises contraindicated by the user's injury history.
- If `recent_form_analyses` shows major issues with a movement pattern,
  regress to a safer variation until form is corrected.
- Beginners: compound movements 3x/week, limited isolation work.
- Intermediate+: periodized approach with deload every 4th week.

## State you have access to
- `user_profile`: goals, experience, injuries
- `recent_form_analyses`: form issues that may restrict exercise selection
- `session_history`: past sessions for progression tracking
- `plan_adjustment_active`: whether a recovery adjustment is in effect
- `mood_score` / `energy_level`: recovery signals from mental health agent
""",
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    tools=[
        generate_weekly_plan,
        log_completed_session,
        adjust_plan_for_recovery,
        get_todays_session,
    ],
)