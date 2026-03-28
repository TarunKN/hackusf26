"""
agents/nutrition/macros.py

Deterministic macro and calorie calculation engine.
All formulas are evidence-based and fully unit-tested independently of the LLM.
The nutrition agent's tools call these functions rather than asking the LLM to
do arithmetic — LLMs are bad at math, these functions are not.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Literal

# ── Types ──────────────────────────────────────────────────────────────────────

Sex        = Literal["male", "female", "other"]
Goal       = Literal["fat_loss", "maintenance", "muscle_gain", "strength",
                     "hypertrophy", "endurance", "general_health"]
Activity   = Literal["sedentary", "light", "moderate", "active", "very_active"]


@dataclass
class MacroResult:
    calories:  int
    protein_g: float
    carbs_g:   float
    fat_g:     float
    tdee:      int
    bmr:       int
    goal:      str
    notes:     list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "calories":  self.calories,
            "protein_g": round(self.protein_g, 1),
            "carbs_g":   round(self.carbs_g, 1),
            "fat_g":     round(self.fat_g, 1),
            "tdee":      self.tdee,
            "bmr":       self.bmr,
            "goal":      self.goal,
            "notes":     self.notes,
        }


# ── Activity multipliers (Katch-McArdle style) ────────────────────────────────

ACTIVITY_MULTIPLIERS: dict[Activity, float] = {
    "sedentary":    1.2,    # Desk job, no exercise
    "light":        1.375,  # 1-3 days/week light exercise
    "moderate":     1.55,   # 3-5 days/week moderate exercise
    "active":       1.725,  # 6-7 days/week hard exercise
    "very_active":  1.9,    # Twice/day training or physical job
}

# ── Calorie adjustments per goal ──────────────────────────────────────────────

CALORIE_ADJUSTMENTS: dict[Goal, int] = {
    "fat_loss":       -500,
    "maintenance":       0,
    "general_health":    0,
    "endurance":       150,
    "strength":        200,
    "hypertrophy":     300,
    "muscle_gain":     300,
}

# ── Protein targets (g per kg bodyweight) ─────────────────────────────────────

PROTEIN_PER_KG: dict[Goal, float] = {
    "fat_loss":       2.4,   # Higher protein preserves muscle in deficit
    "maintenance":    1.8,
    "general_health": 1.6,
    "endurance":      1.6,
    "strength":       2.2,
    "hypertrophy":    2.2,
    "muscle_gain":    2.0,
}


# ── BMR calculators ───────────────────────────────────────────────────────────

def mifflin_st_jeor(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    """
    Mifflin-St Jeor BMR equation.
    Most accurate for the general population; preferred over Harris-Benedict.
    """
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def katch_mcardle(lean_mass_kg: float) -> float:
    """
    Katch-McArdle BMR — most accurate when lean body mass is known.
    370 + (21.6 × LBM in kg)
    """
    return 370 + 21.6 * lean_mass_kg


# ── Main calculation ───────────────────────────────────────────────────────────

def calculate_macros(
    weight_kg:     float,
    height_cm:     float,
    age:           int,
    sex:           Sex,
    goal:          Goal,
    activity:      Activity = "moderate",
    body_fat_pct:  float | None = None,
) -> MacroResult:
    """
    Calculate personalised TDEE and macro targets.

    Uses Katch-McArdle if body_fat_pct is provided (more accurate),
    otherwise falls back to Mifflin-St Jeor.

    Args:
        weight_kg:    Current body weight in kg.
        height_cm:    Height in cm.
        age:          Age in years.
        sex:          "male", "female", or "other" (uses female equation).
        goal:         Primary training goal — drives calorie and protein targets.
        activity:     Activity multiplier category.
        body_fat_pct: Optional body fat percentage (0-100). Enables Katch-McArdle.

    Returns:
        MacroResult dataclass with all targets and audit notes.
    """
    notes: list[str] = []

    # 1. BMR
    if body_fat_pct is not None and 5 <= body_fat_pct <= 60:
        lean_mass = weight_kg * (1 - body_fat_pct / 100)
        bmr = katch_mcardle(lean_mass)
        notes.append(f"BMR via Katch-McArdle (LBM={lean_mass:.1f} kg).")
    else:
        bmr = mifflin_st_jeor(weight_kg, height_cm, age, sex)
        notes.append("BMR via Mifflin-St Jeor.")

    # 2. TDEE
    multiplier = ACTIVITY_MULTIPLIERS.get(activity, 1.55)
    tdee = bmr * multiplier
    notes.append(f"Activity multiplier: {multiplier} ({activity}).")

    # 3. Calorie target
    adjustment = CALORIE_ADJUSTMENTS.get(goal, 0)
    target_calories = max(1200, round(tdee + adjustment))
    if adjustment != 0:
        notes.append(f"Calorie adjustment for {goal}: {adjustment:+d} kcal.")

    # 4. Protein
    protein_g = weight_kg * PROTEIN_PER_KG.get(goal, 1.8)
    protein_g = round(protein_g, 1)
    protein_cals = protein_g * 4

    # 5. Fat — 25-30% of target calories
    fat_pct = 0.30 if goal == "fat_loss" else 0.25
    fat_g = round((target_calories * fat_pct) / 9, 1)
    fat_cals = fat_g * 9

    # 6. Carbs — remaining calories
    carb_cals = target_calories - protein_cals - fat_cals
    carbs_g = round(max(50, carb_cals / 4), 1)   # floor at 50g for brain function

    # 7. Recalculate actual calories after rounding
    actual_cals = round(protein_g * 4 + fat_g * 9 + carbs_g * 4)

    return MacroResult(
        calories  = actual_cals,
        protein_g = protein_g,
        carbs_g   = carbs_g,
        fat_g     = fat_g,
        tdee      = round(tdee),
        bmr       = round(bmr),
        goal      = goal,
        notes     = notes,
    )


# ── Micro helpers ──────────────────────────────────────────────────────────────

def calories_from_macros(protein_g: float, carbs_g: float, fat_g: float) -> int:
    """Atwater factors: protein=4, carbs=4, fat=9 kcal/g."""
    return round(protein_g * 4 + carbs_g * 4 + fat_g * 9)


def protein_per_meal(total_protein_g: float, meals_per_day: int = 3) -> float:
    """
    Distribute protein evenly. Research shows ~0.4g/kg per meal maximises MPS.
    Returns grams of protein per meal.
    """
    return round(total_protein_g / max(1, meals_per_day), 1)


def water_intake_litres(weight_kg: float, activity: Activity = "moderate") -> float:
    """
    Baseline hydration recommendation: 35ml/kg + activity bonus.
    """
    bonus = {"sedentary": 0, "light": 0.3, "moderate": 0.5,
             "active": 0.7, "very_active": 1.0}.get(activity, 0.5)
    return round(weight_kg * 0.035 + bonus, 1)


def estimate_cutting_timeline(
    current_weight_kg: float,
    target_weight_kg:  float,
    weekly_deficit_kcal: int = 3500,   # ~0.45 kg/week
) -> dict:
    """
    Estimate weeks to reach target weight at a given weekly calorie deficit.
    1 kg fat ≈ 7700 kcal.
    """
    kg_to_lose = max(0, current_weight_kg - target_weight_kg)
    kcal_to_deficit = kg_to_lose * 7700
    weeks = math.ceil(kcal_to_deficit / weekly_deficit_kcal) if weekly_deficit_kcal > 0 else 0
    return {
        "kg_to_lose":          round(kg_to_lose, 1),
        "estimated_weeks":     weeks,
        "weekly_loss_kg":      round(weekly_deficit_kcal / 7700, 2),
        "note": "Actual results vary. Non-linear loss is normal.",
    }
