import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import {
  Activity,
  AlertTriangle,
  Check,
  ChevronRight,
  Clock3,
  Download,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Redo2,
  RotateCcw,
  ScanLine,
  Sparkles,
  Upload,
  Undo2,
  Users,
  Volume2,
} from "lucide-react";
import type {
  Analysis,
  Constraints,
  EnsembleAnalysis,
  EnsembleSyncEvent,
  Formation,
  MotionAnalysis,
  MotionClip,
  MotionClipSummary,
  PlanResponse,
  PlanRevisionResponse,
  Point,
} from "./types";
import DancerGlyph from "./DancerGlyph";

const initialConstraints: Constraints = {
  dancer_count: 6,
  stage_width: 12,
  stage_depth: 8,
  min_spacing: 1.2,
  max_speed: 3,
  mood: "Cinematic, precise, with moments of expansive unison",
  preferred_formations: ["line", "v", "circle", "diagonal", "two_rows"],
  preferred_motion_genres: [],
  motion_selection_mode: "palette",
};
const formationChoices = [
  "line",
  "v",
  "inverted_v",
  "circle",
  "semicircle",
  "diagonal",
  "two_rows",
  "two_columns",
  "staggered",
  "diamond",
  "box",
  "cross",
];
const API = "/api";
const colors = [
  "#f8ff73",
  "#75f4d1",
  "#8da2ff",
  "#ff75ae",
  "#ffb86c",
  "#c792ff",
  "#4dd8ff",
  "#ff6b6b",
  "#a7ff83",
  "#ffd166",
];

function Timeline({
  analysis,
  time,
  onSeek,
}: {
  analysis: Analysis;
  time: number;
  onSeek: (n: number) => void;
}) {
  const w = 1000,
    h = 154;
  const duration = analysis.duration;
  return (
    <div
      className="timeline"
      onClick={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        onSeek(((e.clientX - r.left) / r.width) * duration);
      }}
    >
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        {analysis.sections.map((s, i) => (
          <rect
            key={s.label}
            x={(s.start / duration) * w}
            width={((s.end - s.start) / duration) * w}
            y="0"
            height={h}
            className={`energy ${s.energy}`}
            opacity={i % 2 ? 0.22 : 0.14}
          />
        ))}
        <line x1="0" x2={w} y1="77" y2="77" className="axis" />
        {analysis.waveform.map((p, i) => {
          const x = (p.time / duration) * w,
            bar = Math.max(2, p.value * 55);
          return (
            <line
              key={i}
              x1={x}
              x2={x}
              y1={77 - bar}
              y2={77 + bar}
              className="wave"
            />
          );
        })}
        {analysis.beat_times.map((b, i) => (
          <line
            key={i}
            x1={(b / duration) * w}
            x2={(b / duration) * w}
            y1="129"
            y2="139"
            className="beat"
          />
        ))}
        {analysis.sections.map((s) => (
          <text
            key={s.label}
            x={(s.start / duration) * w + 9}
            y="18"
            className="section-label"
          >
            {s.label} · {s.energy}
          </text>
        ))}
        <line
          x1={(time / duration) * w}
          x2={(time / duration) * w}
          y1="0"
          y2={h}
          className="playhead"
        />
      </svg>
    </div>
  );
}

const poseConnections = [
  ["left_shoulder", "right_shoulder"], ["left_shoulder", "left_elbow"], ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"], ["right_elbow", "right_wrist"], ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"], ["left_hip", "right_hip"], ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"], ["right_hip", "right_knee"], ["right_knee", "right_ankle"],
] as const;

function EnsembleDiagnosis({
  diagnosis,
  videoUrl,
  onAskAI,
}: {
  diagnosis: EnsembleAnalysis;
  videoUrl: string;
  onAskAI: (event: EnsembleSyncEvent) => void;
}) {
  const width = 900,
    height = 74,
    duration = Math.max(diagnosis.duration, 0.1),
    points = diagnosis.timeline.map((point) => `${(point.time / duration) * width},${height - (point.synchronization_score / 100) * (height - 8)}`).join(" ");
  const videoRef = useRef<HTMLVideoElement>(null);
  const [reviewTime, setReviewTime] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<EnsembleSyncEvent | null>(diagnosis.events[0] || null);
  const poseFrame = useMemo(() => {
    if (!diagnosis.pose_frames.length) return null;
    return diagnosis.pose_frames.reduce((nearest, frame) =>
      Math.abs(frame.time - reviewTime) < Math.abs(nearest.time - reviewTime) ? frame : nearest,
    );
  }, [diagnosis.pose_frames, reviewTime]);
  const seekReview = (target: number, event?: EnsembleSyncEvent) => {
    const bounded = Math.max(0, Math.min(target, duration));
    if (videoRef.current) videoRef.current.currentTime = bounded;
    setReviewTime(bounded);
    if (event) setSelectedEvent(event);
  };
  return (
    <section className="ensemble-diagnosis panel" id="rehearsal-review">
      <div className="panel-head">
        <div><span className="eyebrow">REHEARSAL INTELLIGENCE</span><h2>{diagnosis.overall_synchronization_score.toFixed(0)} <small>/ 100 {diagnosis.observation_confidence_score < 70 ? "provisional " : ""}synchronization</small></h2></div>
        <span className="ensemble-coverage">{diagnosis.tracked_dancers} track IDs · {diagnosis.mean_detected_dancers.toFixed(1)}/{diagnosis.expected_dancers} average visible</span>
      </div>
      <div className="ensemble-score-row">
        <div><b>{diagnosis.timing_score?.toFixed(0) ?? "—"}</b><span>BEAT TIMING</span></div>
        <div><b>{diagnosis.pose_agreement_score.toFixed(0)}</b><span>POSE AGREEMENT</span></div>
        <div><b>{diagnosis.spacing_consistency_score.toFixed(0)}</b><span>IMAGE-SPACE SPACING</span></div>
        <div><b>{Math.round(diagnosis.full_ensemble_coverage * 100)}%</b><span>FULL ENSEMBLE VISIBLE</span></div>
        <div><b>{diagnosis.observation_confidence_score.toFixed(0)}</b><span>OBSERVATION CONFIDENCE</span></div>
      </div>
      <div className="rehearsal-review-grid">
        <div className="rehearsal-player">
          <video ref={videoRef} src={videoUrl} controls preload="metadata" onTimeUpdate={(event) => setReviewTime(event.currentTarget.currentTime)} />
          {poseFrame && <svg className="pose-overlay" viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Tracked dancer pose overlay">
            {Object.entries(poseFrame.dancers).map(([dancerId, landmarks], dancerIndex) => {
              const color = colors[dancerIndex % colors.length];
              const visibleConnections = poseConnections.filter(([from, to]) => landmarks[from]?.visibility >= .3 && landmarks[to]?.visibility >= .3);
              const anchor = landmarks.nose || landmarks.left_shoulder;
              return <g key={dancerId}>
                {visibleConnections.map(([from, to]) => <line key={`${from}-${to}`} x1={landmarks[from].x} y1={landmarks[from].y} x2={landmarks[to].x} y2={landmarks[to].y} stroke={color} />)}
                {Object.entries(landmarks).filter(([, point]) => point.visibility >= .3).map(([name, point]) => <circle key={name} cx={point.x} cy={point.y} r=".006" fill={color} />)}
                {anchor && <text x={anchor.x} y={Math.max(.03, anchor.y - .045)} fill={color}>{dancerId}</text>}
              </g>;
            })}
          </svg>}
          <span className="overlay-disclosure">AI pose estimate · temporary IDs</span>
        </div>
        <div className="review-inspector">
          <span className="eyebrow">SELECTED MOMENT · {reviewTime.toFixed(1)}s</span>
          {selectedEvent ? <>
            <strong>{selectedEvent.kind.toUpperCase()} · {selectedEvent.severity}</strong>
            <p>{selectedEvent.message}</p>
            <button onClick={() => onAskAI(selectedEvent)}><Sparkles size={13} /> Ask AI how to adapt the choreography</button>
          </> : <p>Select a warning marker or timeline moment to inspect it.</p>}
          <small>AI suggestions change the choreography plan, not an individual dancer's recorded performance.</small>
        </div>
      </div>
      <div className="sync-timeline-wrap">
        <svg className="sync-timeline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-label="Clickable synchronization score over time" onClick={(event) => {
          const bounds = event.currentTarget.getBoundingClientRect();
          seekReview(((event.clientX - bounds.left) / bounds.width) * duration);
        }}>
          <line x1="0" x2={width} y1={height / 2} y2={height / 2} />
          <polyline points={points} />
          {diagnosis.events.filter((event) => event.time >= 0).map((event, index) => <circle
            key={`${event.time}-${index}`}
            className={`event-marker ${event.severity}`}
            cx={(event.time / duration) * width}
            cy={12 + (index % 2) * 12}
            r="5"
            onClick={(click) => { click.stopPropagation(); seekReview(event.time, event); }}
          />)}
          <line className="review-playhead" x1={(reviewTime / duration) * width} x2={(reviewTime / duration) * width} y1="0" y2={height} />
        </svg>
        <span>Click the graph or a warning marker to seek the rehearsal video.</span>
      </div>
      <div className="dancer-metrics">
        {diagnosis.dancers.map((dancer) => (
          <div key={dancer.dancer_id}>
            <strong>{dancer.dancer_id}</strong><b>{dancer.synchronization_score.toFixed(0)}</b>
            <span>{dancer.mean_timing_offset_ms == null ? "No beat estimate" : `${Math.abs(dancer.mean_timing_offset_ms).toFixed(0)} ms ${dancer.mean_timing_offset_ms >= 0 ? "late" : "early"}`}</span>
            <span>{dancer.mean_pose_deviation_deg.toFixed(1)}° pose deviation</span>
          </div>
        ))}
      </div>
      {diagnosis.events.length > 0 && <div className="sync-events">{diagnosis.events.slice(0, 8).map((event, index) => <button key={`${event.time}-${index}`} className={`${event.severity} ${selectedEvent === event ? "selected" : ""}`} onClick={() => seekReview(event.time, event)}><AlertTriangle size={13} /><b>{event.time.toFixed(1)}s</b><span>{event.message}</span></button>)}</div>}
      <p className="diagnosis-limit">Camera-based estimate: temporary identities, joint-angle agreement, motion peaks, and image-space spacing. It is not biometric identification or stage calibration.</p>
    </section>
  );
}

function currentFormation(formations: Formation[], time: number) {
  let current = formations[0];
  for (const f of formations) if (time >= f.start) current = f;
  return current;
}
const cloneResponse = (value: PlanResponse): PlanResponse =>
  JSON.parse(JSON.stringify(value)) as PlanResponse;

function stagePositions(
  formations: Formation[],
  time: number,
): Record<string, Point> {
  if (!formations.length) return {};
  let nextIndex = formations.findIndex((f) => f.start > time);
  if (nextIndex < 0) return formations.at(-1)!.positions;
  if (nextIndex === 0) return formations[0].positions;
  const a = formations[nextIndex - 1],
    b = formations[nextIndex],
    raw = (time - a.start) / (b.start - a.start),
    t = raw * raw * (3 - 2 * raw);
  const result: Record<string, Point> = {};
  Object.keys(a.positions).forEach((id) => {
    const p = a.positions[id],
      q = b.positions[id] || p;
    result[id] = { x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t };
  });
  return result;
}
function Stage({
  result,
  constraints,
  time,
  motion,
  motionCatalog,
  libraryClips,
  editing,
  edited,
  validatingEdit,
  onToggleEditing,
  onMoveDancer,
  onCommitEdit,
  onResetEdits,
  onSeek,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onUpdateFormation,
  onChangeGeometry,
  onUpdateBoundary,
  onExportJson,
  onExportSheet,
}: {
  result: PlanResponse;
  constraints: Constraints;
  time: number;
  motion: MotionAnalysis | null;
  motionCatalog: MotionClipSummary[];
  libraryClips: Record<string, MotionClip>;
  editing: boolean;
  edited: boolean;
  validatingEdit: boolean;
  onToggleEditing: () => void;
  onMoveDancer: (formationId: string, dancerId: string, point: Point) => void;
  onCommitEdit: () => void;
  onResetEdits: () => void;
  onSeek: (time: number) => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onUpdateFormation: (formationId: string, values: Partial<Formation>) => void;
  onChangeGeometry: (formationId: string, kind: string) => void;
  onUpdateBoundary: (formationId: string, boundary: number) => void;
  onExportJson: () => void;
  onExportSheet: () => void;
}) {
  const stageRef = useRef<HTMLDivElement>(null),
    [dragging, setDragging] = useState<string | null>(null),
    f = currentFormation(result.plan.formations, time),
    formationIndex = result.plan.formations.findIndex((item) => item.id === f?.id),
    nextFormation = formationIndex >= 0 ? result.plan.formations[formationIndex + 1] : undefined,
    positions = editing && f ? f.positions : stagePositions(result.plan.formations, time),
    libraryMotion = f?.motion_clip_id
      ? libraryClips[f.motion_clip_id] || null
      : null,
    activeMotion = motion || libraryMotion,
    motionTime = Math.max(0, time - (f?.start || 0)) * (f?.motion_speed || 1),
    motionLabel = motion
      ? "uploaded reference"
      : libraryMotion
        ? `${libraryMotion.genre} · ${libraryMotion.label_scope === "family_reference" ? "curated adavu" : "AIST++"}`
        : "procedural body motion";
  const updateDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!editing || !dragging || !f || !stageRef.current) return;
    const rect = stageRef.current.getBoundingClientRect();
    const x = Math.min(constraints.stage_width - 0.25, Math.max(0.25, ((event.clientX - rect.left) / rect.width) * constraints.stage_width));
    const y = Math.min(constraints.stage_depth - 0.25, Math.max(0.25, ((event.clientY - rect.top) / rect.height) * constraints.stage_depth));
    onMoveDancer(f.id, dragging, { x: +x.toFixed(3), y: +y.toFixed(3) });
  };
  const finishDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    updateDrag(event);
    setDragging(null);
    onCommitEdit();
  };
  return (
    <section className="stage-card panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">LIVE STAGE</span>
          <h2>{f?.name || "Awaiting plan"}</h2>
        </div>
        <div className="stage-edit-actions">
          <button onClick={onUndo} disabled={!canUndo} title="Undo edit"><Undo2 size={13} /></button>
          <button onClick={onRedo} disabled={!canRedo} title="Redo edit"><Redo2 size={13} /></button>
          <button onClick={onExportJson} title="Download editable JSON"><Download size={13} /> JSON</button>
          <button onClick={onExportSheet} title="Download printable rehearsal sheet"><Download size={13} /> Sheet</button>
          {edited && (
            <button onClick={onResetEdits} title="Restore the generated plan">
              <RotateCcw size={13} /> Reset
            </button>
          )}
          <button className={editing ? "active" : ""} onClick={onToggleEditing}>
            <Pencil size={13} /> {editing ? "Finish editing" : "Edit positions"}
          </button>
          <span className="timecode">{time.toFixed(1)}s</span>
        </div>
      </div>
      <div className="formation-tabs">
        {result.plan.formations.map((formation) => (
          <button key={formation.id} className={formation.id === f?.id ? "active" : ""} onClick={() => onSeek(formation.start + 0.001)}>
            {formation.id} · {formation.name}
          </button>
        ))}
      </div>
      {editing && (
        <>
          <div className="edit-hint">
            Drag a numbered dancer or edit the active phrase below. {validatingEdit ? "Checking spacing and paths…" : "Every committed change revalidates the complete plan."}
          </div>
          {f && (
            <div className="phrase-editor">
              <label>Name<input value={f.name} onChange={(event) => onUpdateFormation(f.id, { name: event.target.value })} onBlur={onCommitEdit} /></label>
              <label>Formation<select value={f.geometry_kind || ""} onChange={(event) => onChangeGeometry(f.id, event.target.value)}><option value="" disabled>Custom positions</option>{formationChoices.map((kind) => <option key={kind} value={kind}>{kind.replaceAll("_", " ")}</option>)}</select></label>
              <label>Motion<select value={f.motion_clip_id || ""} onChange={(event) => { onUpdateFormation(f.id, { motion_clip_id: event.target.value || null }); onCommitEdit(); }}><option value="">Procedural</option>{motionCatalog.map((clip) => <option key={clip.id} value={clip.id}>{clip.genre}</option>)}</select></label>
              <label>Behavior<select value={f.movement} onChange={(event) => { onUpdateFormation(f.id, { movement: event.target.value }); onCommitEdit(); }}>{["unison", "canon", "ripple", "travel", "turn", "level_change", "hold"].map((movement) => <option key={movement} value={movement}>{movement.replaceAll("_", " ")}</option>)}</select></label>
              <label>Speed <b>{f.motion_speed.toFixed(2)}×</b><input type="range" min="0.5" max="2" step="0.05" value={f.motion_speed} onChange={(event) => onUpdateFormation(f.id, { motion_speed: +event.target.value })} onPointerUp={onCommitEdit} /></label>
              <label className="check-edit"><input type="checkbox" checked={f.mirror_motion} onChange={(event) => { onUpdateFormation(f.id, { mirror_motion: event.target.checked }); onCommitEdit(); }} /> Mirror alternate dancers</label>
              {nextFormation && (
                <label>Next transition <b>{f.end.toFixed(1)}s</b><input type="range" min={f.start + 1} max={nextFormation.end - 1} step="0.25" value={f.end} onChange={(event) => onUpdateBoundary(f.id, +event.target.value)} onPointerUp={onCommitEdit} /></label>
              )}
            </div>
          )}
        </>
      )}
      <div
        ref={stageRef}
        className="stage"
        style={{
          aspectRatio: `${constraints.stage_width}/${constraints.stage_depth}`,
        }}
        onPointerMove={updateDrag}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
      >
        <div className="stage-grid" />
        <span className="upstage">UPSTAGE</span>
        <span className="audience">AUDIENCE</span>
        {Object.entries(positions).map(([id, p], i) => (
          <DancerGlyph
            key={id}
            id={id}
            position={p}
            stageWidth={constraints.stage_width}
            stageDepth={constraints.stage_depth}
            color={colors[i % colors.length]}
            time={motionTime}
            motion={activeMotion}
            movement={f?.movement || "unison"}
            index={i}
            phaseOffset={f?.phase_offset || 0}
            mirror={!!f?.mirror_motion && i % 2 === 1}
            motionLabel={motionLabel}
            editable={editing}
            onPointerDown={(event) => {
              if (!editing) return;
              event.preventDefault();
              event.currentTarget.setPointerCapture(event.pointerId);
              setDragging(id);
            }}
          />
        ))}
      </div>
      <div className="movement">
        <Sparkles size={16} />
        <div>
          <strong>{f?.movement?.replace("_", " ")}</strong>
          <p>{f?.movement_description}</p>
        </div>
        <span className="pose-mode">{motionLabel}</span>
      </div>
    </section>
  );
}

function Control({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="control">
      <span>
        {label}
        <b>{value}</b>
      </span>
      <input
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(+e.target.value)}
      />
    </label>
  );
}

export default function App() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null),
    [motion, setMotion] = useState<MotionAnalysis | null>(null),
    [ensemble, setEnsemble] = useState<EnsembleAnalysis | null>(null),
    [rehearsalVideoUrl, setRehearsalVideoUrl] = useState(""),
    [motionCatalog, setMotionCatalog] = useState<MotionClipSummary[]>([]),
    [libraryClips, setLibraryClips] = useState<Record<string, MotionClip>>({}),
    [audioId, setAudioId] = useState(""),
    [result, setResult] = useState<PlanResponse | null>(null),
    [constraints, setConstraints] = useState(initialConstraints),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [time, setTime] = useState(0),
    [playing, setPlaying] = useState(false),
    [editing, setEditing] = useState(false),
    [edited, setEdited] = useState(false),
    [validatingEdit, setValidatingEdit] = useState(false);
  const [revisionPrompt, setRevisionPrompt] = useState(""),
    [revisionProposal, setRevisionProposal] = useState<PlanRevisionResponse | null>(null),
    [revisionBusy, setRevisionBusy] = useState(false);
  const audio = useRef<HTMLAudioElement>(null),
    fileInput = useRef<HTMLInputElement>(null),
    videoInput = useRef<HTMLInputElement>(null),
    rehearsalInput = useRef<HTMLInputElement>(null),
    rehearsalObjectUrl = useRef(""),
    resultRef = useRef<PlanResponse | null>(null),
    generatedBaseline = useRef<PlanResponse | null>(null),
    historyRef = useRef<PlanResponse[]>([]),
    historyIndexRef = useRef(-1);
  const [, setHistoryVersion] = useState(0);
  useEffect(() => () => {
    if (rehearsalObjectUrl.current) URL.revokeObjectURL(rehearsalObjectUrl.current);
  }, []);
  useEffect(() => {
    let frame = 0;
    const tick = () => {
      if (audio.current) setTime(audio.current.currentTime);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/motions`)
      .then((r) =>
        r.ok ? r.json() : Promise.reject(Error("Motion library unavailable")),
      )
      .then((data) => {
        if (!cancelled) setMotionCatalog(data.clips || []);
      })
      .catch(() => {
        if (!cancelled) setMotionCatalog([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  useEffect(() => {
    const ids = [
      ...new Set(
        (result?.plan.formations || [])
          .map((f) => f.motion_clip_id)
          .filter((id): id is string => !!id),
      ),
    ];
    const missing = ids.filter((id) => !libraryClips[id]);
    if (!missing.length) return;
    let cancelled = false;
    Promise.all(
      missing.map((id) =>
        fetch(`${API}/motions/${encodeURIComponent(id)}`).then((r) => {
          if (!r.ok) throw Error(`Motion clip ${id} unavailable`);
          return r.json() as Promise<MotionClip>;
        }),
      ),
    )
      .then((clips) => {
        if (!cancelled)
          setLibraryClips((current) => ({
            ...current,
            ...Object.fromEntries(clips.map((clip) => [clip.id, clip])),
          }));
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [result, libraryClips]);
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      void loadDemo();
    }
  }, []);
  const patch = <K extends keyof Constraints>(key: K, value: Constraints[K]) =>
    setConstraints((x) => ({ ...x, [key]: value }));
  const motionOptions = useMemo(
    () => ({
      adavus: [...new Set(motionCatalog.filter((clip) => clip.label_scope === "family_reference").map((clip) => clip.genre))],
      genres: [...new Set(motionCatalog.filter((clip) => clip.label_scope === "genre").map((clip) => clip.genre))],
    }),
    [motionCatalog],
  );
  const toggleMotion = (genre: string) =>
    patch(
      "preferred_motion_genres",
      constraints.preferred_motion_genres.includes(genre)
        ? constraints.preferred_motion_genres.filter((item) => item !== genre)
        : [...constraints.preferred_motion_genres, genre],
    );
  const installGeneratedResult = (next: PlanResponse) => {
    const copy = cloneResponse(next);
    generatedBaseline.current = cloneResponse(next);
    resultRef.current = copy;
    setResult(copy);
    historyRef.current = [cloneResponse(copy)];
    historyIndexRef.current = 0;
    setHistoryVersion((version) => version + 1);
    setEdited(false);
    setEditing(false);
  };
  async function upload(file?: File) {
    if (!file) return;
    setBusy("Analyzing audio");
    setError("");
    resultRef.current = null;
    generatedBaseline.current = null;
    historyRef.current = [];
    historyIndexRef.current = -1;
    setResult(null);
    setEdited(false);
    setEditing(false);
    setEnsemble(null);
    if (rehearsalObjectUrl.current) URL.revokeObjectURL(rehearsalObjectUrl.current);
    rehearsalObjectUrl.current = "";
    setRehearsalVideoUrl("");
    const body = new FormData();
    body.append("file", file);
    try {
      const r = await fetch(`${API}/analyze`, { method: "POST", body });
      const data = await r.json();
      if (!r.ok) throw Error(data.detail || "Analysis failed");
      setAnalysis(data.analysis);
      setAudioId(data.audio_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
  async function uploadMotion(file?: File) {
    if (!file) return;
    setBusy("Extracting body pose");
    setError("");
    const body = new FormData();
    body.append("file", file);
    try {
      const r = await fetch(`${API}/analyze-motion`, { method: "POST", body });
      const data = await r.json();
      if (!r.ok) throw Error(data.detail || "Pose analysis failed");
      setMotion(data.motion_analysis);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
  async function diagnoseRehearsal(file?: File) {
    if (!file) return;
    setBusy("Diagnosing team rehearsal");
    setError("");
    const body = new FormData();
    body.append("file", file);
    body.append("expected_dancers", String(constraints.dancer_count));
    body.append("beat_times", JSON.stringify(analysis?.beat_times || []));
    try {
      const response = await fetch(`${API}/analyze-ensemble`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Rehearsal diagnosis failed");
      setEnsemble(data.ensemble_analysis);
      if (rehearsalObjectUrl.current) URL.revokeObjectURL(rehearsalObjectUrl.current);
      rehearsalObjectUrl.current = URL.createObjectURL(file);
      setRehearsalVideoUrl(rehearsalObjectUrl.current);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy("");
    }
  }
  async function loadDemo() {
    setBusy("Loading cached demo");
    setError("");
    try {
      const r = await fetch(`${API}/demo`);
      const data = await r.json();
      if (!r.ok) throw Error(data.detail || "Demo failed");
      setAnalysis(data.analysis);
      setAudioId(data.audio_id);
      installGeneratedResult(data.result);
      if (new URLSearchParams(window.location.search).get("edit") === "1") {
        setEditing(true);
      }
      setMotion(null);
      setEnsemble(null);
      if (rehearsalObjectUrl.current) URL.revokeObjectURL(rehearsalObjectUrl.current);
      rehearsalObjectUrl.current = "";
      setRehearsalVideoUrl("");
      setConstraints(initialConstraints);
      setTime(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
  async function generate() {
    if (!analysis) return;
    setBusy(result ? "Replanning choreography" : "Agent planning");
    setError("");
    try {
      const r = await fetch(`${API}/plan`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          analysis,
          constraints,
          previous_plan: result?.plan || null,
          motion_analysis: motion,
        }),
      });
      const data = await r.json();
      if (!r.ok) throw Error(data.detail || "Planning failed");
      installGeneratedResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
  function toggle() {
    if (!audio.current) return;
    if (audio.current.paused) {
      audio.current.play();
      setPlaying(true);
    } else {
      audio.current.pause();
      setPlaying(false);
    }
  }
  function seekTo(nextTime: number) {
    if (audio.current) audio.current.currentTime = nextTime;
    setTime(nextTime);
  }
  function toggleEditing() {
    if (audio.current && !audio.current.paused) audio.current.pause();
    setPlaying(false);
    setEditing((current) => !current);
  }
  function moveDancer(formationId: string, dancerId: string, point: Point) {
    const current = resultRef.current;
    if (!current) return;
    const next = cloneResponse(current);
    const formation = next.plan.formations.find((item) => item.id === formationId);
    if (!formation) return;
    formation.positions[dancerId] = point;
    resultRef.current = next;
    setResult(next);
    setEdited(true);
  }
  async function validateEdits() {
    const current = resultRef.current;
    if (!current) return;
    const submittedPlan = JSON.stringify(current.plan);
    setValidatingEdit(true);
    try {
      const response = await fetch(`${API}/validate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ plan: current.plan, constraints }),
      });
      const validation = await response.json();
      if (!response.ok) throw Error(validation.detail || "Validation failed");
      const latest = resultRef.current;
      if (!latest || JSON.stringify(latest.plan) !== submittedPlan) return;
      const changes = latest.changes.includes("Stage positions manually edited by choreographer")
        ? latest.changes
        : [...latest.changes, "Stage positions manually edited by choreographer"];
      const next = { ...latest, validation, changes };
      resultRef.current = next;
      setResult(next);
      const retained = historyRef.current.slice(0, historyIndexRef.current + 1);
      if (!retained.length || JSON.stringify(retained.at(-1)?.plan) !== JSON.stringify(next.plan)) {
        retained.push(cloneResponse(next));
        historyRef.current = retained;
        historyIndexRef.current = retained.length - 1;
        setHistoryVersion((version) => version + 1);
      } else {
        retained[retained.length - 1] = cloneResponse(next);
        historyRef.current = retained;
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setValidatingEdit(false);
    }
  }
  function resetEdits() {
    if (!generatedBaseline.current) return;
    const restored = cloneResponse(generatedBaseline.current);
    resultRef.current = restored;
    setResult(restored);
    setEdited(false);
    historyRef.current = [...historyRef.current.slice(0, historyIndexRef.current + 1), cloneResponse(restored)];
    historyIndexRef.current = historyRef.current.length - 1;
    setHistoryVersion((version) => version + 1);
  }
  function restoreHistory(index: number) {
    const snapshot = historyRef.current[index];
    if (!snapshot) return;
    historyIndexRef.current = index;
    const restored = cloneResponse(snapshot);
    resultRef.current = restored;
    setResult(restored);
    setEdited(JSON.stringify(restored.plan) !== JSON.stringify(generatedBaseline.current?.plan));
    setHistoryVersion((version) => version + 1);
  }
  function updateFormation(formationId: string, values: Partial<Formation>) {
    const current = resultRef.current;
    if (!current) return;
    const next = cloneResponse(current);
    const formation = next.plan.formations.find((item) => item.id === formationId);
    if (!formation) return;
    Object.assign(formation, values);
    resultRef.current = next;
    setResult(next);
    setEdited(true);
  }
  async function changeGeometry(formationId: string, kind: string) {
    const current = resultRef.current;
    if (!current) return;
    const index = current.plan.formations.findIndex((item) => item.id === formationId);
    const previousPositions = index > 0 ? current.plan.formations[index - 1].positions : null;
    setValidatingEdit(true);
    try {
      const response = await fetch(`${API}/formations/generate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ kind, constraints, previous_positions: previousPositions }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "Formation generation failed");
      updateFormation(formationId, {
        positions: data.positions,
        geometry_kind: kind,
        name: kind.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()),
      });
      await validateEdits();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setValidatingEdit(false);
    }
  }
  function updateBoundary(formationId: string, boundary: number) {
    const current = resultRef.current;
    if (!current) return;
    const index = current.plan.formations.findIndex((item) => item.id === formationId);
    if (index < 0 || index >= current.plan.formations.length - 1) return;
    const next = cloneResponse(current);
    next.plan.formations[index].end = boundary;
    next.plan.formations[index + 1].start = boundary;
    resultRef.current = next;
    setResult(next);
    setEdited(true);
  }
  function downloadFile(filename: string, type: string, content: string) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
  function exportPlanJson() {
    if (!resultRef.current) return;
    downloadFile("form-choreography-plan.json", "application/json", JSON.stringify({ constraints, ...resultRef.current }, null, 2));
  }
  function exportRehearsalSheet() {
    const current = resultRef.current;
    if (!current) return;
    const escape = (value: unknown) => String(value ?? "").replace(/[&<>\"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character] || character);
    const rows = current.plan.formations.map((item) => {
      const motionName = motionCatalog.find((clip) => clip.id === item.motion_clip_id)?.genre || "Procedural";
      const positions = Object.entries(item.positions).map(([id, point]) => `${id} (${point.x.toFixed(1)}, ${point.y.toFixed(1)})`).join(", ");
      return `<tr><td>${escape(item.id)}</td><td>${escape(`${item.start.toFixed(1)}–${item.end.toFixed(1)}s`)}</td><td>${escape(item.name)}</td><td>${escape(motionName)}</td><td>${escape(item.movement.replaceAll("_", " "))}</td><td>${escape(positions)}</td></tr>`;
    }).join("");
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>FORM rehearsal sheet</title><style>body{font:14px Arial;margin:32px;color:#182018}h1{margin-bottom:4px}p{color:#586158}table{width:100%;border-collapse:collapse;margin-top:24px}th,td{border:1px solid #abb4ab;padding:8px;text-align:left;vertical-align:top}th{background:#e8ff5b}td:last-child{font-size:11px}</style></head><body><h1>${escape(current.plan.title)}</h1><p>${escape(current.plan.creative_direction)}</p><p>Stage: ${constraints.stage_width}m × ${constraints.stage_depth}m · ${constraints.dancer_count} dancers · Minimum spacing ${constraints.min_spacing}m</p><table><thead><tr><th>Phrase</th><th>Time</th><th>Formation</th><th>Motion</th><th>Behavior</th><th>Dancer positions (m)</th></tr></thead><tbody>${rows}</tbody></table></body></html>`;
    downloadFile("form-rehearsal-sheet.html", "text/html", html);
  }
  function applyClassicalPreset() {
    setConstraints((current) => ({
      ...current,
      mood: "Precise Kalakshetra-style Bharatanatyam ensemble with grounded posture, clean symmetry, clear eight-count accents, and synchronized finishes.",
      preferred_formations: ["line", "v", "semicircle", "diamond", "two_rows"],
      preferred_motion_genres: ["Thattadavu", "Nattadavu", "Kudithu Mettu"],
      motion_selection_mode: "palette",
    }));
  }
  function applyMixedPreset() {
    setConstraints((current) => ({
      ...current,
      mood: "A collaborative fusion that keeps each movement vocabulary recognizable, using sharp ensemble accents, contrasting group textures, and a confident unison finish.",
      preferred_formations: ["staggered", "diamond", "cross", "two_rows", "circle"],
      preferred_motion_genres: ["Thattadavu", "Middle Hip-Hop", "House", "Nattadavu"],
      motion_selection_mode: "palette",
    }));
  }
  async function proposeRevision(instruction: string) {
    const current = resultRef.current;
    if (!analysis || !current || instruction.trim().length < 3) return;
    setRevisionBusy(true);
    setRevisionProposal(null);
    setError("");
    try {
      const response = await fetch(`${API}/revise`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ analysis, constraints, current_plan: current.plan, instruction: instruction.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.detail || "The co-director could not propose a revision");
      setRevisionProposal(data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setRevisionBusy(false);
    }
  }
  function askCoDirector() {
    void proposeRevision(revisionPrompt);
  }
  function askAIAboutIssue(event: EnsembleSyncEvent) {
    const current = resultRef.current;
    if (!current) {
      setError("Generate a choreography plan before asking the AI co-director to adapt it to a rehearsal issue.");
      return;
    }
    const phrase = currentFormation(current.plan.formations, Math.min(event.time, analysis?.duration || event.time));
    const instruction = `The rehearsal diagnosis flagged this ${event.severity} ${event.kind} issue at ${event.time.toFixed(1)} seconds${event.dancer_id ? ` for ${event.dancer_id}` : ""}: "${event.message}" This occurs during ${phrase.id}, "${phrase.name}" (${phrase.start.toFixed(1)}-${phrase.end.toFixed(1)}s). Propose the smallest choreography adjustment that could make this passage easier to synchronize while preserving the rest of the plan. Treat the camera diagnosis as uncertain evidence, not ground truth.`;
    setRevisionPrompt(instruction);
    setRevisionProposal(null);
    requestAnimationFrame(() => document.getElementById("ai-co-director")?.scrollIntoView({ behavior: "smooth", block: "center" }));
    void proposeRevision(instruction);
  }
  function acceptRevision() {
    const current = resultRef.current;
    if (!current || !revisionProposal?.validation.valid) return;
    const next: PlanResponse = {
      ...current,
      plan: revisionProposal.revised_plan,
      validation: revisionProposal.validation,
      attempts: revisionProposal.attempts,
      latency_ms: revisionProposal.latency_ms,
      execution_mode: "live_agent",
      changes: revisionProposal.changes,
      decision_log: [
        ...current.decision_log,
        { attempt: revisionProposal.attempts, phase: "CO-DIRECT", message: revisionProposal.summary, validation: revisionProposal.validation },
      ],
    };
    resultRef.current = next;
    setResult(next);
    setEdited(true);
    const retained = historyRef.current.slice(0, historyIndexRef.current + 1);
    retained.push(cloneResponse(next));
    historyRef.current = retained;
    historyIndexRef.current = retained.length - 1;
    setHistoryVersion((version) => version + 1);
    setRevisionProposal(null);
    setRevisionPrompt("");
  }
  const formation = result
    ? currentFormation(result.plan.formations, time)
    : null;
  return (
    <main>
      <header>
        <div className="brand">
          <div className="mark">F</div>
          <div>
            <h1>FORM</h1>
            <span>AI CHOREOGRAPHY ARCHITECT</span>
          </div>
        </div>
        <div className="status">
          <i />
          <span>STUDIO ONLINE</span>
        </div>
      </header>
      <div className="workspace">
        <aside className="sidebar panel">
          <div className="panel-title">
            <span>PROJECT INPUTS</span>
            <em>01</em>
          </div>
          <button className="upload" onClick={() => fileInput.current?.click()}>
            <Upload size={21} />
            <strong>{analysis ? "Replace audio" : "Drop music excerpt"}</strong>
            <span>MP3 or WAV · 20–45 sec</span>
          </button>
          <input
            hidden
            ref={fileInput}
            type="file"
            accept=".mp3,.wav,audio/*"
            onChange={(e) => upload(e.target.files?.[0])}
          />
          <button className="demo-link" disabled={!!busy} onClick={loadDemo}>
            No network? Load cached studio demo
          </button>
          {analysis && (
            <div className="audio-summary">
              <Volume2 size={17} />
              <div>
                <strong>{analysis.filename}</strong>
                <span>
                  {analysis.duration.toFixed(1)} sec ·{" "}
                  {analysis.tempo.toFixed(0)} BPM
                </span>
              </div>
            </div>
          )}
          <button
            className="motion-upload"
            disabled={!!busy}
            onClick={() => videoInput.current?.click()}
          >
            <ScanLine size={15} />
            {motion
              ? "Replace movement reference"
              : "Add movement reference video"}
          </button>
          <input
            hidden
            ref={videoInput}
            type="file"
            accept=".mp4,.mov,.webm,.avi,video/*"
            onChange={(e) => uploadMotion(e.target.files?.[0])}
          />
          {motion && (
            <div className="motion-summary">
              <strong>{motion.filename}</strong>
              <span>
                {Math.round(motion.pose_coverage * 100)}% pose coverage ·{" "}
                {motion.detected_frames} frames
              </span>
            </div>
          )}
          <button className="rehearsal-upload" disabled={!!busy} onClick={() => rehearsalInput.current?.click()}>
            <Users size={15} /> {ensemble ? "Replace team rehearsal" : "Diagnose team rehearsal video"}
          </button>
          <input hidden ref={rehearsalInput} type="file" accept=".mp4,.mov,.webm,.avi,video/*" onChange={(event) => diagnoseRehearsal(event.target.files?.[0])} />
          {ensemble && <div className="motion-summary ensemble-summary"><strong>{ensemble.filename}</strong><span>{ensemble.tracked_dancers} track IDs · {ensemble.mean_detected_dancers.toFixed(1)}/{ensemble.expected_dancers} average visible · {ensemble.overall_synchronization_score.toFixed(0)}/100 provisional synchronization</span></div>}
          <div className="divider" />
          <div className="section-heading">
            <Users size={15} /> Ensemble
          </div>
          <Control
            label="Dancers"
            value={constraints.dancer_count}
            min={3}
            max={10}
            step={1}
            onChange={(n) => patch("dancer_count", n)}
          />
          <div className="twocol">
            <Control
              label="Width (m)"
              value={constraints.stage_width}
              min={6}
              max={20}
              step={0.5}
              onChange={(n) => patch("stage_width", n)}
            />
            <Control
              label="Depth (m)"
              value={constraints.stage_depth}
              min={4}
              max={14}
              step={0.5}
              onChange={(n) => patch("stage_depth", n)}
            />
          </div>
          <Control
            label="Minimum spacing (m)"
            value={constraints.min_spacing}
            min={0.5}
            max={3}
            step={0.1}
            onChange={(n) => patch("min_spacing", n)}
          />
          <div className="section-heading">
            <Sparkles size={15} /> Creative direction
          </div>
          <textarea
            value={constraints.mood}
            onChange={(e) => patch("mood", e.target.value)}
          />
          <div className="preset-row">
            <button onClick={applyClassicalPreset}>Classical demo preset</button>
            <button onClick={applyMixedPreset}>Mixed-style demo preset</button>
          </div>
          <div className="chips">
            {formationChoices.map((x) => (
              <button
                key={x}
                className={
                  constraints.preferred_formations.includes(x) ? "active" : ""
                }
                onClick={() =>
                  patch(
                    "preferred_formations",
                    constraints.preferred_formations.includes(x)
                      ? constraints.preferred_formations.filter((y) => y !== x)
                      : [...constraints.preferred_formations, x],
                  )
                }
              >
                {x.replace("_", " ")}
              </button>
            ))}
          </div>
          {motionCatalog.length > 0 && (
            <>
              <div className="section-heading">
                <Activity size={15} /> Motion palette
              </div>
              <button
                className={`palette-any ${constraints.preferred_motion_genres.length === 0 ? "active" : ""}`}
                onClick={() => patch("preferred_motion_genres", [])}
              >
                Agent chooses any
              </button>
              <div className="palette-mode" role="group" aria-label="Motion selection behavior">
                <button
                  className={constraints.motion_selection_mode === "palette" ? "active" : ""}
                  onClick={() => patch("motion_selection_mode", "palette")}
                >
                  Palette · AI arranges
                </button>
                <button
                  className={constraints.motion_selection_mode === "sequence" ? "active" : ""}
                  onClick={() => patch("motion_selection_mode", "sequence")}
                >
                  Ordered sequence
                </button>
              </div>
              <span className="palette-label">Adavu families</span>
              <div className="chips motion-chips">
                {motionOptions.adavus.map((genre) => (
                  <button key={genre} className={constraints.preferred_motion_genres.includes(genre) ? "active" : ""} onClick={() => toggleMotion(genre)}>
                    {genre}
                  </button>
                ))}
              </div>
              <span className="palette-label">Other dance genres</span>
              <div className="chips motion-chips">
                {motionOptions.genres.map((genre) => (
                  <button key={genre} className={constraints.preferred_motion_genres.includes(genre) ? "active" : ""} onClick={() => toggleMotion(genre)}>
                    {genre}
                  </button>
                ))}
              </div>
              {constraints.preferred_motion_genres.length > 0 && (
                <p className="palette-order">
                  {constraints.motion_selection_mode === "sequence"
                    ? `Sequence: ${constraints.preferred_motion_genres.join(" → ")}`
                    : `Include, AI chooses order: ${constraints.preferred_motion_genres.join(", ")}`}
                </p>
              )}
              <p className="library-note">
                {motionCatalog.length} attributed motion studies · curated adavu
                families are references, not classifier output
              </p>
            </>
          )}
          <button
            className="primary"
            disabled={!analysis || !!busy}
            onClick={generate}
          >
            {busy ? (
              <RefreshCw className="spin" size={18} />
            ) : result ? (
              <RefreshCw size={18} />
            ) : (
              <Sparkles size={18} />
            )}{" "}
            {busy ||
              (result ? "Replan with constraints" : "Generate choreography")}
            <ChevronRight size={18} />
          </button>
        </aside>
        <div className="content">
          {!analysis ? (
            <section className="empty panel">
              <div className="orb">
                <Activity />
              </div>
              <p className="eyebrow">MUSIC → SPACE → MOVEMENT</p>
              <h2>
                Architecture for bodies
                <br />
                in motion.
              </h2>
              <p>
                Upload a short music excerpt to reveal its measured pulse,
                energy, and change points—then let FORM build and validate the
                spatial score.
              </p>
              <button onClick={() => fileInput.current?.click()}>
                <Upload size={17} /> Choose audio
              </button>
            </section>
          ) : (
            <>
              <section className="analysis panel">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">MUSICAL INTELLIGENCE</span>
                    <h2>
                      {analysis.tempo} <small>BPM</small>
                    </h2>
                  </div>
                  <div className="metrics">
                    <div>
                      <b>{analysis.beat_times.length}</b>
                      <span>DETECTED BEATS</span>
                    </div>
                    <div>
                      <b>{analysis.sections.length}</b>
                      <span>HEURISTIC SECTIONS</span>
                    </div>
                  </div>
                </div>
                <Timeline
                  analysis={analysis}
                  time={time}
                  onSeek={(n) => {
                    seekTo(n);
                  }}
                />
                <div className="legend">
                  <span>
                    <i className="measured" />
                    Measured waveform + beats
                  </span>
                  <span>
                    <i className="heuristic" />
                    Heuristic energy/sections
                  </span>
                </div>
              </section>
              {ensemble && rehearsalVideoUrl && <EnsembleDiagnosis diagnosis={ensemble} videoUrl={rehearsalVideoUrl} onAskAI={askAIAboutIssue} />}
              <audio
                ref={audio}
                src={audioId ? `${API}/audio/${audioId}` : ""}
                onEnded={() => setPlaying(false)}
              />
              {result ? (
                <div className="stage-grid-layout">
                  <Stage
                    result={result}
                    constraints={constraints}
                    time={time}
                    motion={motion}
                    motionCatalog={motionCatalog}
                    libraryClips={libraryClips}
                    editing={editing}
                    edited={edited}
                    validatingEdit={validatingEdit}
                    onToggleEditing={toggleEditing}
                    onMoveDancer={moveDancer}
                    onCommitEdit={validateEdits}
                    onResetEdits={resetEdits}
                    onSeek={seekTo}
                    canUndo={historyIndexRef.current > 0}
                    canRedo={historyIndexRef.current >= 0 && historyIndexRef.current < historyRef.current.length - 1}
                    onUndo={() => restoreHistory(historyIndexRef.current - 1)}
                    onRedo={() => restoreHistory(historyIndexRef.current + 1)}
                    onUpdateFormation={updateFormation}
                    onChangeGeometry={changeGeometry}
                    onUpdateBoundary={updateBoundary}
                    onExportJson={exportPlanJson}
                    onExportSheet={exportRehearsalSheet}
                  />
                  <section className="inspector panel">
                    <div className="panel-title">
                      <span>AGENT TRACE</span>
                      <em>{result.attempts.toString().padStart(2, "0")}</em>
                    </div>
                    <div
                      className={`validation ${result.validation.valid ? "pass" : "fail"}`}
                    >
                      {result.validation.valid ? <Check /> : <AlertTriangle />}
                      <div>
                        <strong>
                          {result.validation.valid
                            ? "PLAN VALIDATED"
                            : "VALIDATION FAILED"}
                        </strong>
                        <span>
                          {result.validation.samples_checked} transition samples
                          checked
                        </span>
                      </div>
                    </div>
                    <span className={`mode ${result.execution_mode}`}>
                      {result.execution_mode.replace("_", " ")}
                    </span>
                    {edited && <span className="mode human_edit">human edited</span>}
                    <div className="trace">
                      {result.decision_log.map((x, i) => (
                        <div key={i}>
                          <i />
                          <span>{x.phase}</span>
                          <p>{x.message}</p>
                        </div>
                      ))}
                    </div>
                    {result.validation.issues.length > 0 && (
                      <div className="issues">
                        {result.validation.issues.map((x, i) => (
                          <p key={i}>
                            <AlertTriangle size={13} />
                            {x.message}
                          </p>
                        ))}
                      </div>
                    )}
                    {result.changes.length > 0 && (
                      <div className="changes">
                        <strong>WHAT CHANGED</strong>
                        {result.changes.map((x) => (
                          <p key={x}>+ {x}</p>
                        ))}
                      </div>
                    )}
                    <div className="rationale">
                      <strong>WHY THIS MOMENT</strong>
                      <p>{formation?.rationale}</p>
                    </div>
                    <div className="co-director" id="ai-co-director">
                      <strong>AI CO-DIRECTOR</strong>
                      <p>Describe a creative change. FORM proposes a validated revision; nothing changes until you accept it.</p>
                      <textarea value={revisionPrompt} onChange={(event) => setRevisionPrompt(event.target.value)} placeholder="Make the middle phrase more dramatic, keep D1 near center, and preserve the ending…" />
                      <button disabled={revisionBusy || revisionPrompt.trim().length < 3} onClick={askCoDirector}>{revisionBusy ? <RefreshCw className="spin" size={13} /> : <Sparkles size={13} />}{revisionBusy ? "Thinking and validating" : "Propose revision"}</button>
                      {revisionProposal && (
                        <div className={`revision-proposal ${revisionProposal.validation.valid ? "pass" : "fail"}`}>
                          <b>{revisionProposal.validation.valid ? "Validated proposal" : "Proposal remains invalid"}</b>
                          <span>{revisionProposal.attempts} agent attempt{revisionProposal.attempts === 1 ? "" : "s"} · {revisionProposal.validation.samples_checked} path samples</span>
                          {revisionProposal.changes.map((change) => <p key={change}>+ {change}</p>)}
                          {revisionProposal.validation.issues.map((issue) => <p key={`${issue.code}-${issue.formation_id}`}>! {issue.message}</p>)}
                          <div><button disabled={!revisionProposal.validation.valid} onClick={acceptRevision}>Accept revision</button><button onClick={() => setRevisionProposal(null)}>Discard</button></div>
                        </div>
                      )}
                    </div>
                  </section>
                </div>
              ) : (
                <section className="ready panel">
                  <Sparkles />
                  <div>
                    <strong>Analysis complete</strong>
                    <span>
                      Adjust the ensemble constraints, then ask FORM to create
                      the spatial score.
                    </span>
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>
      {analysis && (
        <footer>
          <button className="transport" onClick={toggle}>
            {playing ? <Pause /> : <Play fill="currentColor" />}
          </button>
          <span className="footer-time">
            {time.toFixed(1)} <i>/ {analysis.duration.toFixed(1)}s</i>
          </span>
          <div className="progress">
            <span style={{ width: `${(time / analysis.duration) * 100}%` }} />
          </div>
          <strong>{formation?.name || "Analysis ready"}</strong>
          <Clock3 size={15} />
        </footer>
      )}
      {error && (
        <div className="toast">
          <AlertTriangle />
          {error}
          <button onClick={() => setError("")}>×</button>
        </div>
      )}
    </main>
  );
}
