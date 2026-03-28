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

GEMINI_VISION_URL = (
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

Analyze the athlete's form in this image for the following exercise: {exercise}.
Athlete experience level: {experience_level}.{injury_line}

Focus specifically on: {focus_str}.

Evaluate what you can observe. If certain angles are not visible, note that limitation honestly.

Respond ONLY with a valid JSON object — no markdown, no text outside the JSON. Use this exact schema:

{{
  "score": <integer 0-100, overall form quality>,
  "label": <one of: "Excellent form" | "Good form" | "Needs improvement" | "Poor form" | "Cannot assess">,
  "summary": <string, 1-2 sentence overall assessment>,
  "safe_to_continue": <boolean>,
  "issues": [
    {{
      "title": <string, brief issue name>,
      "description": <string, what you observe and why it matters biomechanically>,
      "severity": <"minor" | "moderate" | "major">,
      "cue": <string, one actionable coaching cue to correct this issue>
    }}
  ],
  "cues": [<string>, ...],
  "visibility_notes": <string or null, what could not be assessed from this angle>
}}

Return 3-5 coaching cues total. If no form issues found, return an empty issues array."""


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
            "temperature": 0.2,         # Low temperature = consistent structured output
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",  # Forces clean JSON, no fences
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        ],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(GEMINI_VISION_URL, json=payload)
        response.raise_for_status()

    data = response.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
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

    issues = [FormIssue(**i) for i in raw.get("issues", [])]

    return FormAnalysisResult(
        score=raw.get("score", 0),
        label=raw.get("label", "Cannot assess"),
        summary=raw.get("summary", ""),
        safe_to_continue=raw.get("safe_to_continue", True),
        issues=issues,
        cues=raw.get("cues", []),
        visibility_notes=raw.get("visibility_notes"),
        exercise=exercise,
        analyzed_at=utc_now_iso(),
    )