"""
agents/form_coach/vision.py
Handles all Gemini Vision API interactions for form analysis.
Called as a tool by the form_coach agent.
"""

import base64
import logging
from pathlib import Path
from typing import Optional

import httpx
from shared.config import GEMINI_API_KEY, GEMINI_VISION_MODEL
from shared.utils import safe_parse_json, utc_now_iso
from shared.schemas import FormAnalysisResult, FormIssue

logger = logging.getLogger(__name__)

def _vision_url() -> str:
    """Build the Gemini Vision URL dynamically so env changes are picked up."""
    return (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_VISION_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )


# ── Prompt construction ────────────────────────────────────────────────────────

def build_form_analysis_prompt(
    exercise: str,
    experience_level: str,
    focus_areas: list[str],
    injuries: Optional[list[str]] = None,
) -> str:
    """
    Build the structured prompt sent to Gemini Vision.
    Context injection is the key difference between a generic vision call
    and a medically-informed coaching analysis.
    """
    focus_str = ", ".join(focus_areas) if focus_areas else "overall form and safety"
    injury_line = (
        f"\nKnown injury history: {', '.join(injuries)}. "
        "Flag any movement patterns that could aggravate these conditions."
        if injuries else ""
    )

    return f"""You are an expert strength and conditioning coach with deep knowledge of biomechanics and injury prevention.

Analyze the athlete's form in this image for the following exercise: **{exercise}**.
Athlete experience level: {experience_level}.{injury_line}

Focus specifically on: {focus_str}.

## Scoring guidelines (be consistent and calibrated)

Use the 0-100 scale as follows:
- 90-100: Excellent — textbook form, competition-ready
- 75-89: Good — solid, safe to progress with minor tweaks
- 55-74: Needs improvement — clear correctable faults, safe to train but address issues
- 35-54: Poor — multiple significant faults, reduce load and fix form
- 0-34: Dangerous — high injury risk, stop loading this movement

**Calibration rules (apply strictly):**
- A typical gym-goer with acceptable but imperfect form scores 60-75.
- Only score above 85 if the form is genuinely excellent.
- Only score below 40 if there are multiple major faults or acute injury risk.
- If you cannot see key joints, note it in visibility_notes and score conservatively.
- Be consistent: the same form should score within ±5 points across analyses.

## Output format

Respond ONLY with a valid JSON object — no markdown, no text outside the JSON:

{{
  "score": <integer 0-100>,
  "label": <"Excellent form" | "Good form" | "Needs improvement" | "Poor form" | "Cannot assess">,
  "summary": <string, 2-3 sentence overall assessment including what is done well>,
  "safe_to_continue": <boolean — false only if score < 40 or acute injury risk visible>,
  "issues": [
    {{
      "title": <string, brief issue name>,
      "description": <string, what you observe and WHY it matters biomechanically>,
      "severity": <"minor" | "moderate" | "major">,
      "cue": <string, one specific, immediately actionable coaching cue>
    }}
  ],
  "cues": [<string, 3-5 positive coaching cues the athlete can apply right now>],
  "visibility_notes": <string or null — note any joints/angles not visible>
}}

Rules:
- Return 0-5 issues. If form is good, return fewer issues, not zero just to seem thorough.
- Return exactly 3-5 coaching cues even if form is excellent (reinforce good habits).
- safe_to_continue = false ONLY when score < 40 or there is a clearly visible acute injury risk.
- If the image is too blurry or the athlete is out of frame, set label to "Cannot assess" and explain in visibility_notes."""


# ── Image encoding ─────────────────────────────────────────────────────────────

def encode_image_to_base64(image_path: str) -> tuple[str, str]:
    """
    Read an image file and return (base64_data, mime_type).
    Supports JPEG, PNG, WEBP.
    """
    path = Path(image_path)
    suffix = path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(suffix, "image/jpeg")

    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime_type


def encode_image_bytes_to_base64(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


# ── Gemini Vision API call ─────────────────────────────────────────────────────

async def call_gemini_vision(
    image_base64: str,
    mime_type: str,
    prompt: str,
) -> dict:
    """
    POST to Gemini Vision and return the parsed JSON response dict.
    Uses responseMimeType to enforce JSON output at the API level.
    """
    payload = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,          # Very low = maximum consistency
            "topP": 0.95,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",  # Forces clean JSON, no fences
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    url = _vision_url()
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()

    # Handle blocked responses
    candidate = data.get("candidates", [{}])[0]
    finish_reason = candidate.get("finishReason", "STOP")
    if finish_reason not in ("STOP", "MAX_TOKENS"):
        block_reason = data.get("promptFeedback", {}).get("blockReason", finish_reason)
        raise ValueError(f"Gemini Vision blocked: {block_reason}")

    raw_text = candidate["content"]["parts"][0]["text"]
    logger.info(f"[vision] Gemini raw response preview: {raw_text[:200]}")

    return safe_parse_json(raw_text)


# ── Main entry point called by the ADK tool ────────────────────────────────────

async def analyze_form(
    image_path: str,
    exercise: str,
    experience_level: str,
    focus_areas: list[str],
    injuries: Optional[list[str]] = None,
) -> FormAnalysisResult:
    """
    Full pipeline: encode image → build prompt → call Gemini Vision → parse result.
    This is what the form_coach tool wraps.
    """
    image_b64, mime_type = encode_image_to_base64(image_path)
    prompt = build_form_analysis_prompt(exercise, experience_level, focus_areas, injuries)

    raw = await call_gemini_vision(image_b64, mime_type, prompt)

    # Validate and clamp score
    score = raw.get("score", 50)
    try:
        score = max(0, min(100, int(score)))
    except (TypeError, ValueError):
        score = 50

    # Derive safe_to_continue from score if not explicitly set
    safe_to_continue = raw.get("safe_to_continue", score >= 40)

    # Parse issues with graceful fallback
    raw_issues = raw.get("issues", [])
    issues = []
    for i in raw_issues:
        try:
            issues.append(FormIssue(**i))
        except Exception as e:
            logger.warning(f"[vision] Skipping malformed issue: {e}")

    # Derive label from score if not provided
    label = raw.get("label", "")
    if not label:
        if score >= 90:   label = "Excellent form"
        elif score >= 75: label = "Good form"
        elif score >= 55: label = "Needs improvement"
        elif score >= 35: label = "Poor form"
        else:             label = "Cannot assess"

    return FormAnalysisResult(
        score=score,
        label=label,
        summary=raw.get("summary", ""),
        safe_to_continue=safe_to_continue,
        issues=issues,
        cues=raw.get("cues", []),
        visibility_notes=raw.get("visibility_notes"),
        exercise=exercise,
        analyzed_at=utc_now_iso(),
    )