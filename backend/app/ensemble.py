from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from .models import (
    EnsembleAnalysis,
    EnsembleDancerMetrics,
    EnsemblePoseFrame,
    EnsembleSyncEvent,
    EnsembleTimelinePoint,
    PoseLandmark,
)
from .pose import JOINTS, MODEL_PATH, _distance


ANGLE_TRIPLETS = [
    ("left_shoulder", "left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow", "right_wrist"),
    ("left_hip", "left_knee", "left_ankle"),
    ("right_hip", "right_knee", "right_ankle"),
    ("left_shoulder", "left_hip", "left_knee"),
    ("right_shoulder", "right_hip", "right_knee"),
]


def _center(landmarks: dict[str, PoseLandmark]) -> tuple[float, float]:
    hips = [landmarks["left_hip"], landmarks["right_hip"]]
    return (float(np.mean([p.x for p in hips])), float(np.mean([p.y for p in hips])))


def _angle(a: PoseLandmark, b: PoseLandmark, c: PoseLandmark) -> float:
    first = np.array([a.x - b.x, a.y - b.y], dtype=float)
    second = np.array([c.x - b.x, c.y - b.y], dtype=float)
    denominator = max(float(np.linalg.norm(first) * np.linalg.norm(second)), 1e-8)
    cosine = float(np.clip(np.dot(first, second) / denominator, -1, 1))
    return math.degrees(math.acos(cosine))


def _angles(landmarks: dict[str, PoseLandmark]) -> np.ndarray:
    return np.array([_angle(landmarks[a], landmarks[b], landmarks[c]) for a, b, c in ANGLE_TRIPLETS], dtype=float)


def _selected_pose(pose) -> dict[str, PoseLandmark]:
    return {
        name: PoseLandmark(
            x=round(float(pose[index].x), 5),
            y=round(float(pose[index].y), 5),
            z=round(float(pose[index].z), 5),
            visibility=round(float(pose[index].visibility or 0.0), 4),
        )
        for name, index in JOINTS.items()
    }


def _selected_crop_pose(pose, x0: int, width: int, frame_width: int) -> dict[str, PoseLandmark]:
    selected = _selected_pose(pose)
    return {
        name: point.model_copy(update={
            "x": round((x0 + point.x * width) / frame_width, 5),
            "z": round(point.z * width / frame_width, 5),
        })
        for name, point in selected.items()
    }


def analyze_ensemble(
    path: Path,
    filename: str,
    expected_dancers: int,
    beat_times: list[float] | None = None,
    target_fps: float = 6.0,
    max_seconds: float = 30.0,
) -> EnsembleAnalysis:
    if not MODEL_PATH.exists():
        raise RuntimeError("Pose model is not installed")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("Could not decode this rehearsal video")
    source_fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = min(total_frames / source_fps if total_frames > 0 else max_seconds, max_seconds)
    frame_step = max(1, round(source_fps / target_fps))
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=expected_dancers,
        min_pose_detection_confidence=0.35,
        min_pose_presence_confidence=0.35,
        min_tracking_confidence=0.35,
    )
    crop_options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.3,
        min_pose_presence_confidence=0.3,
        min_tracking_confidence=0.3,
    )
    tracks: dict[str, list[dict]] = defaultdict(list)
    last_centers: dict[str, tuple[float, float]] = {}
    last_landmarks: dict[str, dict[str, PoseLandmark]] = {}
    frame_records: list[dict] = []
    next_id = 1
    sampled = 0

    with (
        mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker,
        mp.tasks.vision.PoseLandmarker.create_from_options(crop_options) as crop_landmarker,
    ):
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            time_seconds = frame_index / source_fps
            if time_seconds > max_seconds:
                break
            if frame_index % frame_step:
                frame_index += 1
                continue
            sampled += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            result = landmarker.detect_for_video(image, int(round(time_seconds * 1000)))
            detections = [_selected_pose(pose) for pose in result.pose_landmarks]
            if len(detections) < expected_dancers:
                # Wide stage recordings often make each body too small for a
                # whole-frame detector. Overlapping full-height crops recover
                # separated dancers without pretending to identify faces.
                frame_height, frame_width = rgb.shape[:2]
                fraction = min(0.65, max(0.28, 2.2 / expected_dancers))
                window_width = round(frame_width * fraction)
                starts = np.linspace(0, max(0, frame_width - window_width), max(2, expected_dancers))
                crop_candidates = list(detections)
                for start in starts:
                    x0 = int(round(start))
                    crop = np.ascontiguousarray(rgb[:, x0:x0 + window_width])
                    crop_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=crop)
                    crop_result = crop_landmarker.detect(crop_image)
                    if not crop_result.pose_landmarks:
                        continue
                    candidate = _selected_crop_pose(crop_result.pose_landmarks[0], x0, window_width, frame_width)
                    candidate_center = _center(candidate)
                    if all(math.dist(candidate_center, _center(existing)) > 0.09 for existing in crop_candidates):
                        crop_candidates.append(candidate)
                if len(crop_candidates) > len(detections):
                    detections = crop_candidates[:expected_dancers]
            centers = [_center(pose) for pose in detections]
            assignments: dict[int, str] = {}
            if last_centers and centers:
                candidates = sorted(
                    (math.dist(center, previous), index, dancer_id)
                    for index, center in enumerate(centers)
                    for dancer_id, previous in last_centers.items()
                )
                used_detections: set[int] = set()
                used_tracks: set[str] = set()
                for distance, detection_index, dancer_id in candidates:
                    if distance > 0.32 or detection_index in used_detections or dancer_id in used_tracks:
                        continue
                    assignments[detection_index] = dancer_id
                    used_detections.add(detection_index)
                    used_tracks.add(dancer_id)
            for detection_index in sorted(range(len(detections)), key=lambda index: centers[index][0]):
                if detection_index not in assignments and next_id <= expected_dancers:
                    assignments[detection_index] = f"D{next_id}"
                    next_id += 1

            current: dict[str, dict] = {}
            for detection_index, dancer_id in assignments.items():
                pose = detections[detection_index]
                previous = last_landmarks.get(dancer_id)
                visible = [name for name in pose if previous and pose[name].visibility >= 0.3 and previous[name].visibility >= 0.3]
                energy = float(np.mean([_distance(pose[name], previous[name]) for name in visible])) if visible else 0.0
                record = {
                    "time": round(time_seconds, 3),
                    "center": centers[detection_index],
                    "landmarks": pose,
                    "angles": _angles(pose),
                    "energy": energy,
                }
                tracks[dancer_id].append(record)
                current[dancer_id] = record
                last_centers[dancer_id] = centers[detection_index]
                last_landmarks[dancer_id] = pose
            frame_records.append({"time": round(time_seconds, 3), "dancers": current})
            frame_index += 1
    capture.release()

    if not tracks:
        raise ValueError("No full-body dancers were detected. Use a well-lit, mostly front-facing rehearsal clip.")

    pose_deviations: dict[str, list[float]] = defaultdict(list)
    motion_deviations: dict[str, list[float]] = defaultdict(list)
    nearest_spacing: dict[str, list[float]] = defaultdict(list)
    timeline: list[EnsembleTimelinePoint] = []
    events: list[EnsembleSyncEvent] = []
    for frame in frame_records:
        dancers = frame["dancers"]
        if len(dancers) >= 2:
            ids = list(dancers)
            median_angles = np.median(np.stack([dancers[dancer_id]["angles"] for dancer_id in ids]), axis=0)
            energies = np.array([dancers[dancer_id]["energy"] for dancer_id in ids], dtype=float)
            median_energy = float(np.median(energies))
            frame_pose = []
            frame_motion = []
            for dancer_id in ids:
                pose_deviation = float(np.mean(np.abs(dancers[dancer_id]["angles"] - median_angles)))
                motion_deviation = min(1.0, abs(dancers[dancer_id]["energy"] - median_energy) / max(median_energy, 0.015))
                pose_deviations[dancer_id].append(pose_deviation)
                motion_deviations[dancer_id].append(motion_deviation)
                frame_pose.append(pose_deviation)
                frame_motion.append(motion_deviation)
                distances = [math.dist(dancers[dancer_id]["center"], dancers[other]["center"]) for other in ids if other != dancer_id]
                if distances:
                    nearest_spacing[dancer_id].append(min(distances))
            score = max(0.0, 100 - float(np.mean(frame_pose)) * 1.6 - float(np.mean(frame_motion)) * 35)
            timeline.append(EnsembleTimelinePoint(time=frame["time"], detected_dancers=len(ids), synchronization_score=round(score, 1)))
            if float(np.mean(frame_pose)) > 28:
                worst = ids[int(np.argmax(frame_pose))]
                events.append(EnsembleSyncEvent(time=frame["time"], dancer_id=worst, kind="pose", severity="warning", message=f"{worst} differs from the group pose by about {max(frame_pose):.0f}°.", value=round(max(frame_pose), 1)))
            centers = [dancers[dancer_id]["center"] for dancer_id in ids]
            closest = min(math.dist(centers[a], centers[b]) for a in range(len(centers)) for b in range(a + 1, len(centers)))
            if closest < 0.075:
                events.append(EnsembleSyncEvent(time=frame["time"], kind="spacing", severity="high", message="Two tracked dancers become unusually close in image space.", value=round(closest, 4)))
        else:
            timeline.append(EnsembleTimelinePoint(time=frame["time"], detected_dancers=len(dancers), synchronization_score=0.0))

    beat_times = [beat for beat in (beat_times or []) if 0 <= beat <= duration]
    dancer_metrics: list[EnsembleDancerMetrics] = []
    timing_scores = []
    for dancer_id in sorted(tracks, key=lambda value: int(value[1:])):
        records = tracks[dancer_id]
        offsets = []
        if beat_times:
            for beat in beat_times:
                nearby = [record for record in records if abs(record["time"] - beat) <= 0.3]
                if nearby:
                    peak = max(nearby, key=lambda record: record["energy"])
                    offsets.append((peak["time"] - beat) * 1000)
        mean_offset = float(np.mean(offsets)) if offsets else None
        timing_score = max(0.0, 100 - abs(mean_offset) * 0.28) if mean_offset is not None else None
        if timing_score is not None:
            timing_scores.append(timing_score)
        pose_deviation = float(np.mean(pose_deviations[dancer_id])) if pose_deviations[dancer_id] else 0.0
        motion_consistency = max(0.0, 100 - (float(np.mean(motion_deviations[dancer_id])) if motion_deviations[dancer_id] else 1.0) * 100)
        pose_score = max(0.0, 100 - pose_deviation * 2.0)
        component_scores = [pose_score, motion_consistency] + ([timing_score] if timing_score is not None else [])
        sync_score = float(np.mean(component_scores))
        coverage = len(records) / sampled if sampled else 0.0
        dancer_metrics.append(EnsembleDancerMetrics(
            dancer_id=dancer_id,
            coverage=round(coverage, 3),
            mean_timing_offset_ms=round(mean_offset, 1) if mean_offset is not None else None,
            mean_pose_deviation_deg=round(pose_deviation, 1),
            motion_consistency=round(motion_consistency, 1),
            synchronization_score=round(sync_score, 1),
        ))
        if mean_offset is not None and abs(mean_offset) > 150:
            direction = "late" if mean_offset > 0 else "early"
            events.append(EnsembleSyncEvent(time=0, dancer_id=dancer_id, kind="timing", severity="warning", message=f"{dancer_id} peaks average {abs(mean_offset):.0f} ms {direction} relative to detected beats.", value=round(mean_offset, 1)))
        if coverage < 0.5:
            events.append(EnsembleSyncEvent(time=0, dancer_id=dancer_id, kind="tracking", severity="warning", message=f"{dancer_id} has low tracking coverage; occlusion may affect the diagnosis.", value=round(coverage, 3)))

    if len(tracks) < expected_dancers:
        events.append(EnsembleSyncEvent(
            time=0,
            kind="tracking",
            severity="high",
            message=f"Detected {len(tracks)} of {expected_dancers} expected dancers. Synchronization conclusions are incomplete.",
            value=float(len(tracks)),
        ))

    all_spacings = [value for values in nearest_spacing.values() for value in values]
    spacing_cv = float(np.std(all_spacings) / max(np.mean(all_spacings), 1e-6)) if all_spacings else 1.0
    spacing_score = max(0.0, 100 - spacing_cv * 100)
    pose_score = max(0.0, 100 - float(np.mean([metric.mean_pose_deviation_deg for metric in dancer_metrics])) * 2)
    timing_score = float(np.mean(timing_scores)) if timing_scores else None
    overall_components = [pose_score, spacing_score, float(np.mean([metric.motion_consistency for metric in dancer_metrics]))]
    if timing_score is not None:
        overall_components.append(timing_score)
    multi_person_frames = sum(1 for frame in frame_records if len(frame["dancers"]) >= 2)
    full_ensemble_frames = sum(1 for frame in frame_records if len(frame["dancers"]) >= expected_dancers)
    full_ensemble_coverage = full_ensemble_frames / sampled if sampled else 0.0
    mean_detected_dancers = float(np.mean([len(frame["dancers"]) for frame in frame_records])) if frame_records else 0.0
    observation_confidence = min(100.0, mean_detected_dancers / expected_dancers * 100)
    if full_ensemble_coverage < 0.5:
        events.append(EnsembleSyncEvent(
            time=0,
            kind="tracking",
            severity="high",
            message=f"The complete {expected_dancers}-dancer ensemble is visible in only {full_ensemble_coverage * 100:.0f}% of sampled frames; synchronization scores are provisional.",
            value=round(full_ensemble_coverage, 3),
        ))
    notes = [
        "MediaPipe detects multiple full-body poses; FORM assigns temporary D-labels using nearest-centroid tracking.",
        "Timing compares motion-energy peaks with the uploaded song's detected beat timestamps; it does not identify choreographic counts.",
        "Pose agreement compares six joint angles with the group median. Spacing is measured in image coordinates, not stage metres.",
        "A fixed camera, visible full bodies, minimal occlusion, and limited crossing produce the most reliable identity tracking.",
    ]
    overlay_step = max(1, len(frame_records) // 90)
    pose_frames = [
        EnsemblePoseFrame(
            time=frame["time"],
            dancers={
                dancer_id: record["landmarks"]
                for dancer_id, record in frame["dancers"].items()
            },
        )
        for frame in frame_records[::overlay_step]
        if frame["dancers"]
    ]
    return EnsembleAnalysis(
        filename=filename,
        duration=round(duration, 3),
        expected_dancers=expected_dancers,
        tracked_dancers=len(tracks),
        sampled_frames=sampled,
        multi_person_coverage=round(multi_person_frames / sampled if sampled else 0.0, 3),
        full_ensemble_coverage=round(full_ensemble_coverage, 3),
        mean_detected_dancers=round(mean_detected_dancers, 2),
        observation_confidence_score=round(observation_confidence, 1),
        overall_synchronization_score=round(float(np.mean(overall_components)), 1),
        timing_score=round(timing_score, 1) if timing_score is not None else None,
        pose_agreement_score=round(pose_score, 1),
        spacing_consistency_score=round(spacing_score, 1),
        dancers=dancer_metrics,
        events=sorted(events, key=lambda event: (0 if event.severity == "high" else 1, event.time))[:30],
        timeline=timeline[::max(1, len(timeline) // 80)],
        pose_frames=pose_frames,
        notes=notes,
    )
