"""
shared/config.py
Central configuration loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini / ADK ──────────────────────────────────────────────────────────────
GEMINI_MODEL          = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
GEMINI_VISION_MODEL   = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY", "")

# ── ADK retry policy ──────────────────────────────────────────────────────────
# Keep retries low so the server fails fast on quota errors instead of
# hammering the API for minutes and blocking the request thread.
RETRY_INITIAL_DELAY   = float(os.getenv("RETRY_INITIAL_DELAY", "2"))
RETRY_MAX_DELAY       = float(os.getenv("RETRY_MAX_DELAY", "8"))
RETRY_ATTEMPTS        = int(os.getenv("RETRY_ATTEMPTS", "3"))

# ── API ───────────────────────────────────────────────────────────────────────
API_HOST              = os.getenv("API_HOST", "0.0.0.0")
API_PORT              = int(os.getenv("API_PORT", "8000"))

# ── Logging ───────────────────────────────────────────────────────────────────
USE_CLOUD_LOGGING     = os.getenv("USE_CLOUD_LOGGING", "false").lower() == "true"
LOG_LEVEL             = os.getenv("LOG_LEVEL", "INFO")

RETRY_OPTIONS = {
    "initial_delay": RETRY_INITIAL_DELAY,
    "max_delay": RETRY_MAX_DELAY,
    "attempts": RETRY_ATTEMPTS,
}