"""
shared/utils.py
Shared utilities: logging callbacks (matching the Google sample pattern),
retry options builder, and small helpers used across agents.
"""

import logging
import json
from datetime import datetime, timezone
from google.genai import types
from shared.config import RETRY_INITIAL_DELAY, RETRY_MAX_DELAY, RETRY_ATTEMPTS

logger = logging.getLogger(__name__)


# ── ADK callback logging (mirrors the sample's callback_logging pattern) ──────

def log_query_to_model(callback_context, llm_request):
    """Before-model callback: logs the outgoing request to the LLM."""
    agent_name = callback_context.agent_name
    try:
        content_preview = str(llm_request.contents)[:300]
    except Exception:
        content_preview = "<unreadable>"
    logger.info(f"[{agent_name}] → MODEL | {content_preview}")
    return None  # returning None lets the request proceed unmodified


def log_model_response(callback_context, llm_response):
    """After-model callback: logs the LLM response."""
    agent_name = callback_context.agent_name
    try:
        text = llm_response.candidates[0].content.parts[0].text[:300]
    except Exception:
        text = "<no text content>"
    logger.info(f"[{agent_name}] ← MODEL | {text}")
    return None  # returning None lets the response pass through unmodified


# ── Retry options ─────────────────────────────────────────────────────────────

def build_retry_options():
    """
    Build retry options compatible with the installed ADK version.
    ADK agents accept retry_options as a plain dict or HttpRetryOptions.
    We return a dict so it works regardless of ADK version.
    """
    return {
        "initial_delay": RETRY_INITIAL_DELAY,
        "max_delay": RETRY_MAX_DELAY,
        "attempts": RETRY_ATTEMPTS,
    }


RETRY_OPTIONS = build_retry_options()


# ── Misc helpers ──────────────────────────────────────────────────────────────

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON. Returns {} on failure."""
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e} | raw: {cleaned[:200]}")
        return {}