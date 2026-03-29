# Form Coach Agent

Expert strength and conditioning coach that analyzes exercise form from images or video frames using **Gemini 2.5 Flash Vision**. Detects biomechanical issues, provides actionable coaching cues, and flags injury risks to the orchestrator.

## How It Works

```
User uploads image/video
        │
        ▼
analyze_exercise_form (tool)
        │
        ├── Reads user profile from session state (experience, injuries)
        ├── Calls vision.py → Gemini Vision API
        │       ├── Builds context-aware prompt (exercise, level, focus areas, injuries)
        │       └── Returns structured JSON (score, label, issues, cues)
        ├── Saves result to session state (recent_form_analyses)
        └── Sets medical_review_requested = True if major issues found
```

## Tools

### `analyze_exercise_form`
Main tool. Reads user profile, calls Gemini Vision, saves result.

```python
analyze_exercise_form(
    image_path: str,          # Path to uploaded image/video frame
    exercise: str,            # e.g. "barbell back squat"
    focus_areas: list[str],   # e.g. ["spine neutrality", "knee tracking"]
)
# Returns: FormAnalysisResult dict
```

### `get_form_history`
Returns the last 5 form analyses from session state for progress tracking.

### `save_coaching_note`
Persists a coaching observation to session state for continuity across turns.

## Vision Pipeline (`vision.py`)

1. **`encode_image_to_base64`** — reads image file, returns (base64, mime_type)
2. **`build_form_analysis_prompt`** — constructs a biomechanically-informed prompt with:
   - Exercise name and athlete experience level
   - Known injury history (flags movements that could aggravate)
   - Focus areas (spine, knees, hips, shoulders, etc.)
   - Calibrated scoring rubric (0-100 scale with explicit band definitions)
3. **`call_gemini_vision`** — POSTs to Gemini Vision API with `temperature=0.1` for consistency
4. **`analyze_form`** — full pipeline, returns `FormAnalysisResult` Pydantic model

## Form Score Bands

| Score | Label | Meaning |
|---|---|---|
| 90-100 | Excellent form | Competition-ready technique |
| 75-89 | Good form | Safe to progress, minor tweaks |
| 55-74 | Needs improvement | Correctable faults, safe to train |
| 35-54 | Poor form | Multiple faults, reduce load |
| 0-34 | Cannot assess | High injury risk or unassessable |

## Pose Utils (`utils/pose-utils.py`)

Deterministic biomechanical calculations that operate on the structured JSON from Gemini Vision:

- **`JointAngles`** — knee, hip, elbow angles in degrees
- **`PostureFlags`** — knee valgus, butt wink, forward lean, elbow flare, hyperextension, asymmetry
- **`derive_posture_flags`** — applies exercise-specific threshold rules
- **`flags_to_severity_score`** — converts flags to 0-100 score with cumulative deductions

## Session State

| Key | Description |
|---|---|
| `recent_form_analyses` | Last 5 `FormAnalysisResult` dicts |
| `medical_review_requested` | `True` if major issue detected |
| `medical_review_reason` | Description of the flagged issue |
| `session_notes` | Running coaching notes |

## Frontend Integration

After analysis, the frontend automatically:
1. Renders the result card (verdict badge, issues list, coaching cues)
2. Injects a summary into the **Ask Coach** chat via `injectFormCoachToChat()`
3. Sends the summary to the orchestrator for proactive plan adjustment
