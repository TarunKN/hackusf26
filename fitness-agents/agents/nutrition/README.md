# Nutrition Agent

Registered dietitian-level nutrition agent. Calculates personalized macro targets, logs food intake, generates meal plans, and coordinates pre/post-workout nutrition with the workout planner.

## Tools

### `calculate_macro_targets`
Calculates daily calorie and macro targets using the **Mifflin-St Jeor equation** for TDEE, adjusted per goal.

```python
calculate_macro_targets(goal_override=None)
# Reads: user_profile (weight, height, age, sex, goals)
# Saves: macro_targets to session state
# Returns: {calories, protein_g, carbs_g, fat_g, tdee, goal, explanation}
```

**Calorie adjustments by goal:**
| Goal | Adjustment |
|---|---|
| fat_loss | −400 kcal |
| general_health | 0 |
| endurance | +200 kcal |
| strength | +200 kcal |
| hypertrophy / muscle_gain | +300 kcal |

**Protein targets:**
- Strength/hypertrophy: 2.2g/kg bodyweight
- All other goals: 1.8g/kg bodyweight

### `log_food_entry`
Logs a food entry and returns running daily totals vs. targets.

```python
log_food_entry(food_name, calories, protein_g, carbs_g, fat_g, meal_type)
# meal_type: "breakfast" | "lunch" | "dinner" | "snack"
# Returns: {totals_today, remaining}
```

### `get_meal_suggestions`
Returns context (calorie budget, goal, restrictions) that the LLM uses to generate 3 specific meal suggestions.

```python
get_meal_suggestions(meal_type, remaining_calories=None)
# meal_type: "breakfast" | "lunch" | "dinner" | "snack" | "pre_workout" | "post_workout"
```

### `check_nutrition_vs_training`
Cross-references today's food log against the scheduled training session. Returns pre/post-workout fueling recommendations.

## Supporting Modules

### `macros.py` — Deterministic macro engine
All arithmetic is done here, not by the LLM. Includes:
- `mifflin_st_jeor(weight_kg, height_cm, age, sex)` — BMR calculation
- `katch_mcardle(lean_mass_kg)` — more accurate when body fat % is known
- `calculate_macros(...)` — full pipeline returning `MacroResult`
- `water_intake_litres(weight_kg, activity)` — hydration recommendation
- `estimate_cutting_timeline(current, target, weekly_deficit)` — weeks to goal

### `meal-planner.py` — Template scaffolding
Builds structured meal plan templates that the LLM fills in with actual foods:
- `build_day_template(...)` — single day with training/rest day layouts
- `build_week_template(...)` — 7-day plan with training day pre/post-workout slots
- `food_reference_for_restrictions(restrictions)` — filters food lists by dietary restrictions (vegan, vegetarian, gluten-free, dairy-free)

## Session State

| Key | Description |
|---|---|
| `macro_targets` | `{calories, protein_g, carbs_g, fat_g, tdee, goal}` |
| `food_log_today` | List of food entry dicts |
| `last_meal_suggestion_context` | Context for last meal suggestion request |
| `workout_today` | Read from workout_planner for training coordination |

## Important Guidelines

- Not a medical doctor — for medical nutrition therapy, always recommend consulting a registered dietitian
- Always acknowledge dietary restrictions from user profile
- Be specific with portions: "150g cooked chicken breast" not "a chicken breast"
- If user reports low energy, note it and suggest orchestrator check in
