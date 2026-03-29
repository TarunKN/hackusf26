# Orchestrator Agent

The root agent and entry point for every user interaction. All messages go through the orchestrator first — it routes to specialist sub-agents, synthesizes cross-agent signals, and proactively triggers agent collaboration without the user asking.

## Responsibilities

| Task | How |
|---|---|
| **Onboarding** | Collects user profile (name, age, weight, height, sex, experience, goals, injuries, dietary restrictions) via `save_user_profile` |
| **Routing** | Delegates to `form_coach`, `nutrition`, or `workout_planner` based on message intent |
| **Daily briefing** | Calls `get_system_summary` when user says "good morning" or "what's my plan" |
| **Mood check-in** | Logs mood/energy via `log_mood_and_energy`, triggers plan adjustments if low |
| **Cross-agent coordination** | Proactively connects signals: bad form → adjust workout plan; low energy → reduce volume + adjust nutrition |

## Tools

### `save_user_profile`
Saves the user's profile to session state. All sub-agents read from this for personalization.

```python
save_user_profile(
    user_id, name, age, weight_kg, height_cm,
    sex, experience_level, goals, injuries, dietary_restrictions
)
```

### `log_mood_and_energy`
Records daily mood (1-10) and energy (1-10). Sets `low_mood_flag` / `low_energy_flag` in state when ≤ 4, which triggers automatic plan adjustments.

### `get_system_summary`
Returns a holistic snapshot: nutrition progress, training sessions, latest form score, active flags.

## Routing Rules

1. Image upload or form question → `form_coach`
2. Food, macros, meal planning → `nutrition`
3. Workouts, training plans → `workout_planner`
4. Mood/stress/sleep → log it, then route to appropriate specialist
5. First message (no profile) → collect profile first

## Autonomous Behaviors

- `medical_review_requested = True` (set by form_coach) → tell user, route to workout_planner to adjust
- `low_mood_flag` or `low_energy_flag` → route to workout_planner to reduce volume
- Poor form score on compound lift → suggest workout_planner regress the exercise

## Session State Keys

| Key | Set by | Read by |
|---|---|---|
| `user_profile` | orchestrator | all agents |
| `mood_score` | orchestrator | workout_planner |
| `energy_level` | orchestrator | workout_planner |
| `low_mood_flag` | orchestrator | workout_planner |
| `medical_review_requested` | form_coach | orchestrator |

## ADK Entry Point

```python
from agents.orchestration.agent import app  # App instance for ADK
```

The `app` object is what `get_fast_api_app(agents_dir=...)` discovers and mounts.
