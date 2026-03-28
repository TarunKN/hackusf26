"""
agents/workout_planner/routines.py

Exercise library and session template builder.
The workout planner agent calls these to get validated exercise selections and
structured session skeletons — avoiding hallucinated exercise names or impossible
set/rep schemes from the LLM.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

Level    = Literal["beginner", "intermediate", "advanced"]
Goal     = Literal["strength", "hypertrophy", "fat_loss", "endurance", "general_health"]
Pattern  = Literal["squat", "hinge", "push_horizontal", "push_vertical",
                   "pull_horizontal", "pull_vertical", "carry", "core", "accessory"]


# ── Exercise dataclass ─────────────────────────────────────────────────────────

@dataclass
class ExerciseTemplate:
    name:          str
    pattern:       Pattern
    equipment:     list[str]                      # ["barbell", "rack"] etc.
    levels:        list[Level]                    # which levels this suits
    goals:         list[Goal]
    sets:          str                            # "3-4"
    reps:          str                            # "5" | "8-12" | "12-15"
    rpe:           str                            # "7-8"
    contraindications: list[str] = field(default_factory=list)   # injury keywords
    notes:         str = ""

    def to_dict(self) -> dict:
        return {
            "name":       self.name,
            "pattern":    self.pattern,
            "sets":       self.sets,
            "reps":       self.reps,
            "rpe":        self.rpe,
            "equipment":  self.equipment,
            "notes":      self.notes,
        }


# ── Exercise library ───────────────────────────────────────────────────────────
# A curated, injury-aware library.  Not exhaustive — the LLM can augment,
# but it will always start from validated templates.

EXERCISE_LIBRARY: list[ExerciseTemplate] = [

    # ── Squat pattern ─────────────────────────────────────────────────────────
    ExerciseTemplate("Barbell back squat",      "squat",
        ["barbell","rack"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "4-5","3-6","8-9",
        contraindications=["knee replacement","hip replacement"],
        notes="Brace core, knees track toes, break parallel."),

    ExerciseTemplate("Barbell front squat",     "squat",
        ["barbell","rack"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "3-4","4-6","8",
        contraindications=["wrist pain","shoulder pain"],
        notes="Upright torso, elbows high."),

    ExerciseTemplate("Goblet squat",            "squat",
        ["dumbbell","kettlebell"], ["beginner","intermediate"],
        ["hypertrophy","general_health","fat_loss"], "3","10-15","7",
        notes="Great for teaching squat mechanics. Counterbalance aids depth."),

    ExerciseTemplate("Bulgarian split squat",   "squat",
        ["dumbbell","barbell"], ["intermediate","advanced"],
        ["hypertrophy","fat_loss"], "3-4","8-12","8",
        contraindications=["knee pain","hip flexor strain"],
        notes="Rear foot elevated. Front shin vertical at bottom."),

    ExerciseTemplate("Leg press",               "squat",
        ["leg press machine"], ["beginner","intermediate","advanced"],
        ["hypertrophy","general_health"], "3-4","10-15","7-8",
        notes="Good option when spinal loading is contraindicated."),

    ExerciseTemplate("Box squat",               "squat",
        ["barbell","rack","box"], ["beginner","intermediate","advanced"],
        ["strength"], "4-5","3-5","8",
        notes="Sit back onto box; teaches hip hinge in squat."),

    # ── Hinge pattern ─────────────────────────────────────────────────────────
    ExerciseTemplate("Conventional deadlift",   "hinge",
        ["barbell"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "4-5","3-6","9",
        contraindications=["disc herniation","lower back injury"],
        notes="Lat tight, bar close, drive floor away."),

    ExerciseTemplate("Romanian deadlift",       "hinge",
        ["barbell","dumbbell"], ["beginner","intermediate","advanced"],
        ["hypertrophy","general_health"], "3-4","8-12","7-8",
        notes="Hinge until hamstring tension, neutral spine throughout."),

    ExerciseTemplate("Trap bar deadlift",       "hinge",
        ["trap bar"], ["beginner","intermediate","advanced"],
        ["strength","general_health"], "4","4-6","8",
        notes="More upright torso than conventional. Easier on lower back."),

    ExerciseTemplate("Kettlebell swing",        "hinge",
        ["kettlebell"], ["beginner","intermediate"],
        ["endurance","fat_loss","general_health"], "4","15-20","7",
        notes="Hip snap, not a squat. Powerful hip extension."),

    ExerciseTemplate("Good morning",            "hinge",
        ["barbell"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "3","8-10","7",
        contraindications=["lower back injury"],
        notes="Light load, feel hamstrings. Don't round lower back."),

    # ── Horizontal push ───────────────────────────────────────────────────────
    ExerciseTemplate("Barbell bench press",     "push_horizontal",
        ["barbell","bench"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "4-5","3-6","8-9",
        contraindications=["shoulder impingement","AC joint pain"],
        notes="Retract scapulae, slight arch, elbows ~75°."),

    ExerciseTemplate("Dumbbell bench press",    "push_horizontal",
        ["dumbbell","bench"], ["beginner","intermediate","advanced"],
        ["hypertrophy","general_health"], "3-4","8-12","7-8",
        notes="Greater ROM than barbell. Good for shoulder health."),

    ExerciseTemplate("Push-up",                 "push_horizontal",
        ["bodyweight"], ["beginner","intermediate"],
        ["general_health","fat_loss","endurance"], "3","10-20","7",
        notes="Hands just outside shoulder width. Full lockout."),

    ExerciseTemplate("Incline dumbbell press",  "push_horizontal",
        ["dumbbell","bench"], ["beginner","intermediate","advanced"],
        ["hypertrophy"], "3-4","10-15","7-8",
        notes="30-45° incline hits upper chest."),

    # ── Vertical push ─────────────────────────────────────────────────────────
    ExerciseTemplate("Barbell overhead press",  "push_vertical",
        ["barbell","rack"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "4","4-8","8",
        contraindications=["shoulder impingement","rotator cuff"],
        notes="Bar path: chin back, press up and slightly back."),

    ExerciseTemplate("Dumbbell shoulder press", "push_vertical",
        ["dumbbell"], ["beginner","intermediate","advanced"],
        ["hypertrophy","general_health"], "3-4","10-15","7-8",
        notes="Neutral or pronated grip. Don't shrug."),

    ExerciseTemplate("Landmine press",          "push_vertical",
        ["barbell","landmine"], ["beginner","intermediate","advanced"],
        ["hypertrophy","general_health"], "3","10-12","7",
        notes="Shoulder-friendly pressing variation. Great for beginners."),

    # ── Horizontal pull ───────────────────────────────────────────────────────
    ExerciseTemplate("Barbell row",             "pull_horizontal",
        ["barbell"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "4","4-8","8",
        contraindications=["lower back injury"],
        notes="Hinge to ~45°, row to hip, squeeze at top."),

    ExerciseTemplate("Dumbbell row",            "pull_horizontal",
        ["dumbbell","bench"], ["beginner","intermediate","advanced"],
        ["hypertrophy","general_health"], "3-4","10-15","7-8",
        notes="Support with opposite hand, full stretch at bottom."),

    ExerciseTemplate("Cable row",               "pull_horizontal",
        ["cable machine"], ["beginner","intermediate","advanced"],
        ["hypertrophy","general_health"], "3-4","10-15","7-8",
        notes="Drive elbows back, keep torso upright."),

    ExerciseTemplate("Seated machine row",      "pull_horizontal",
        ["machine"], ["beginner"],
        ["general_health","hypertrophy"], "3","12-15","7",
        notes="Stable base. Good for teaching the movement pattern."),

    # ── Vertical pull ─────────────────────────────────────────────────────────
    ExerciseTemplate("Pull-up / chin-up",       "pull_vertical",
        ["pull-up bar"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "3-4","4-10","8",
        notes="Full hang at bottom, chin over bar at top."),

    ExerciseTemplate("Assisted pull-up",        "pull_vertical",
        ["assisted machine","band"], ["beginner"],
        ["general_health","hypertrophy"], "3","8-12","7",
        notes="Use assistance to build the movement pattern."),

    ExerciseTemplate("Lat pulldown",            "pull_vertical",
        ["cable machine"], ["beginner","intermediate","advanced"],
        ["hypertrophy","general_health"], "3-4","10-15","7-8",
        notes="Pull to upper chest, slight lean back."),

    # ── Core ──────────────────────────────────────────────────────────────────
    ExerciseTemplate("Plank",                   "core",
        ["bodyweight"], ["beginner","intermediate","advanced"],
        ["general_health","strength","endurance"], "3","30-60s","7",
        notes="Neutral spine. Don't let hips sag or pike."),

    ExerciseTemplate("Pallof press",            "core",
        ["cable machine","band"], ["beginner","intermediate","advanced"],
        ["general_health","strength"], "3","10-12","7",
        notes="Anti-rotation. Keep hips square."),

    ExerciseTemplate("Dead bug",                "core",
        ["bodyweight"], ["beginner","intermediate"],
        ["general_health","strength"], "3","8-10","6-7",
        notes="Lower back pressed to floor throughout."),

    ExerciseTemplate("Ab wheel rollout",        "core",
        ["ab wheel"], ["intermediate","advanced"],
        ["strength","hypertrophy"], "3","8-12","8",
        contraindications=["lower back injury"],
        notes="Keep core braced, don't let hips drop."),

    # ── Carry ─────────────────────────────────────────────────────────────────
    ExerciseTemplate("Farmer's carry",          "carry",
        ["dumbbell","kettlebell","trap bar"], ["beginner","intermediate","advanced"],
        ["strength","general_health","fat_loss"], "3","20-40m","7",
        notes="Stand tall, brace core, don't lean."),

    ExerciseTemplate("Suitcase carry",          "carry",
        ["dumbbell","kettlebell"], ["beginner","intermediate","advanced"],
        ["general_health","strength"], "3","20m each side","7",
        notes="Anti-lateral flexion. Great for core stability."),
]


# ── Library query helpers ──────────────────────────────────────────────────────

def filter_exercises(
    pattern:     Pattern | None   = None,
    level:       Level | None     = None,
    goal:        Goal | None      = None,
    exclude_contraindications: list[str] | None = None,
    equipment_available: list[str] | None = None,
) -> list[ExerciseTemplate]:
    """
    Filter the exercise library by any combination of criteria.
    Returns all exercises that pass every supplied filter.
    """
    results = EXERCISE_LIBRARY.copy()

    if pattern:
        results = [e for e in results if e.pattern == pattern]
    if level:
        results = [e for e in results if level in e.levels]
    if goal:
        results = [e for e in results if goal in e.goals]
    if exclude_contraindications:
        keywords = [kw.lower() for kw in exclude_contraindications]
        results = [
            e for e in results
            if not any(
                any(kw in ci.lower() for kw in keywords)
                for ci in e.contraindications
            )
        ]
    if equipment_available:
        avail = {eq.lower() for eq in equipment_available}
        results = [
            e for e in results
            if any(eq.lower() in avail for eq in e.equipment)
        ]

    return results


def get_exercise_by_name(name: str) -> ExerciseTemplate | None:
    name_lower = name.lower()
    for ex in EXERCISE_LIBRARY:
        if ex.name.lower() == name_lower:
            return ex
    return None


# ── Session skeleton builder ───────────────────────────────────────────────────

# Movement patterns required per training split
PPL_SESSIONS = {
    "Push": ["push_horizontal", "push_vertical", "core"],
    "Pull": ["pull_horizontal", "pull_vertical", "core"],
    "Legs": ["squat", "hinge", "carry"],
}

UPPER_LOWER_SESSIONS = {
    "Upper": ["push_horizontal", "push_vertical", "pull_horizontal", "pull_vertical"],
    "Lower": ["squat", "hinge", "core", "carry"],
}

FULL_BODY_PATTERNS = ["squat", "hinge", "push_horizontal", "pull_vertical", "core"]


def build_session_skeleton(
    session_name:  str,
    patterns:      list[Pattern],
    level:         Level,
    goal:          Goal,
    injuries:      list[str] | None = None,
    equipment:     list[str] | None = None,
) -> list[dict]:
    """
    For each movement pattern, pick the best matching exercise from the library
    and return a list of exercise dicts ready for the LLM agent to present.
    """
    skeleton: list[dict] = []
    for pattern in patterns:
        options = filter_exercises(
            pattern                   = pattern,
            level                     = level,
            goal                      = goal,
            exclude_contraindications = injuries or [],
            equipment_available       = equipment,
        )
        if options:
            skeleton.append(options[0].to_dict())   # Best match (first result)

    return skeleton


def session_skeletons_for_split(
    split:    Literal["PPL", "Upper_Lower", "Full_Body"],
    level:    Level,
    goal:     Goal,
    injuries: list[str] | None = None,
    equipment: list[str] | None = None,
) -> dict[str, list[dict]]:
    """
    Return skeleton sessions for the given split style, e.g.:
    {"Push": [...exercises], "Pull": [...], "Legs": [...]}
    """
    if split == "PPL":
        session_map = PPL_SESSIONS
    elif split == "Upper_Lower":
        session_map = UPPER_LOWER_SESSIONS
    else:
        session_map = {"Full Body": FULL_BODY_PATTERNS}

    return {
        name: build_session_skeleton(name, patterns, level, goal, injuries, equipment)
        for name, patterns in session_map.items()
    }
