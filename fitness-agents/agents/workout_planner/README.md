# Workout Planner Agent

Expert personal trainer that builds periodized training programs, tracks session-by-session progression, and adjusts training load based on recovery signals from the form coach and orchestrator.

## Tools

### `generate_weekly_plan`
Generates a personalized weekly training plan context based on user profile, goals, injury history, and recent form analysis results.

```python
generate_weekly_plan(
    days_per_week: int = 4,   # 2-6
    plan_style: str = "PPL",  # "PPL" | "Upper_Lower" | "Full_Body" | "Bro_Split"
)
# Reads: user_profile, recent_form_analyses (flags major issues)
# Saves: current_plan_context, plan_week to session state
# Returns: plan context dict the LLM uses to generate actual exercises
```

**Plan styles:**
| Style | Description |
|---|---|
| `PPL` | Push / Pull / Legs — classic 3-6 day split |
| `Upper_Lower` | Upper body / Lower body alternating |
| `Full_Body` | All muscle groups each session |
| `Bro_Split` | One muscle group per day |

### `log_completed_session`
Logs a completed training session and returns a progression recommendation.

```python
log_completed_session(
    session_name: str,
    exercises_completed: list[dict],  # [{name, sets_done, reps_done, weight_kg}]
    rpe_overall: int,                 # 1-10
    notes: str = None,
)
# Keeps last 20 sessions in session_history
# Returns: progression recommendation based on RPE
```

**Progression logic:**
- RPE ≤ 6: "Add 2.5-5kg next week"
- RPE 7-8: "Maintain or small increment"
- RPE ≥ 9: "Prioritize recovery — hold load"

### `adjust_plan_for_recovery`
Modifies the current plan based on recovery signals (low mood, poor sleep, medical flags).

```python
adjust_plan_for_recovery(adjustment_reason: str)
# Reads: mood_score, energy_level from session state
# Returns: {reduction_level, guidance, plan_modified: True}
```

**Reduction levels:**
- Mood/energy ≤ 4: 40% volume reduction, consider active recovery
- Mood/energy ≤ 6: 20% volume reduction, moderate intensity
- Otherwise: 10% de-load, maintain movement patterns

### `get_todays_session`
Retrieves today's scheduled training session and shares it with the nutrition agent via `workout_today` state key.

## Supporting Modules

### `progression.py`
Deterministic progressive overload calculations:
- Linear progression for beginners
- Double progression (reps then weight) for intermediate
- Periodization schemes (wave loading, deload weeks)

### `routines.py`
Pre-built exercise templates for each split style and experience level. Used as scaffolding that the LLM fills in with specific weights and rep schemes.

## Session State

| Key | Set by | Read by |
|---|---|---|
| `current_plan_context` | workout_planner | workout_planner, orchestrator |
| `plan_week` | workout_planner | workout_planner |
| `session_history` | workout_planner | workout_planner |
| `plan_adjustment` | workout_planner | orchestrator, nutrition |
| `plan_adjustment_active` | workout_planner | orchestrator |
| `workout_today` | workout_planner | nutrition |

## Exercise Selection Rules

- Always avoid exercises contraindicated by injury history
- If `recent_form_analyses` shows major issues with a movement: regress to safer variation
- Beginners: compound movements 3×/week, limited isolation
- Intermediate+: periodized approach with deload every 4th week
