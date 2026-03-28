"""
agents/workout_planner/progression.py

Progressive overload and periodisation engine.
Deterministic rules for when and how to add load, volume, or intensity —
kept out of the LLM to avoid hallucinated progressions.
"""

from __future__ import annotations
import math
import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

Level = Literal["beginner", "intermediate", "advanced"]


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class SessionLog:
    """One completed training session entry."""
    week:          int
    session_name:  str
    exercise_name: str
    sets_done:     int
    reps_done:     int       # average reps across sets
    weight_kg:     float
    rpe:           float     # 1-10


@dataclass
class ProgressionRecommendation:
    exercise:    str
    action:      Literal["increase_load", "increase_volume", "maintain", "deload", "regress"]
    delta_kg:    float = 0.0         # load change (positive = add, negative = remove)
    delta_sets:  int   = 0           # set change
    delta_reps:  int   = 0           # rep change
    rationale:   str   = ""
    new_rpe_target: float = 0.0

    def to_dict(self) -> dict:
        return {
            "exercise":       self.exercise,
            "action":         self.action,
            "delta_kg":       self.delta_kg,
            "delta_sets":     self.delta_sets,
            "delta_reps":     self.delta_reps,
            "rationale":      self.rationale,
            "new_rpe_target": self.new_rpe_target,
        }


# ── Progression increments ─────────────────────────────────────────────────────
# How much load to add per successful session, by level and movement category.

LOAD_INCREMENTS: dict[Level, dict[str, float]] = {
    "beginner": {
        "squat":            5.0,
        "hinge":            5.0,
        "push_horizontal":  2.5,
        "push_vertical":    2.5,
        "pull_horizontal":  2.5,
        "pull_vertical":    2.5,
        "accessory":        1.25,
        "default":          2.5,
    },
    "intermediate": {
        "squat":            2.5,
        "hinge":            2.5,
        "push_horizontal":  1.25,
        "push_vertical":    1.25,
        "pull_horizontal":  1.25,
        "pull_vertical":    1.25,
        "accessory":        1.0,
        "default":          1.25,
    },
    "advanced": {
        "squat":            1.25,
        "hinge":            1.25,
        "push_horizontal":  0.5,
        "push_vertical":    0.5,
        "pull_horizontal":  0.5,
        "pull_vertical":    0.5,
        "accessory":        0.5,
        "default":          0.5,
    },
}

# RPE thresholds for progression decisions
RPE_TOO_EASY    = 6.5   # below this → ready to add load
RPE_IDEAL_LOW   = 7.0
RPE_IDEAL_HIGH  = 8.5
RPE_TOO_HARD    = 9.0   # above this → maintain or deload


# ── Core logic ─────────────────────────────────────────────────────────────────

def recommend_progression(
    last_session:  SessionLog,
    level:         Level,
    movement_pattern: str = "default",
) -> ProgressionRecommendation:
    """
    Given the most recent session log for one exercise, return a progression
    recommendation for the next session.

    Decision tree:
      RPE ≤ 6.5 AND reps hit top of range → add load
      RPE 7-8.5 AND reps hit target        → maintain or small volume increase
      RPE > 9.0 OR reps missed target       → maintain load, check recovery
      Called on deload week                 → reduce load 10%
    """
    ex   = last_session.exercise_name
    rpe  = last_session.rpe
    reps = last_session.reps_done
    kg   = last_session.weight_kg
    increment = LOAD_INCREMENTS.get(level, LOAD_INCREMENTS["intermediate"]).get(
        movement_pattern, LOAD_INCREMENTS["intermediate"]["default"]
    )

    if rpe <= RPE_TOO_EASY:
        return ProgressionRecommendation(
            exercise       = ex,
            action         = "increase_load",
            delta_kg       = increment,
            rationale      = f"RPE {rpe} is below target. Add {increment} kg next session.",
            new_rpe_target = RPE_IDEAL_LOW,
        )
    elif rpe <= RPE_IDEAL_HIGH:
        # In the ideal zone — consider volume increase before load
        return ProgressionRecommendation(
            exercise       = ex,
            action         = "increase_volume",
            delta_sets     = 1 if last_session.sets_done < 5 else 0,
            delta_reps     = 1 if last_session.sets_done >= 5 else 0,
            rationale      = f"RPE {rpe} is in ideal range. Add one set or one rep before increasing load.",
            new_rpe_target = RPE_IDEAL_HIGH,
        )
    elif rpe < RPE_TOO_HARD:
        return ProgressionRecommendation(
            exercise       = ex,
            action         = "maintain",
            rationale      = f"RPE {rpe} — good session. Repeat same load next week.",
            new_rpe_target = RPE_IDEAL_HIGH,
        )
    else:
        return ProgressionRecommendation(
            exercise       = ex,
            action         = "maintain",
            delta_kg       = 0,
            rationale      = (
                f"RPE {rpe} is very high. Prioritise recovery. "
                "Do not increase load until RPE drops below 9."
            ),
            new_rpe_target = RPE_IDEAL_HIGH,
        )


def deload_recommendation(current_weight_kg: float, deload_pct: float = 0.10) -> dict:
    """
    Return deload parameters: reduce load by deload_pct (default 10%),
    reduce sets by 1, maintain reps.
    Called automatically every 4th week of a training block.
    """
    return {
        "load_kg":        round(current_weight_kg * (1 - deload_pct), 2),
        "sets_reduction": 1,
        "rpe_target":     6.0,
        "rationale":      (
            f"Week 4 deload. Reduce load to {round(current_weight_kg * (1-deload_pct), 1)} kg "
            f"({int(deload_pct*100)}% reduction), drop one set, keep reps the same. "
            "Focus on technique and recovery."
        ),
    }


# ── Periodisation planner ──────────────────────────────────────────────────────

@dataclass
class TrainingBlock:
    """A 4-week mesocycle: 3 accumulation weeks + 1 deload."""
    block_number:  int
    start_load_kg: float
    exercise:      str
    level:         Level
    pattern:       str = "default"
    weeks:         list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.weeks:
            self.weeks = self._build_weeks()

    def _build_weeks(self) -> list[dict]:
        increment = LOAD_INCREMENTS.get(self.level, {}).get(self.pattern, 2.5)
        weeks = []
        for w in range(1, 5):
            if w < 4:
                load = self.start_load_kg + increment * (w - 1)
                rpe_target = 7.0 + (w - 1) * 0.5          # ramps 7→8 across accumulation
                weeks.append({
                    "week":       w,
                    "type":       "accumulation",
                    "load_kg":    round(load, 2),
                    "rpe_target": round(rpe_target, 1),
                    "note":       f"Week {w} — push to RPE {round(rpe_target,1)}.",
                })
            else:
                deload_load = self.start_load_kg * 0.90
                weeks.append({
                    "week":       4,
                    "type":       "deload",
                    "load_kg":    round(deload_load, 2),
                    "rpe_target": 6.0,
                    "note":       "Deload week — reduced intensity, focus on recovery.",
                })
        return weeks

    def to_dict(self) -> dict:
        return {
            "block":    self.block_number,
            "exercise": self.exercise,
            "level":    self.level,
            "weeks":    self.weeks,
        }


def plan_training_blocks(
    exercise:      str,
    starting_kg:   float,
    level:         Level,
    pattern:       str  = "default",
    num_blocks:    int  = 3,
) -> list[dict]:
    """
    Plan N consecutive 4-week training blocks for one exercise.
    Each block starts from where the previous one left off (minus deload).

    Returns a list of block dicts for the agent to present.
    """
    blocks: list[dict] = []
    current_start = starting_kg

    for i in range(1, num_blocks + 1):
        block = TrainingBlock(
            block_number  = i,
            start_load_kg = current_start,
            exercise      = exercise,
            level         = level,
            pattern       = pattern,
        )
        blocks.append(block.to_dict())
        # Next block starts from week-3 load (after deload recovery)
        increment = LOAD_INCREMENTS.get(level, {}).get(pattern, 2.5)
        current_start = round(current_start + increment * 2, 2)   # 2 weeks of gain carried over

    return blocks


# ── One-rep max estimators ─────────────────────────────────────────────────────

def epley_1rm(weight_kg: float, reps: int) -> float:
    """Epley formula: 1RM = w × (1 + r/30). Most used in strength sports."""
    if reps == 1:
        return weight_kg
    return round(weight_kg * (1 + reps / 30), 1)


def brzycki_1rm(weight_kg: float, reps: int) -> float:
    """Brzycki formula: more accurate at lower rep ranges (1-10)."""
    if reps >= 37:   # formula breaks down at high reps
        return weight_kg
    return round(weight_kg * (36 / (37 - reps)), 1)


def percentage_of_1rm(one_rm: float, pct: float) -> float:
    """Return the load at a given percentage of 1RM."""
    return round(one_rm * pct / 100, 2)


def rpe_to_rir(rpe: float) -> int:
    """Convert RPE to Reps in Reserve (RIR = 10 - RPE)."""
    return max(0, round(10 - rpe))


def rir_to_rpe(rir: int) -> float:
    """Convert Reps in Reserve to RPE."""
    return round(10 - rir, 1)
