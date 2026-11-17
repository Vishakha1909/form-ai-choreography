from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


FormationKind = Literal[
    "line", "v", "inverted_v", "circle", "semicircle", "diagonal",
    "two_rows", "two_columns", "staggered", "diamond", "box", "cross",
]


class Point(BaseModel):
    x: float
    y: float


class StageConstraints(BaseModel):
    dancer_count: int = Field(6, ge=3, le=10)
    stage_width: float = Field(12, gt=2, le=40)
    stage_depth: float = Field(8, gt=2, le=30)
    min_spacing: float = Field(1.2, gt=0.1, le=8)
    max_speed: float = Field(3.0, gt=0.1, le=10)
    mood: str = Field("dynamic and architectural", max_length=500)
    preferred_formations: list[FormationKind] = Field(default_factory=lambda: ["line", "v", "circle", "diagonal", "two_rows"])
    preferred_motion_genres: list[str] = Field(default_factory=list)
    motion_selection_mode: Literal["palette", "sequence"] = "palette"


class AudioFrame(BaseModel):
    time: float
    value: float


class MusicalSection(BaseModel):
    start: float
    end: float
    label: str
    energy: Literal["low", "medium", "high"]
    mean_rms: float
    interpretation: str


class AudioAnalysis(BaseModel):
    filename: str
    duration: float
    tempo: float
    beat_times: list[float]
    onset_envelope: list[AudioFrame]
    rms_envelope: list[AudioFrame]
    waveform: list[AudioFrame]
    sections: list[MusicalSection]
    notes: list[str]


class PoseLandmark(BaseModel):
    x: float
    y: float
    z: float
    visibility: float


class PoseFrame(BaseModel):
    time: float
    motion_energy: float
    landmarks: dict[str, PoseLandmark]


class MotionAnalysis(BaseModel):
    filename: str
    duration: float
    source_fps: float
    sampled_fps: float
    sampled_frames: int
    detected_frames: int
    pose_coverage: float
    mean_motion_energy: float
    high_motion_times: list[float]
    frames: list[PoseFrame]
    notes: list[str]


class EnsembleDancerMetrics(BaseModel):
    dancer_id: str
    coverage: float
    mean_timing_offset_ms: float | None = None
    mean_pose_deviation_deg: float
    motion_consistency: float
    synchronization_score: float


class EnsembleSyncEvent(BaseModel):
    time: float
    dancer_id: str | None = None
    kind: Literal["timing", "pose", "spacing", "tracking"]
    severity: Literal["info", "warning", "high"]
    message: str
    value: float | None = None


class EnsembleTimelinePoint(BaseModel):
    time: float
    detected_dancers: int
    synchronization_score: float


class EnsemblePoseFrame(BaseModel):
    time: float
    dancers: dict[str, dict[str, PoseLandmark]]


class EnsembleAnalysis(BaseModel):
    filename: str
    duration: float
    expected_dancers: int
    tracked_dancers: int
    sampled_frames: int
    multi_person_coverage: float
    full_ensemble_coverage: float
    mean_detected_dancers: float
    observation_confidence_score: float
    overall_synchronization_score: float
    timing_score: float | None = None
    pose_agreement_score: float
    spacing_consistency_score: float
    dancers: list[EnsembleDancerMetrics]
    events: list[EnsembleSyncEvent]
    timeline: list[EnsembleTimelinePoint]
    pose_frames: list[EnsemblePoseFrame] = Field(default_factory=list)
    notes: list[str]


class MotionClipSummary(BaseModel):
    id: str
    name: str
    genre: str
    source: str
    duration: float = Field(gt=0)
    fps: float = Field(gt=0)
    frame_count: int = Field(gt=0)
    loopable: bool = False
    attribution: str
    collection: str = "AIST++"
    movement_family: str | None = None
    style: str | None = None
    source_url: str | None = None
    label_scope: Literal["genre", "family_reference"] = "genre"
    default_counts: int | None = Field(None, ge=1, le=128)


class MotionClip(MotionClipSummary):
    frames: list[PoseFrame]


Movement = Literal["travel", "hold", "turn", "level_change", "canon", "ripple", "unison"]


class Formation(BaseModel):
    id: str
    name: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    positions: dict[str, Point]
    geometry_kind: FormationKind | None = None
    movement: Movement
    movement_description: str
    rationale: str
    motion_clip_id: str | None = None
    motion_speed: float = Field(1.0, ge=0.5, le=2.0)
    mirror_motion: bool = False
    phase_offset: float = Field(0.0, ge=0, le=4)
    counts: int | None = Field(None, ge=1, le=128)

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end <= self.start:
            raise ValueError("formation end must be after start")
        return self


class ChoreographyPlan(BaseModel):
    title: str
    creative_direction: str
    formations: list[Formation]


class ValidationIssue(BaseModel):
    code: Literal["OUT_OF_BOUNDS", "MIN_SPACING", "EXCESSIVE_DISTANCE", "INSUFFICIENT_TIME", "PATH_COLLISION", "MISSING_DANCER", "TIMELINE_GAP", "MISSING_MOTION_CLIP", "UNKNOWN_MOTION_CLIP", "MOTION_TOO_SHORT"]
    message: str
    formation_id: str | None = None
    dancer_ids: list[str] = Field(default_factory=list)
    time: float | None = None
    details: dict[str, float | str] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue]
    samples_checked: int


class PlanRequest(BaseModel):
    analysis: AudioAnalysis
    constraints: StageConstraints
    previous_plan: ChoreographyPlan | None = None
    motion_analysis: MotionAnalysis | None = None


class ValidationRequest(BaseModel):
    plan: ChoreographyPlan
    constraints: StageConstraints


class FormationGeometryRequest(BaseModel):
    kind: FormationKind
    constraints: StageConstraints
    previous_positions: dict[str, Point] | None = None


class PlanRevisionRequest(BaseModel):
    analysis: AudioAnalysis
    constraints: StageConstraints
    current_plan: ChoreographyPlan
    instruction: str = Field(min_length=3, max_length=1000)


class PlanRevisionResponse(BaseModel):
    revised_plan: ChoreographyPlan
    validation: ValidationResult
    attempts: int
    latency_ms: int
    execution_mode: Literal["live_agent"] = "live_agent"
    summary: str
    changes: list[str]


class DecisionLogEntry(BaseModel):
    attempt: int
    phase: str
    message: str
    validation: ValidationResult | None = None


class PlanResponse(BaseModel):
    plan: ChoreographyPlan
    validation: ValidationResult
    attempts: int
    latency_ms: int
    execution_mode: Literal["live_agent", "local_fallback", "cached_demo"]
    decision_log: list[DecisionLogEntry]
    changes: list[str] = Field(default_factory=list)

