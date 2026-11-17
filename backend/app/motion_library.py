from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import MotionClip, MotionClipSummary


LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "motion_library"


@lru_cache(maxsize=1)
def list_motion_summaries() -> list[MotionClipSummary]:
    summaries = []
    for catalog_path in sorted(LIBRARY_ROOT.glob("*/catalog.json")):
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        summaries.extend(MotionClipSummary.model_validate(item) for item in payload.get("clips", []))
    return summaries


def motion_catalog() -> dict[str, MotionClipSummary]:
    return {clip.id: clip for clip in list_motion_summaries()}


@lru_cache(maxsize=32)
def load_motion_clip(clip_id: str) -> MotionClip:
    summary = motion_catalog().get(clip_id)
    if summary is None:
        raise KeyError(clip_id)
    paths = list(LIBRARY_ROOT.glob(f"*/clips/{clip_id}.json"))
    if not paths:
        raise KeyError(clip_id)
    path = paths[0]
    return MotionClip.model_validate_json(path.read_text(encoding="utf-8"))


def library_metadata() -> dict:
    catalogs = []
    for catalog_path in sorted(LIBRARY_ROOT.glob("*/catalog.json")):
        catalogs.append(json.loads(catalog_path.read_text(encoding="utf-8")))
    if not catalogs:
        return {
            "dataset": "FORM motion libraries",
            "clips": [],
            "notice": "No local motion library has been imported yet.",
        }
    return {
        "dataset": "FORM attributed motion libraries",
        "license": "Each collection retains its own source and attribution metadata.",
        "collections": [{key: value for key, value in catalog.items() if key != "clips"} for catalog in catalogs],
        "clips": [clip.model_dump() for clip in list_motion_summaries()],
    }
