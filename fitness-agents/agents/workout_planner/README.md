# Workout Planner Agent

Expert personal trainer that builds periodized training programs, tracks session-by-session progression, and adjusts training load based on recovery signals from the form coach and orchestrator.

---

## Tools

### `generate_weekly_plan`
Generates a personalized weekly training plan based on user profile, goals, injury history, and recent form analysis results.

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

| Style | Description | Best for |
|---|---|---|
| `PPL` | Push / Pull / Legs — classic 3–6 day split | Intermediate+ |
| `Upper_Lower` | Upper body / Lower body alternating | Intermediate |
| `Full_Body` | All muscle groups each session | Beginners, 3x/week |
| `Bro_Split` | One muscle group per day | Advanced, 5–6x/week |

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

**Progression logic (RPE-based):**

| RPE | Recommendation |
|---|---|
| ≤ 6 | Add 2.5–5 kg next session |
| 7–8 | Maintain load or small increment |
| ≥ 9 | Prioritize recovery — hold load next session |

### `adjust_plan_for_recovery`
Modifies the current plan based on recovery signals (low mood, poor sleep, medical flags from form coach).

```python
adjust_plan_for_recovery(adjustment_reason: str)
# Reads: mood_score, energy_level from session state
# Returns: {reduction_level, guidance, plan_modified: True}
```

**Reduction levels:**

| Condition | Volume Reduction | Guidance |
|---|---|---|
| Mood/energy ≤ 4 | 40% | Consider active recovery or rest |
| Mood/energy ≤ 6 | 20% | Moderate intensity, no PRs |
| Otherwise | 10% | De-load, maintain movement patterns |

### `get_todays_session`
Retrieves today's scheduled training session and shares it with the nutrition agent via the `workout_today` state key.

---

## Supporting Modules

### `progression.py` — Progressive overload calculations

Deterministic load progression logic:

| Function | Description |
|---|---|
| Linear progression | For beginners — add weight every session |
| Double progression | For intermediate — add reps first, then weight |
| Wave loading | For advanced — undulating periodization |
| Deload detection | Flags deload week every 4th week |

### `routines.py` — Pre-built split templates

Pre-built exercise templates for each split style and experience level. Used as scaffolding that the LLM fills in with specific weights and rep schemes. Includes:
- Beginner, intermediate, and advanced variants for each split
- Exercise substitutions for common injuries
- Warm-up and cool-down protocols

---

## Session State

| Key | Set by | Read by | Description |
|---|---|---|---|
| `current_plan_context` | workout_planner | workout_planner, orchestrator | Current plan metadata |
| `plan_week` | workout_planner | workout_planner | Week number in the program |
| `session_history` | workout_planner | workout_planner | Last 20 completed sessions |
| `plan_adjustment` | workout_planner | orchestrator, nutrition | Active plan modification |
| `plan_adjustment_active` | workout_planner | orchestrator | Whether a modification is in effect |
| `workout_today` | workout_planner | nutrition | Today's session (for fueling coordination) |

---

## Exercise Selection Rules

- Always avoid exercises contraindicated by injury history in `user_profile.injuries`
- If `recent_form_analyses` shows major issues with a movement: regress to a safer variation (e.g. goblet squat instead of barbell back squat)
- **Beginners:** compound movements 3×/week, limited isolation work
- **Intermediate+:** periodized approach with deload every 4th week
- **Advanced:** undulating periodization, higher frequency, more variation

---

## Frontend Integration

The frontend has a built-in workout planner that works independently of the backend agent:

- **Generate plan** — builds PPL/Upper-Lower/Full Body weekly schedule client-side using `SPLITS` templates
- **Log session** — increments session counter, sends RPE-based progression message to Ask Coach chat, then redirects to the chat tab
- The backend agent provides richer, personalized plans when called via `agentRun()`

---

## Model Config

- **Model:** `GEMINI_MODEL` (default: `gemini-2.0-flash-lite`)
- **Temperature:** default — allows natural language plan descriptions while keeping structure
