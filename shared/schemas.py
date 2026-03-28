"""
shared/schemas.py
Pydantic schemas shared across all agents. Acts as the contract between
the orchestrator, sub-agents, and the API layer.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import date


# ── User profile ──────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    user_id: str
    name: str
    age: int
    weight_kg: float
    height_cm: float
    sex: Literal["male", "female", "other"]
    experience_level: Literal["beginner", "intermediate", "advanced"]
    goals: List[Literal["strength", "hypertrophy", "fat_loss", "endurance", "general_health"]]
    injuries: Optional[List[str]] = []
    dietary_restrictions: Optional[List[str]] = []


# ── Form analysis ─────────────────────────────────────────────────────────────

class FormIssue(BaseModel):
    title: str
    description: str
    severity: Literal["minor", "moderate", "major"]
    cue: str                        # One actionable coaching cue


class FormAnalysisResult(BaseModel):
    score: int = Field(ge=0, le=100)
    label: Literal["Excellent form", "Good form", "Needs improvement", "Poor form", "Cannot assess"]
    summary: str
    safe_to_continue: bool
    issues: List[FormIssue] = []
    cues: List[str] = []
    visibility_notes: Optional[str] = None
    exercise: str
    analyzed_at: str                # ISO timestamp


# ── Nutrition ─────────────────────────────────────────────────────────────────

class MacroTargets(BaseModel):
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float


class MealPlan(BaseModel):
    day: date
    meals: List[dict]               # {"name": str, "foods": [...], "macros": MacroTargets}
    total_macros: MacroTargets
    notes: Optional[str] = None


# ── Workout planner ───────────────────────────────────────────────────────────

class Exercise(BaseModel):
    name: str
    sets: int
    reps: str                       # e.g. "8-12" or "5"
    rpe: Optional[float] = None     # Rate of perceived exertion 1-10
    notes: Optional[str] = None


class WorkoutSession(BaseModel):
    session_id: str
    day: str                        # "Monday", "Tuesday", etc.
    focus: str                      # "Upper body push", "Lower body", etc.
    exercises: List[Exercise]
    estimated_duration_min: int


class WorkoutPlan(BaseModel):
    plan_id: str
    user_id: str
    week: int
    sessions: List[WorkoutSession]
    progression_notes: Optional[str] = None


# ── Agent state (shared across all agents via session) ────────────────────────

class AgentState(BaseModel):
    user_profile: Optional[UserProfile] = None
    workout_plan: Optional[WorkoutPlan] = None
    meal_plan: Optional[MealPlan] = None
    recent_form_analyses: List[FormAnalysisResult] = []
    mood_score: Optional[int] = None        # 1-10 from mental health check-in
    energy_level: Optional[int] = None     # 1-10
    session_notes: List[str] = []