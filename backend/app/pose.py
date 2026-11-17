from __future__ import annotations

import math
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from .models import MotionAnalysis, PoseFrame, PoseLandmark


MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "pose_landmarker_full.task"
JOINTS = {
    "nose": 0,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_heel": 29,
    "right_heel": 30,
    "left_foot": 31,
    "right_foot": 32,
}


def _distance(a: PoseLandmark, b: PoseLandmark) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def analyze_motion(path: Path, filename: str, target_fps: float = 6.0, max_seconds: float = 20.0) -> MotionAnalysis:
    if not MODEL_PATH.exists():
        raise RuntimeError("Pose model is not installed. Expected backend/models/pose_landmarker_full.task")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("Could not decode this video")
    source_fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    source_duration = total_frames / source_fps if total_frames > 0 else max_seconds
    duration = min(source_duration, max_seconds)
    frame_step = max(1, round(source_fps / target_fps))
    sampled_fps = source_fps / frame_step
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.45,
        min_pose_presence_confidence=0.45,
        min_tracking_confidence=0.45,
    )
    frames: list[PoseFrame] = []
    sampled = 0
    previous: dict[str, PoseLandmark] | None = None
    with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            time_seconds = frame_index / source_fps
            if time_seconds > max_seconds:
                break
            if frame_index % frame_step != 0:
                frame_index += 1
                continue
            sampled += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            result = landmarker.detect_for_video(mp_image, int(round(time_seconds * 1000)))
            if result.pose_landmarks:
                pose = result.pose_landmarks[0]
                selected = {
                    name: PoseLandmark(
                        x=round(float(pose[index].x), 5),
                        y=round(float(pose[index].y), 5),
                        z=round(float(pose[index].z), 5),
                        visibility=round(float(pose[index].visibility or 0.0), 4),
                    )
                    for name, index in JOINTS.items()
                }
                energy = 0.0
                if previous:
                    visible = [name for name in selected if selected[name].visibility >= 0.35 and previous[name].visibility >= 0.35]
                    energy = float(np.mean([_distance(selected[name], previous[name]) for name in visible])) if visible else 0.0
                frames.append(PoseFrame(time=round(time_seconds, 3), motion_energy=round(energy, 5), landmarks=selected))
                previous = selected
            frame_index += 1
    capture.release()
    energies = np.array([frame.motion_energy for frame in frames], dtype=float)
    positive = energies[energies > 0]
    threshold = float(np.quantile(positive, 0.75)) if len(positive) else 0.0
    high_motion = [frame.time for frame in frames if threshold > 0 and frame.motion_energy >= threshold]
    coverage = len(frames) / sampled if sampled else 0.0
    notes = [
        "MediaPipe Pose Landmarker estimates 33 body keypoints; FORM stores 17 joints needed for the skeletal preview.",
        "Motion energy is a heuristic mean landmark displacement between sampled frames, not a recognized dance step.",
        "The first 20 seconds are sampled locally at approximately 6 FPS; the source video is not sent to the language model.",
    ]
    if coverage < 0.5:
        notes.append("Pose coverage is low. Use a well-lit clip with one full body visible from head to feet.")
    return MotionAnalysis(
        filename=filename,
        duration=round(duration, 3),
        source_fps=round(source_fps, 2),
        sampled_fps=round(sampled_fps, 2),
        sampled_frames=sampled,
        detected_frames=len(frames),
        pose_coverage=round(coverage, 4),
        mean_motion_energy=round(float(np.mean(energies)) if len(energies) else 0.0, 5),
        high_motion_times=[round(value, 3) for value in high_motion[:20]],
        frames=frames,
        notes=notes,
    )
