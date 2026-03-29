# Form Coach Agent

Expert strength and conditioning coach that analyzes exercise form from photos or videos using **Gemini 2.5 Flash Vision**. Detects biomechanical issues, provides actionable coaching cues, and flags injury risks to the orchestrator.

---

## How It Works

```
User uploads photo or video
        │
        ▼
Frontend (index.html)
        │
        ├── Image → base64 inline_data → Gemini Vision API (direct, client-side)
        │
        └── Video → Gemini File API upload → poll until ACTIVE → file_data URI → Gemini Vision API
                │
                ▼
        Structured JSON response
        (verdict, issues, cues, safety flag)
                │
                ▼
        renderFormResults() — displays result card
                │
                ▼
        injectFormCoachToChat() — injects summary into Ask Coach chat
                │
                ▼
        agentRun() — sends summary to orchestrator for plan adjustment
                │
                ▼
        showView("chat") — redirects to Ask Coach tab
```

For server-side agent calls (via ADK `/run`):

```
analyze_exercise_form (tool)
        │
        ├── Reads user profile from session state (experience, injuries)
        ├── Calls vision.py → Gemini Vision API
        │       ├── Builds context-aware prompt (exercise, level, focus areas, injuries)
        │       └── Returns structured JSON (verdict, label, issues, cues)
        ├── Saves result to session state (recent_form_analyses)
        └── Sets medical_review_requested = True if major issues found
```

---

## Video Analysis — Gemini File API

Videos are processed using the **Gemini File API** for true multi-frame analysis:

1. **Upload** — `POST https://generativelanguage.googleapis.com/upload/v1beta/files` (resumable upload)
2. **Poll** — `GET /v1beta/{file.name}` every 2 seconds until `state === "ACTIVE"`
3. **Analyze** — `generateContent` with `file_data: { file_uri }` instead of `inline_data`

This enables Gemini to analyze motion, timing, and form across the entire video clip — not just the first frame. Supports MP4 and MOV up to the Gemini File API limit (~2GB).

Images continue to use base64 `inline_data` (faster, no upload step needed).

---

## Tools

### `analyze_exercise_form`
Main tool. Reads user profile, calls Gemini Vision, saves result to session state.

```python
analyze_exercise_form(
    image_path: str,          # Absolute path to uploaded image/video frame
    exercise: str,            # e.g. "barbell back squat"
    focus_areas: list[str],   # e.g. ["spine neutrality", "knee tracking"]
)
# Returns: FormAnalysisResult dict
```

**Default focus areas** (when none specified):
- Spine neutrality
- Knee tracking
- Hip hinge
- Depth and range of motion
- Shoulder position

### `get_form_history`
Returns the last 5 form analyses from session state for progress tracking.

```python
get_form_history()
# Returns: {analyses: [...], count: int}
```

### `save_coaching_note`
Persists a coaching observation to session state for continuity across turns.

```python
save_coaching_note(note: str)
# Returns: {status, total_notes}
```

---

## Form Verdicts

| Verdict | Meaning | Safety |
|---|---|---|
| **excellent** | Competition-ready technique — only tiny refinements | ✓ Safe |
| **good** | Solid form — safe to progress with minor tweaks | ✓ Safe |
| **decent** | Acceptable — fine to keep training, polish over time | ✓ Safe |
| **bad** | Multiple visible faults or one major fault — fix before adding load | ⚠ Caution |
| **dangerous** | Unambiguous high-risk pattern — stop heavy loading immediately | ✗ Stop |
| **unclear** | Cannot judge (body out of frame, unusable blur, etc.) | — |

**Tie-breaker rule:** When unsure between `decent` and `bad`, always choose `decent`. Only use `bad` when you would honestly tell the athlete "that rep is not acceptable to repeat."

---

## Vision Pipeline (`vision.py`)

1. **`encode_image_to_base64`** — reads image file, returns `(base64, mime_type)`
2. **`build_form_analysis_prompt`** — constructs a biomechanically-informed prompt with:
   - Exercise name and athlete experience level
   - Known injury history (flags movements that could aggravate)
   - Focus areas (spine, knees, hips, shoulders, etc.)
   - Calibrated verdict rubric with explicit tie-breaker rules
3. **`call_gemini_vision`** — POSTs to Gemini Vision API with `temperature=0` for consistency
4. **`analyze_form`** — full pipeline, returns `FormAnalysisResult` Pydantic model

---

## Pose Utils (`utils/pose-utils.py`)

Deterministic biomechanical calculations that operate on the structured JSON from Gemini Vision:

- **`JointAngles`** — knee, hip, elbow angles in degrees
- **`PostureFlags`** — knee valgus, butt wink, forward lean, elbow flare, hyperextension, asymmetry
- **`derive_posture_flags`** — applies exercise-specific threshold rules
- **`flags_to_severity_score`** — converts flags to 0–100 score with cumulative deductions

---

## Session State

| Key | Description |
|---|---|
| `recent_form_analyses` | Last 5 `FormAnalysisResult` dicts |
| `medical_review_requested` | `True` if major issue detected |
| `medical_review_reason` | Description of the flagged issue |
| `session_notes` | Running coaching notes |

---

## Frontend Integration

After analysis completes, the frontend automatically:

1. Renders the result card (verdict badge, issues list, coaching cues) in the Form Coach view
2. Injects a rich summary card into the **Ask Coach** chat via `injectFormCoachToChat()`
3. Sends the summary to the orchestrator via `agentRun()` for proactive plan adjustment
4. Redirects to the **Ask Coach** tab via `showView("chat")`

---

## Supported Exercises

Any exercise can be analyzed. The UI provides quick-select options for common lifts:

- Barbell back squat / front squat
- Conventional deadlift / sumo deadlift / Romanian deadlift
- Barbell bench press / overhead press / row
- Pull-up / chin-up
- Dumbbell lunge
- Push-up
- Kettlebell swing
- Custom (free text)

---

## Model Config

- **Model:** `GEMINI_VISION_MODEL` (default: `gemini-2.5-flash`)
- **Temperature:** `0` — deterministic for consistent verdicts
- **Response format:** `application/json` with enforced schema
- **Max output tokens:** `8192`
