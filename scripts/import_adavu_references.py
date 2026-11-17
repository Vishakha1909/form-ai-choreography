"""Build compact, family-level FORM motion references from local source videos."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.pose import analyze_motion


def select_window(frames, seconds: float, fps: float):
    if not frames:
        return [], 0.0
    window_frames = max(1, round(seconds * fps))
    best, best_score = frames[:window_frames], -1.0
    for start in range(0, len(frames), max(1, round(fps))):
        candidate = frames[start : start + window_frames]
        if len(candidate) < window_frames * 0.75:
            continue
        score = len(candidate) + sum(frame.motion_energy for frame in candidate) * 20
        if score > best_score:
            best, best_score = candidate, score
    origin = best[0].time if best else 0.0
    normalized = [frame.model_copy(update={"time": round(frame.time - origin, 4)}) for frame in best]
    return normalized, origin


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--scan-seconds", type=float, default=45.0)
    parser.add_argument("--clip-seconds", type=float, default=12.0)
    parser.add_argument("--fps", type=float, default=8.0)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    clips_dir = args.output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for item in manifest["clips"]:
        path = args.source_dir / item["filename"]
        analysis = analyze_motion(path, item["title"], target_fps=args.fps, max_seconds=args.scan_seconds)
        frames, source_start = select_window(analysis.frames, args.clip_seconds, analysis.sampled_fps)
        if len(frames) < round(args.clip_seconds * args.fps * 0.6):
            raise RuntimeError(f"Insufficient pose coverage for {item['family']}: {len(frames)} frames")
        duration = round((frames[-1].time + 1 / analysis.sampled_fps), 3)
        source_url = f"https://www.youtube.com/watch?v={item['video_id']}"
        summary = {
            "id": item["id"],
            "name": f"{item['family']} family study",
            "genre": item["family"],
            "source": f"YouTube:{item['video_id']}#t={source_start:.1f}",
            "duration": duration,
            "fps": analysis.sampled_fps,
            "frame_count": len(frames),
            "loopable": False,
            "attribution": f"Reference demonstration by {manifest['primary_channel']}; derived pose sequence for a class project",
            "collection": manifest["collection"],
            "movement_family": item["family"],
            "style": manifest["style"],
            "source_url": source_url,
            "label_scope": "family_reference",
            "default_counts": item["counts"],
        }
        summaries.append(summary)
        (clips_dir / f"{item['id']}.json").write_text(
            json.dumps({**summary, "frames": [frame.model_dump() for frame in frames]}, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"{item['family']}: {len(frames)} frames from {source_start:.1f}s, coverage {analysis.pose_coverage:.0%}")
    catalog = {
        "dataset": manifest["collection"],
        "source_url": manifest["supporting_playlists"][0],
        "supporting_playlists": manifest["supporting_playlists"],
        "license": "Source links retained; only derived pose landmarks are bundled for this class project.",
        "conversion": "MediaPipe body landmarks sampled locally; labels are curated family references, not classifier output.",
        "generated_at": datetime.now(UTC).isoformat(),
        "clips": summaries,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Imported {len(summaries)} adavu family references")


if __name__ == "__main__":
    main()
