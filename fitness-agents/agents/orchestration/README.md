# Orchestrator Agent

The root agent and entry point for every user interaction. All messages go through the orchestrator first — it routes to specialist sub-agents, synthesizes cross-agent signals, and proactively triggers agent collaboration without the user asking.

---

## Responsibilities

| Task | How |
|---|---|
| **Onboarding** | Collects user profile (name, age, weight, height, sex, experience, goals, injuries, dietary restrictions) via `save_user_profile` |
| **Routing** | Delegates to `form_coach`, `nutrition`, or `workout_planner` based on message intent |
| **Daily briefing** | Calls `get_system_summary` when user says "good morning" or "what's my plan" |
| **Mood check-in** | Logs mood/energy via `log_mood_and_energy`, triggers plan adjustments if low |
| **Cross-agent coordination** | Proactively connects signals: bad form → adjust workout plan; low energy → reduce volume + adjust nutrition |

---

## Tools

### `save_user_profile`
Saves the user's profile to session state. All sub-agents read from this for personalization.

```python
save_user_profile(
    user_id: str,
    name: str,
    age: int,
    weight_kg: float,
    height_cm: float,
    sex: str,                    # "male" | "female" | "other"
    experience_level: str,       # "beginner" | "intermediate" | "advanced"
    goals: list[str],            # ["strength", "hypertrophy", "fat_loss", "endurance", "general_health"]
    injuries: list[str] = None,
    dietary_restrictions: list[str] = None,
)
# Returns: {status, name, goals}
```

### `log_mood_and_energy`
Records daily mood (1–10) and energy (1–10). Sets `low_mood_flag` / `low_energy_flag` in state when ≤ 4, which triggers automatic plan adjustments downstream.

```python
log_mood_and_energy(
    mood_score: int,     # 1-10
    energy_level: int,   # 1-10
    notes: str = None,
)
# Returns: {mood_score, energy_level, flags_triggered, message}
```

**Automatic flags:**
- `mood_score ≤ 4` → sets `low_mood_flag = True`
- `energy_level ≤ 4` → sets `low_energy_flag = True`

Both flags are read by the Workout Planner to reduce training volume.

### `get_system_summary`
Returns a holistic snapshot of the user's current state across all agents. Used to generate the daily briefing or answer "how am I doing?" questions.

```python
get_system_summary()
# Returns: {user, goals, nutrition, training, form, flags}
```

---

## Routing Rules

1. Image upload or form question → `form_coach`
2. Food, macros, meal planning → `nutrition`
3. Workouts, training plans, session logging → `workout_planner`
4. Mood/stress/sleep → log it with `log_mood_and_energy`, then route to appropriate specialist
5. First message (no profile in state) → collect profile first via `save_user_profile`

---

## Autonomous Behaviors

These happen automatically without the user asking:

| Condition | Action |
|---|---|
| `medical_review_requested = True` (set by form_coach) | Tell user clearly, recommend resting the movement, route to workout_planner to adjust plan |
| `low_mood_flag` or `low_energy_flag` | Route to workout_planner to reduce volume, suggest nutrition adjusts to comfort foods/more carbs |
| Poor form score on compound lift | Proactively suggest workout_planner regress the exercise to a safer variation |

---

## Session State Keys

| Key | Set by | Read by | Description |
|---|---|---|---|
| `user_profile` | orchestrator | all agents | Full user profile dict |
| `mood_score` | orchestrator | workout_planner | Today's mood (1–10) |
| `energy_level` | orchestrator | workout_planner | Today's energy (1–10) |
| `low_mood_flag` | orchestrator | workout_planner | True when mood ≤ 4 |
| `low_energy_flag` | orchestrator | workout_planner | True when energy ≤ 4 |
| `session_notes` | orchestrator, form_coach | orchestrator | Running notes from this session |
| `medical_review_requested` | form_coach | orchestrator | True when major form issue detected |
| `medical_review_reason` | form_coach | orchestrator | Description of the flagged issue |

---

## ADK Entry Point

```python
from agents.orchestration.agent import app  # App instance for ADK
```

The `app` object is what `get_fast_api_app(agents_dir=...)` discovers and mounts. It exposes `/run`, `/stream`, and `/sessions` endpoints automatically.

```python
# agent.py
app = App(
    name="orchestration",
    root_agent=orchestrator_agent,
)
```

---

## Model Config

- **Model:** `GEMINI_MODEL` (default: `gemini-2.0-flash-lite`)
- **Temperature:** `0.3` — low enough for consistent routing, high enough for natural conversation
- **Retry:** 3 attempts, 2–8s backoff (configured in `shared/config.py`)
