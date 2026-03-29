# Shared Module

Common utilities, configuration, and schemas used across all agents and the API layer.

---

## Files

### `config.py` — Environment configuration

Loads all configuration from environment variables (via `python-dotenv`). Import from here instead of calling `os.getenv()` directly in agent code.

```python
from shared.config import GEMINI_MODEL, GEMINI_API_KEY, RETRY_OPTIONS
```

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | `""` | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | Model for agent reasoning |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` | Model for form analysis vision calls |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |
| `USE_CLOUD_LOGGING` | `false` | Enable Google Cloud Logging |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `RETRY_INITIAL_DELAY` | `2` | ADK retry initial delay (seconds) |
| `RETRY_MAX_DELAY` | `8` | ADK retry max delay (seconds) |
| `RETRY_ATTEMPTS` | `3` | ADK retry attempts before failing |

`RETRY_OPTIONS` is a pre-built dict ready to pass to `Gemini(retry_options=RETRY_OPTIONS)`.

---

### `schemas.py` — Shared Pydantic models

Pydantic schemas used by multiple agents. Defining them here prevents circular imports and ensures consistent data shapes across the system.

Key models:

```python
class FormIssue(BaseModel):
    title: str
    description: str
    severity: str        # "minor" | "moderate" | "major"
    cue: str             # Actionable coaching cue

class FormAnalysisResult(BaseModel):
    score: int           # 0-100
    label: str           # Human-readable verdict label
    summary: str         # One-sentence summary
    safe_to_continue: bool
    issues: list[FormIssue]
    cues: list[str]      # Top coaching cues
    exercise: str
    form_verdict: str    # "excellent" | "good" | "decent" | "bad" | "dangerous" | "unclear"

class MacroResult(BaseModel):
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    tdee: float
    goal: str
    explanation: str

class UserProfile(BaseModel):
    user_id: str
    name: str
    age: int
    weight_kg: float
    height_cm: float
    sex: str
    experience_level: str
    goals: list[str]
    injuries: list[str]
    dietary_restrictions: list[str]
```

---

### `utils.py` — Logging callbacks and helpers

ADK model callbacks for structured logging. Pass these to every agent definition:

```python
from shared.utils import log_query_to_model, log_model_response

agent = Agent(
    ...
    before_model_callback=log_query_to_model,
    after_model_callback=log_model_response,
)
```

**`log_query_to_model`** — logs the outgoing prompt (truncated to 500 chars) at DEBUG level.

**`log_model_response`** — logs the model's response text (truncated to 500 chars) at DEBUG level.

Both callbacks are no-ops in production unless `LOG_LEVEL=DEBUG` is set.

---

## Usage Pattern

All agents follow this import pattern:

```python
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.config import GEMINI_MODEL, RETRY_OPTIONS
from shared.utils import log_query_to_model, log_model_response
from shared.schemas import FormAnalysisResult  # if needed
```

The `sys.path` manipulation is needed because agents can be run standalone (for testing) or as part of the full ADK app. `api/main.py` adds the project root to `sys.path` at startup so this is only needed for standalone runs.
