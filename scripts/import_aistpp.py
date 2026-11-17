"""Convert AIST++ SMPL motion annotations into FORM's compact pose library.

This converter intentionally uses a generic 24-joint rest skeleton rather than
redistributing the separately licensed SMPL body model. The input annotations
remain subject to the AIST++ dataset terms and attribution requirements.
"""

from __future__ import annotations

import argparse
import json
import pickle
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


GENRES = {
    "BR": "Break",
    "PO": "Pop",
    "LO": "Lock",
    "WA": "Waack",
    "MH": "Middle Hip-Hop",
    "LH": "LA-Style Hip-Hop",
    "HO": "House",
    "KR": "Krump",
    "JS": "Street Jazz",
    "JB": "Ballet Jazz",
}

# SMPL's public 24-joint kinematic layout, represented with an original,
# generic rest skeleton so no SMPL model data is copied into the project.
PARENTS = np.array([-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21])
OFFSETS = np.array(
    [
        [0, 0, 0], [-.10, -.07, 0], [.10, -.07, 0], [0, .12, 0],
        [0, -.42, 0], [0, -.42, 0], [0, .12, 0], [0, -.43, 0],
        [0, -.43, 0], [0, .12, 0], [0, -.05, .12], [0, -.05, .12],
        [0, .15, 0], [-.08, .06, 0], [.08, .06, 0], [0, .17, 0],
        [-.15, .02, 0], [.15, .02, 0], [-.27, 0, 0], [.27, 0, 0],
        [-.25, 0, 0], [.25, 0, 0], [-.09, 0, 0], [.09, 0, 0],
    ],
    dtype=np.float32,
)
DISPLAY_JOINTS = {
    "nose": 15,
    "left_shoulder": 16,
    "right_shoulder": 17,
    "left_elbow": 18,
    "right_elbow": 19,
    "left_wrist": 20,
    "right_wrist": 21,
    "left_hip": 1,
    "right_hip": 2,
    "left_knee": 4,
    "right_knee": 5,
    "left_ankle": 7,
    "right_ankle": 8,
}


def forward_kinematics(axis_angles: np.ndarray) -> np.ndarray:
    frame_count = axis_angles.shape[0]
    local = Rotation.from_rotvec(axis_angles.reshape(-1, 3)).as_matrix().reshape(frame_count, 24, 3, 3)
    global_rot = np.empty_like(local)
    positions = np.zeros((frame_count, 24, 3), dtype=np.float32)
    global_rot[:, 0] = local[:, 0]
    for joint in range(1, 24):
        parent = PARENTS[joint]
        global_rot[:, joint] = global_rot[:, parent] @ local[:, joint]
        positions[:, joint] = positions[:, parent] + np.einsum("nij,j->ni", global_rot[:, parent], OFFSETS[joint])
    return positions


def convert_clip(path: Path, output_fps: float, seconds: float) -> tuple[dict, dict]:
    with path.open("rb") as source:
        payload = pickle.load(source)
    poses = np.asarray(payload["smpl_poses"], dtype=np.float32).reshape(-1, 24, 3)
    source_fps = 60.0
    step = max(1, round(source_fps / output_fps))
    limit = min(len(poses), round(seconds * source_fps))
    sampled = poses[:limit:step]
    positions = forward_kinematics(sampled)
    # Root-relative joint speed gives a transparent motion-energy descriptor.
    centered = positions - positions[:, :1]
    energy = np.zeros(len(centered), dtype=np.float32)
    if len(centered) > 1:
        energy[1:] = np.linalg.norm(np.diff(centered, axis=0), axis=2).mean(axis=1) * output_fps
    genre_code = path.stem[1:3]
    genre = GENRES.get(genre_code, genre_code)
    clip_id = f"aistpp-{genre_code.lower()}-{path.stem[-4:].lower()}"
    duration = len(sampled) / output_fps
    frames = []
    for index, joints in enumerate(centered):
        landmarks = {
            name: {
                "x": round(float(joints[joint, 0]), 5),
                "y": round(float(-joints[joint, 1]), 5),
                "z": round(float(joints[joint, 2]), 5),
                "visibility": 1.0,
            }
            for name, joint in DISPLAY_JOINTS.items()
        }
        frames.append({"time": round(index / output_fps, 4), "motion_energy": round(float(energy[index]), 5), "landmarks": landmarks})
    summary = {
        "id": clip_id,
        "name": f"{genre} study {path.stem[-4:]}",
        "genre": genre,
        "source": f"AIST++:{path.stem}",
        "duration": round(duration, 3),
        "fps": output_fps,
        "frame_count": len(frames),
        "loopable": False,
        "attribution": "AIST++ annotations, Google LLC, CC BY 4.0",
    }
    return summary, {**summary, "frames": frames}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Directory containing AIST++ motion .pkl files")
    parser.add_argument("output", type=Path, help="FORM AIST++ motion-library directory")
    parser.add_argument("--max-per-genre", type=int, default=1)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--seconds", type=float, default=12.0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    clips_dir = args.output / "clips"
    clips_dir.mkdir(exist_ok=True)
    chosen: list[Path] = []
    for code in GENRES:
        chosen.extend(sorted(args.source.glob(f"g{code}_*.pkl"))[: args.max_per_genre])
    summaries = []
    for source_path in chosen:
        summary, clip = convert_clip(source_path, args.fps, args.seconds)
        summaries.append(summary)
        (clips_dir / f"{summary['id']}.json").write_text(json.dumps(clip, separators=(",", ":")), encoding="utf-8")
    catalog = {
        "dataset": "AIST++ Dance Motion Dataset",
        "source_url": "https://google.github.io/aistplusplus_dataset/",
        "license": "AIST++ annotations are CC BY 4.0; source dance videos have separate terms.",
        "conversion": "SMPL axis-angle annotations retargeted to an original generic skeleton; no SMPL body model redistributed.",
        "generated_at": datetime.now(UTC).isoformat(),
        "clips": summaries,
    }
    (args.output / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Imported {len(summaries)} clips across {len({x['genre'] for x in summaries})} genres")


if __name__ == "__main__":
    main()
