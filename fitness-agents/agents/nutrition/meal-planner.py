"""
agents/nutrition/meal_planner.py

Template-based meal plan scaffolding.
The nutrition agent calls these helpers to build structured meal plan contexts
that it then hands to the LLM to fill in with specific foods, portions, and
recipes — keeping deterministic structure separate from creative generation.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Literal

MealType = Literal["breakfast", "lunch", "dinner", "snack", "pre_workout", "post_workout"]

# Fraction of daily calories assigned to each meal slot
MEAL_CALORIE_SPLITS: dict[MealType, float] = {
    "breakfast":    0.25,
    "lunch":        0.30,
    "dinner":       0.30,
    "snack":        0.10,
    "pre_workout":  0.08,   # usually part of another meal slot; listed separately for clarity
    "post_workout": 0.12,
}


@dataclass
class MealSlot:
    meal_type:    MealType
    target_cals:  int
    protein_g:    float
    carbs_g:      float
    fat_g:        float
    timing_note:  str = ""


@dataclass
class DayTemplate:
    total_calories:  int
    protein_g:       float
    carbs_g:         float
    fat_g:           float
    slots:           list[MealSlot] = field(default_factory=list)
    dietary_flags:   list[str]      = field(default_factory=list)
    goal:            str            = "general_health"

    def to_prompt_context(self) -> dict:
        """Return a dict the LLM agent uses to generate actual meal suggestions."""
        return {
            "daily_totals": {
                "calories":  self.total_calories,
                "protein_g": self.protein_g,
                "carbs_g":   self.carbs_g,
                "fat_g":     self.fat_g,
            },
            "goal":           self.goal,
            "dietary_flags":  self.dietary_flags,
            "meal_slots": [
                {
                    "meal_type":   s.meal_type,
                    "target_cals": s.target_cals,
                    "protein_g":   s.protein_g,
                    "carbs_g":     s.carbs_g,
                    "fat_g":       s.fat_g,
                    "timing_note": s.timing_note,
                }
                for s in self.slots
            ],
        }


# ── Builders ───────────────────────────────────────────────────────────────────

def build_day_template(
    total_calories: int,
    protein_g:      float,
    carbs_g:        float,
    fat_g:          float,
    goal:           str = "general_health",
    training_today: bool = False,
    dietary_restrictions: list[str] | None = None,
    meals_per_day:  int = 4,
) -> DayTemplate:
    """
    Scaffold a single day's meal plan template with calorie/macro targets per slot.

    Training days get an explicit pre/post-workout slot; rest days do not.
    The agent uses the returned DayTemplate.to_prompt_context() to ask the LLM
    to fill in actual foods and recipes.
    """
    restrictions = dietary_restrictions or []
    slots: list[MealSlot] = []

    if training_today and meals_per_day >= 3:
        # Training day layout: B / pre-workout / post-workout / D
        schedule: list[tuple[MealType, float, str]] = [
            ("breakfast",    0.25, "High protein, moderate carbs to start the day."),
            ("pre_workout",  0.20, "1-2 hours before training. Carb-forward, easy to digest."),
            ("post_workout", 0.25, "Within 30 min after training. Fast protein + carbs for recovery."),
            ("dinner",       0.30, "Balanced meal to close the day. Include vegetables."),
        ]
    else:
        # Rest day — distribute across meals_per_day
        base_splits = [0.25, 0.30, 0.35, 0.10][:meals_per_day]
        # normalise so they sum to 1
        total = sum(base_splits)
        base_splits = [s / total for s in base_splits]
        meal_names: list[MealType] = ["breakfast", "lunch", "dinner", "snack"]
        timings = ["Start the day with protein.", "Balanced lunch.", "Largest meal of the day.", "Light snack if needed."]
        schedule = list(zip(meal_names[:meals_per_day], base_splits, timings))

    for meal_type, cal_frac, timing in schedule:
        slot_cals  = round(total_calories * cal_frac)
        # Pro-rata macros by calorie fraction
        slot_p = round(protein_g * cal_frac, 1)
        slot_c = round(carbs_g   * cal_frac, 1)
        slot_f = round(fat_g     * cal_frac, 1)
        slots.append(MealSlot(
            meal_type   = meal_type,
            target_cals = slot_cals,
            protein_g   = slot_p,
            carbs_g     = slot_c,
            fat_g       = slot_f,
            timing_note = timing,
        ))

    return DayTemplate(
        total_calories  = total_calories,
        protein_g       = round(protein_g, 1),
        carbs_g         = round(carbs_g, 1),
        fat_g           = round(fat_g, 1),
        slots           = slots,
        dietary_flags   = restrictions,
        goal            = goal,
    )


def build_week_template(
    total_calories: int,
    protein_g:      float,
    carbs_g:        float,
    fat_g:          float,
    goal:           str = "general_health",
    training_days:  list[str] | None = None,   # ["Monday", "Wednesday", "Friday"]
    dietary_restrictions: list[str] | None = None,
) -> dict[str, dict]:
    """
    Build a 7-day template dict keyed by weekday name.
    Training days get pre/post-workout slots; rest days get standard meals.
    """
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    training = set(training_days or ["Monday", "Wednesday", "Friday", "Saturday"])

    week: dict[str, dict] = {}
    for day in weekdays:
        is_training = day in training
        template = build_day_template(
            total_calories        = total_calories,
            protein_g             = protein_g,
            carbs_g               = carbs_g,
            fat_g                 = fat_g,
            goal                  = goal,
            training_today        = is_training,
            dietary_restrictions  = dietary_restrictions,
        )
        week[day] = template.to_prompt_context()
        week[day]["is_training_day"] = is_training

    return week


# ── Common food reference (used by the LLM prompt context) ────────────────────

HIGH_PROTEIN_FOODS = [
    "chicken breast", "turkey mince", "Greek yogurt (0% fat)", "cottage cheese",
    "eggs", "egg whites", "tinned tuna", "salmon", "cod", "shrimp",
    "tofu", "tempeh", "edamame", "lentils", "black beans",
    "whey protein", "casein protein", "skyr",
]

COMPLEX_CARB_SOURCES = [
    "oats", "brown rice", "quinoa", "sweet potato", "white potato",
    "whole-grain bread", "whole-wheat pasta", "barley", "buckwheat",
    "fruit (banana, berries, apple)", "legumes",
]

HEALTHY_FAT_SOURCES = [
    "avocado", "olive oil", "almonds", "walnuts", "cashews",
    "nut butter (almond/peanut)", "chia seeds", "flaxseed",
    "fatty fish (salmon, mackerel)", "dark chocolate (85%+)",
]

def food_reference_for_restrictions(restrictions: list[str]) -> dict:
    """Filter food lists by dietary restrictions for inclusion in the LLM prompt."""
    proteins = HIGH_PROTEIN_FOODS.copy()
    carbs    = COMPLEX_CARB_SOURCES.copy()
    fats     = HEALTHY_FAT_SOURCES.copy()

    if "vegan" in restrictions or "plant-based" in restrictions:
        animal_proteins = {"chicken breast", "turkey mince", "eggs", "egg whites",
                           "tinned tuna", "salmon", "cod", "shrimp",
                           "whey protein", "casein protein", "skyr",
                           "Greek yogurt (0% fat)", "cottage cheese"}
        proteins = [p for p in proteins if p not in animal_proteins]
        fats = [f for f in fats if "fish" not in f]

    if "vegetarian" in restrictions:
        meat_proteins = {"chicken breast", "turkey mince", "tinned tuna", "salmon",
                         "cod", "shrimp"}
        proteins = [p for p in proteins if p not in meat_proteins]

    if "gluten-free" in restrictions:
        gluten_carbs = {"whole-grain bread", "whole-wheat pasta", "barley"}
        carbs = [c for c in carbs if c not in gluten_carbs]

    if "dairy-free" in restrictions:
        dairy = {"Greek yogurt (0% fat)", "cottage cheese", "whey protein",
                 "casein protein", "skyr"}
        proteins = [p for p in proteins if p not in dairy]

    return {
        "protein_sources": proteins[:10],
        "carb_sources":    carbs[:8],
        "fat_sources":     fats[:6],
    }
