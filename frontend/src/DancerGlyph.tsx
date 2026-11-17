import type { MotionAnalysis, MotionClip, Point, PoseLandmark } from "./types";
import type { PointerEvent as ReactPointerEvent } from "react";

type PoseSequence = Pick<MotionAnalysis | MotionClip, "frames" | "duration">;

const BONES = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"],
  ["right_knee", "right_ankle"],
] as const;

function proceduralPose(
  time: number,
  movement: string,
  index: number,
): Record<string, PoseLandmark> {
  const phase =
      time * 3.1 +
      (movement === "canon" || movement === "ripple" ? index * 0.65 : 0),
    s = Math.sin(phase),
    c = Math.cos(phase * 0.8),
    level = movement === "level_change" ? Math.abs(s) * 8 : 0;
  const p = (x: number, y: number): PoseLandmark => ({
    x,
    y,
    z: 0,
    visibility: 1,
  });
  return {
    nose: p(30, 9 + level),
    left_shoulder: p(21, 24 + level),
    right_shoulder: p(39, 24 + level),
    left_elbow: p(13 - s * 7, 38 + level - c * 5),
    right_elbow: p(47 + s * 7, 38 + level + c * 5),
    left_wrist: p(8 - s * 10, 51 + level - c * 9),
    right_wrist: p(52 + s * 10, 51 + level + c * 9),
    left_hip: p(24, 49 + level),
    right_hip: p(36, 49 + level),
    left_knee: p(22 + s * 4, 68 + level),
    right_knee: p(38 - s * 4, 68 + level),
    left_ankle: p(19 + s * 7, 88),
    right_ankle: p(41 - s * 7, 88),
  };
}

function normalizedPose(
  motion: PoseSequence | null,
  time: number,
  index: number,
  movement: string,
  phaseOffset: number,
  mirror: boolean,
): Record<string, PoseLandmark> | null {
  if (!motion?.frames.length) return null;
  const phase =
      movement === "canon" || movement === "ripple"
        ? index * Math.max(phaseOffset, 0.16)
        : 0,
    cycle = (time + phase) % Math.max(0.1, motion.duration);
  const frame = motion.frames.reduce(
    (best, next) =>
      Math.abs(next.time - cycle) < Math.abs(best.time - cycle) ? next : best,
    motion.frames[0],
  );
  const visible = Object.values(frame.landmarks).filter(
    (p) => p.visibility >= 0.25,
  );
  if (visible.length < 8) return null;
  const minX = Math.min(...visible.map((p) => p.x)),
    maxX = Math.max(...visible.map((p) => p.x)),
    minY = Math.min(...visible.map((p) => p.y)),
    maxY = Math.max(...visible.map((p) => p.y));
  const width = Math.max(0.08, maxX - minX),
    height = Math.max(0.15, maxY - minY),
    scale = Math.min(48 / width, 78 / height);
  return Object.fromEntries(
    Object.entries(frame.landmarks).map(([name, p]) => [
      name,
      {
        ...p,
        x: 30 + (p.x - (minX + maxX) / 2) * scale * (mirror ? -1 : 1),
        y: 7 + (p.y - minY) * scale,
      },
    ]),
  );
}

export default function DancerGlyph({
  id,
  position,
  stageWidth,
  stageDepth,
  color,
  time,
  motion,
  movement,
  index,
  phaseOffset = 0,
  mirror = false,
  motionLabel = "reference pose",
  editable = false,
  onPointerDown,
}: {
  id: string;
  position: Point;
  stageWidth: number;
  stageDepth: number;
  color: string;
  time: number;
  motion: PoseSequence | null;
  movement: string;
  index: number;
  phaseOffset?: number;
  mirror?: boolean;
  motionLabel?: string;
  editable?: boolean;
  onPointerDown?: (event: ReactPointerEvent<HTMLDivElement>) => void;
}) {
  const pose =
      normalizedPose(motion, time, index, movement, phaseOffset, mirror) ||
      proceduralPose(time, movement, index),
    head = pose.nose;
  return (
    <div
      className={`dancer-body ${editable ? "editable" : ""}`}
      style={{
        left: `${(position.x / stageWidth) * 100}%`,
        top: `${(position.y / stageDepth) * 100}%`,
        color,
      }}
      title={`${id} · ${motion ? motionLabel : "procedural pose"}`}
      onPointerDown={onPointerDown}
    >
      <svg viewBox="0 0 60 96" aria-label={`${id} animated full-body skeleton`}>
        {BONES.map(([a, b]) =>
          pose[a] && pose[b] ? (
            <line
              key={`${a}-${b}`}
              x1={pose[a].x}
              y1={pose[a].y}
              x2={pose[b].x}
              y2={pose[b].y}
            />
          ) : null,
        )}
        {head && <circle cx={head.x} cy={head.y} r="5" />}
        {Object.entries(pose)
          .filter(([name]) => name !== "nose")
          .map(([name, p]) => (
            <circle key={name} cx={p.x} cy={p.y} r="1.8" className="joint" />
          ))}
      </svg>
      <span>{id.slice(1)}</span>
    </div>
  );
}
