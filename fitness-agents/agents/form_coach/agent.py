"""
agents/form_coach/agent.py
Form Coach agent — analyzes exercise form via Gemini Vision,
saves results to session state, and flags injury risks to the orchestrator.
"""

import os
import asyncio
import logging
import threading
from typing import Optional

from google.adk import Agent
from google.adk.models import Gemini
from google.adk.tools.tool_context import ToolContext
from google.genai import types

# Add project root to path when running standalone
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.config import GEMINI_MODEL, RETRY_OPTIONS
from shared.utils import log_query_to_model, log_model_response
from agents.form_coach.vision import analyze_form

logger = logging.getLogger(__name__)


# ── Tools ──────────────────────────────────────────────────────────────────────

def analyze_exercise_form(
    tool_context: ToolContext,
    image_path: str,
    exercise: str,
    focus_areas: Optional[list[str]] = None,
) -> dict:
    """
    Analyze the user's exercise form from an image file using Gemini Vision.

    This tool:
      1. Reads the user's profile from session state to inject context
         (experience level, injury history) into the vision prompt.
      2. Calls Gemini Vision with a structured, context-aware prompt.
      3. Saves the analysis result to session state.
      4. Sets a flag if the medical agent needs to be notified.

    Args:
        image_path: Absolute or relative path to the uploaded image/frame.
        exercise: Name of the exercise being performed (e.g. "barbell back squat").
        focus_areas: Optional list of specific areas to focus on
                     (e.g. ["spine neutrality", "knee tracking"]).

    Returns:
        dict with keys: score, label, summary, safe_to_continue, issues, cues.
    """
    # Pull user context from session state
    profile = tool_context.state.get("user_profile", {})
    experience = profile.get("experience_level", "intermediate")
    injuries = profile.get("injuries", [])

    default_focus = ["spine neutrality", "knee tracking", "hip hinge",
                     "depth and range of motion", "shoulder position"]
    areas = focus_areas or default_focus

    # Run async vision call in sync context (ADK tools are sync by default).
    # Use a dedicated thread with its own event loop to avoid "loop already running"
    # errors when ADK itself runs an async event loop.
    def _run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                analyze_form(image_path, exercise, experience, areas, injuries)
            )
        finally:
            loop.close()

    container = {}
    exc_container = {}

    def _thread_target():
        try:
            container["result"] = _run_in_thread()
        except Exception as e:
            exc_container["error"] = e

    t = threading.Thread(target=_thread_target)
    t.start()
    t.join(timeout=60)

    if "error" in exc_container:
        raise exc_container["error"]
    if "result" not in container:
        raise TimeoutError("Form analysis timed out after 60 seconds.")

    result = container["result"]

    # Persist result to session state
    existing = tool_context.state.get("recent_form_analyses", [])
    existing.append(result.model_dump())
    tool_context.state["recent_form_analyses"] = existing[-5:]  # Keep last 5 only

    # Signal orchestrator if action required from medical agent
    if not result.safe_to_continue or any(i.severity == "major" for i in result.issues):
        tool_context.state["medical_review_requested"] = True
        tool_context.state["medical_review_reason"] = (
            f"Form analysis flagged major issue(s) during {exercise}. "
            f"Issues: {[i.title for i in result.issues if i.severity == 'major']}"
        )

    logger.info(f"[form_coach] Analysis complete — score={result.score}, safe={result.safe_to_continue}")
    return result.model_dump()


def get_form_history(tool_context: ToolContext) -> dict:
    """
    Retrieve the user's recent form analysis history from session state.

    Returns:
        dict with key 'analyses' containing a list of past form analysis results.
    """
    analyses = tool_context.state.get("recent_form_analyses", [])
    return {"analyses": analyses, "count": len(analyses)}


def save_coaching_note(
    tool_context: ToolContext,
    note: str,
) -> dict:
    """
    Save a coaching note or observation to session state for continuity.

    Args:
        note: A string note from the coach to be persisted across turns.

    Returns:
        dict with status.
    """
    notes = tool_context.state.get("session_notes", [])
    notes.append(note)
    tool_context.state["session_notes"] = notes
    return {"status": "success", "total_notes": len(notes)}


# ── Agent definition ───────────────────────────────────────────────────────────

form_coach_agent = Agent(
    name="form_coach",
    model=Gemini(model=GEMINI_MODEL, retry_options=RETRY_OPTIONS),
    description=(
        "Expert strength and conditioning coach that analyzes exercise form "
        "from images or video frames using computer vision. Detects form "
        "issues, provides biomechanical coaching cues, and flags injury risks."
    ),
    instruction="""
You are an expert strength and conditioning coach with deep knowledge of
biomechanics, injury prevention, and exercise technique.

## Your responsibilities

1. **Form analysis**: When the user shares an image or asks about their form,
   call `analyze_exercise_form` with the image path and exercise name.
   Always confirm the exercise type with the user before analyzing if unclear.

2. **Presenting results**: After analysis, structure your response as:
   - Overall form score and verdict
   - Each issue found, explaining WHY it matters (biomechanically)
   - Actionable cues they can apply immediately
   - Whether it is safe to continue training

3. **Tracking progress**: Use `get_form_history` to compare current form
   against past analyses. Celebrate improvements. Note regressions.

4. **Coaching notes**: Use `save_coaching_note` to record key observations
   about this user's patterns for future sessions.

5. **Medical escalation**: If `safe_to_continue` is false or there are major
   issues, tell the user clearly and explain that you are flagging this for
   medical review. Do NOT attempt to give medical advice yourself.

## Tone
- Encouraging but honest. Never sugarcoat a major issue.
- Use plain language — no excessive jargon.
- Be specific. "Keep your chest up" is better than "improve your posture".

## State you have access to
- `user_profile`: experience level, injuries, goals
- `recent_form_analyses`: last 5 form analysis results
- `session_notes`: running coaching notes from this session
""",
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
    tools=[analyze_exercise_form, get_form_history, save_coaching_note],
)