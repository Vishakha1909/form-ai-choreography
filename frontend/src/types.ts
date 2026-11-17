export type Point = { x: number; y: number };
export type Frame = { time: number; value: number };
export type Section = {
  start: number;
  end: number;
  label: string;
  energy: "low" | "medium" | "high";
  mean_rms: number;
  interpretation: string;
};
export type Analysis = {
  filename: string;
  duration: number;
  tempo: number;
  beat_times: number[];
  onset_envelope: Frame[];
  rms_envelope: Frame[];
  waveform: Frame[];
  sections: Section[];
  notes: string[];
};
export type PoseLandmark = {
  x: number;
  y: number;
  z: number;
  visibility: number;
};
export type PoseFrame = {
  time: number;
  motion_energy: number;
  landmarks: Record<string, PoseLandmark>;
};
export type MotionAnalysis = {
  filename: string;
  duration: number;
  source_fps: number;
  sampled_fps: number;
  sampled_frames: number;
  detected_frames: number;
  pose_coverage: number;
  mean_motion_energy: number;
  high_motion_times: number[];
  frames: PoseFrame[];
  notes: string[];
};
export type EnsembleDancerMetrics = {
  dancer_id: string;
  coverage: number;
  mean_timing_offset_ms?: number | null;
  mean_pose_deviation_deg: number;
  motion_consistency: number;
  synchronization_score: number;
};
export type EnsembleSyncEvent = {
  time: number;
  dancer_id?: string | null;
  kind: "timing" | "pose" | "spacing" | "tracking";
  severity: "info" | "warning" | "high";
  message: string;
  value?: number | null;
};
export type EnsembleAnalysis = {
  filename: string;
  duration: number;
  expected_dancers: number;
  tracked_dancers: number;
  sampled_frames: number;
  multi_person_coverage: number;
  full_ensemble_coverage: number;
  mean_detected_dancers: number;
  observation_confidence_score: number;
  overall_synchronization_score: number;
  timing_score?: number | null;
  pose_agreement_score: number;
  spacing_consistency_score: number;
  dancers: EnsembleDancerMetrics[];
  events: EnsembleSyncEvent[];
  timeline: { time: number; detected_dancers: number; synchronization_score: number }[];
  pose_frames: { time: number; dancers: Record<string, Record<string, PoseLandmark>> }[];
  notes: string[];
};
export type MotionClipSummary = {
  id: string;
  name: string;
  genre: string;
  source: string;
  duration: number;
  fps: number;
  frame_count: number;
  loopable: boolean;
  attribution: string;
  collection: string;
  movement_family?: string | null;
  style?: string | null;
  source_url?: string | null;
  label_scope: "genre" | "family_reference";
  default_counts?: number | null;
};
export type MotionClip = MotionClipSummary & { frames: PoseFrame[] };
export type Constraints = {
  dancer_count: number;
  stage_width: number;
  stage_depth: number;
  min_spacing: number;
  max_speed: number;
  mood: string;
  preferred_formations: string[];
  preferred_motion_genres: string[];
  motion_selection_mode: "palette" | "sequence";
};
export type Formation = {
  id: string;
  name: string;
  start: number;
  end: number;
  positions: Record<string, Point>;
  geometry_kind?: string | null;
  movement: string;
  movement_description: string;
  rationale: string;
  motion_clip_id?: string | null;
  motion_speed: number;
  mirror_motion: boolean;
  phase_offset: number;
  counts?: number | null;
};
export type Plan = {
  title: string;
  creative_direction: string;
  formations: Formation[];
};
export type Issue = {
  code: string;
  message: string;
  formation_id?: string;
  dancer_ids: string[];
  time?: number;
  details: Record<string, string | number>;
};
export type Validation = {
  valid: boolean;
  issues: Issue[];
  samples_checked: number;
};
export type PlanResponse = {
  plan: Plan;
  validation: Validation;
  attempts: number;
  latency_ms: number;
  execution_mode: "live_agent" | "local_fallback" | "cached_demo";
  decision_log: {
    attempt: number;
    phase: string;
    message: string;
    validation?: Validation;
  }[];
  changes: string[];
};
export type PlanRevisionResponse = {
  revised_plan: Plan;
  validation: Validation;
  attempts: number;
  latency_ms: number;
  execution_mode: "live_agent";
  summary: string;
  changes: string[];
};
