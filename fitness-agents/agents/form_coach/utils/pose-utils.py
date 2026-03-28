"""
agents/form_coach/pose_utils.py

Utility functions for processing pose/biomechanical data returned by Gemini Vision.
In a production system you could swap these calculations for MediaPipe landmark
coordinates — the interface is the same.  For the hackathon, these helpers operate
on the structured JSON the vision model returns so every calculation is deterministic
and testable without a GPU.
"""

from __future__ import annotations
import math
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class Point2D:
    x: float
    y: float


@dataclass
class JointAngles:
    """Angles in degrees at major joints, None if the landmark was not visible."""
    left_knee:   Optional[float] = None
    right_knee:  Optional[float] = None
    left_hip:    Optional[float] = None
    right_hip:   Optional[float] = None
    left_elbow:  Optional[float] = None
    right_elbow: Optional[float] = None
    torso_lean:  Optional[float] = None   # degrees from vertical


@dataclass
class PostureFlags:
    """Boolean flags derived from angle thresholds."""
    knee_valgus:        bool = False   # knee caving inward
    butt_wink:          bool = False   # pelvis posterior tilt at depth
    forward_lean:       bool = False   # excessive torso lean
    elbow_flare:        bool = False   # elbows flaring on bench/OHP
    hyperextension:     bool = False   # lumbar hyperextension
    asymmetry_detected: bool = False   # notable L/R difference


# ── Geometry helpers ───────────────────────────────────────────────────────────

def angle_between(a: Point2D, vertex: Point2D, b: Point2D) -> float:
    """
    Return the angle in degrees at `vertex` formed by rays vertex→a and vertex→b.
    Uses the law of cosines on the three point distances.
    """
    ax, ay = a.x - vertex.x, a.y - vertex.y
    bx, by = b.x - vertex.x, b.y - vertex.y
    dot   = ax * bx + ay * by
    mag_a = math.hypot(ax, ay)
    mag_b = math.hypot(bx, by)
    if mag_a == 0 or mag_b == 0:
        return 0.0
    cos_theta = max(-1.0, min(1.0, dot / (mag_a * mag_b)))
    return math.degrees(math.acos(cos_theta))


def vertical_angle(top: Point2D, bottom: Point2D) -> float:
    """
    Return the angle in degrees between the segment top→bottom and a vertical line.
    0° = perfectly vertical, 90° = horizontal.
    """
    dx = top.x - bottom.x
    dy = top.y - bottom.y          # y increases downward in image coords
    return math.degrees(math.atan2(abs(dx), abs(dy)))


def midpoint(a: Point2D, b: Point2D) -> Point2D:
    return Point2D((a.x + b.x) / 2, (a.y + b.y) / 2)


def distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


# ── Angle extraction from Gemini Vision JSON ───────────────────────────────────

def extract_joint_angles_from_vision(vision_json: dict) -> JointAngles:
    """
    Parse joint angle estimates out of the structured response from Gemini Vision.
    Gemini Vision doesn't return raw pixel coordinates by default, but when the
    vision prompt asks for angle estimates it returns them as numeric fields.

    Expected keys in vision_json (all optional — model may omit invisible joints):
      knee_angle_left, knee_angle_right,
      hip_angle_left,  hip_angle_right,
      elbow_angle_left, elbow_angle_right,
      torso_lean_degrees
    """
    def safe_float(key: str) -> Optional[float]:
        val = vision_json.get(key)
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    return JointAngles(
        left_knee   = safe_float("knee_angle_left"),
        right_knee  = safe_float("knee_angle_right"),
        left_hip    = safe_float("hip_angle_left"),
        right_hip   = safe_float("hip_angle_right"),
        left_elbow  = safe_float("elbow_angle_left"),
        right_elbow = safe_float("elbow_angle_right"),
        torso_lean  = safe_float("torso_lean_degrees"),
    )


# ── Posture flag derivation ────────────────────────────────────────────────────

# Thresholds tuned for common powerlifting / strength training cues.
# All values are in degrees.
THRESHOLDS = {
    "squat_depth_hip_angle":    100,   # hip angle > 100° = above parallel
    "knee_valgus_diff":          10,   # L vs R knee angle difference > 10° suggests valgus
    "forward_lean_squat":        45,   # torso lean > 45° on squat = excessive
    "forward_lean_deadlift":     30,   # torso lean > 30° at lockout = not locked out
    "elbow_flare_bench":         75,   # elbow angle < 75° = too flared
    "lumbar_hyperextension":     15,   # torso lean backward > 15° = hyperextension
    "asymmetry_hip":             8,    # L vs R hip angle difference > 8° = asymmetry
}


def derive_posture_flags(angles: JointAngles, exercise: str) -> PostureFlags:
    """
    Apply exercise-specific threshold rules to JointAngles and return PostureFlags.
    All rules are no-ops when the relevant angle is None (joint not visible).
    """
    flags = PostureFlags()
    ex = exercise.lower()

    # Knee valgus: significant asymmetry in knee angle suggests one knee is caving
    if angles.left_knee is not None and angles.right_knee is not None:
        if abs(angles.left_knee - angles.right_knee) > THRESHOLDS["knee_valgus_diff"]:
            flags.knee_valgus = True
            logger.debug(f"Knee valgus flagged: L={angles.left_knee:.1f}° R={angles.right_knee:.1f}°")

    # Torso lean
    if angles.torso_lean is not None:
        if "squat" in ex and angles.torso_lean > THRESHOLDS["forward_lean_squat"]:
            flags.forward_lean = True
        if "deadlift" in ex and angles.torso_lean > THRESHOLDS["forward_lean_deadlift"]:
            flags.forward_lean = True
        if angles.torso_lean < -THRESHOLDS["lumbar_hyperextension"]:
            flags.hyperextension = True

    # Elbow flare on pressing movements
    if "bench" in ex or "press" in ex:
        for elbow_angle in [angles.left_elbow, angles.right_elbow]:
            if elbow_angle is not None and elbow_angle < THRESHOLDS["elbow_flare_bench"]:
                flags.elbow_flare = True
                break

    # Butt wink: detected when hip angle opens significantly (pelvis tilts under)
    # A full depth squat hip angle < 70° combined with visible spine rounding = butt wink
    if "squat" in ex:
        for hip in [angles.left_hip, angles.right_hip]:
            if hip is not None and hip < 70:
                flags.butt_wink = True
                break

    # General asymmetry check
    if angles.left_hip is not None and angles.right_hip is not None:
        if abs(angles.left_hip - angles.right_hip) > THRESHOLDS["asymmetry_hip"]:
            flags.asymmetry_detected = True

    return flags


# ── Severity scoring ───────────────────────────────────────────────────────────

def flags_to_severity_score(flags: PostureFlags) -> tuple[int, list[str]]:
    """
    Convert PostureFlags to a 0–100 form score and a list of human-readable issues.
    Higher score = better form.  Deductions are cumulative.

    Returns:
        (score: int, issues: list[str])
    """
    score = 100
    issues: list[str] = []

    deductions = {
        "knee_valgus":        (15, "Knee valgus (caving) detected"),
        "butt_wink":          (10, "Butt wink at depth — pelvis is tucking under"),
        "forward_lean":       (12, "Excessive torso lean forward"),
        "elbow_flare":        (8,  "Elbows flaring — shoulder impingement risk"),
        "hyperextension":     (12, "Lumbar hyperextension detected"),
        "asymmetry_detected": (5,  "Notable left/right asymmetry"),
    }

    for attr, (penalty, message) in deductions.items():
        if getattr(flags, attr, False):
            score -= penalty
            issues.append(message)

    return max(0, score), issues


# ── Public convenience function ────────────────────────────────────────────────

def process_vision_output(vision_json: dict, exercise: str) -> dict:
    """
    Full pipeline: vision JSON → joint angles → posture flags → score + issues.
    Returns a dict compatible with the FormAnalysisResult schema additions.
    """
    angles = extract_joint_angles_from_vision(vision_json)
    flags  = derive_posture_flags(angles, exercise)
    score, flag_issues = flags_to_severity_score(flags)

    return {
        "computed_score":  score,
        "posture_flags":   vars(flags),
        "joint_angles":    {k: v for k, v in vars(angles).items() if v is not None},
        "flag_issues":     flag_issues,
    }
