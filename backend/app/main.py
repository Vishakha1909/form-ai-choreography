from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .audio import analyze_audio
from .models import FormationGeometryRequest, PlanRequest, PlanResponse, PlanRevisionRequest, PlanRevisionResponse, StageConstraints, ValidationRequest, ValidationResult
from .formations import assign_nearest, generate_positions
from .motion_library import library_metadata, load_motion_clip, motion_catalog
from .planner import plan_choreography, revise_choreography
from .pose import analyze_motion
from .ensemble import analyze_ensemble
from .validation import validate_plan

ROOT = Path(__file__).resolve().parents[2]
UPLOADS = ROOT / "uploads"
FRONTEND_DIST = ROOT / "frontend" / "dist"
UPLOADS.mkdir(exist_ok=True)

app = FastAPI(title="FORM API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "live_agent_configured": bool(os.getenv("OPENAI_API_KEY")), "motion_library_clips": len(motion_catalog())}


@app.get("/api/motions")
def motions():
    """List locally available, attributed motion-library clips."""
    return library_metadata()


@app.get("/api/motions/{clip_id}")
def motion_clip(clip_id: str):
    if Path(clip_id).name != clip_id:
        raise HTTPException(400, "Invalid motion identifier")
    try:
        return load_motion_clip(clip_id)
    except KeyError as exc:
        raise HTTPException(404, "Motion clip not found") from exc


@app.get("/api/demo")
def cached_demo():
    """Return a reproducible offline demo, explicitly marked as cached."""
    destination = UPLOADS / "form-cached-demo.wav"
    if not destination.exists():
        sr, duration = 22050, 30
        t = np.arange(sr * duration) / sr
        carrier = 0.10 * np.sin(2 * np.pi * (110 + 110 * (t >= 10) + 110 * (t >= 20)) * t)
        pulse = np.zeros_like(t)
        for second in np.arange(0, duration, .5):
            start = int(second * sr); length = min(int(.055 * sr), len(pulse) - start)
            pulse[start:start + length] += (.15 + .08 * (second >= 10)) * np.hanning(length)
        envelope = np.where(t < 10, .55, np.where(t < 20, 1.0, .72))
        sf.write(destination, np.clip((carrier + pulse) * envelope, -.95, .95), sr)
    analysis = analyze_audio(destination, "FORM cached studio demo · synthetic 30s WAV")
    result = plan_choreography(analysis, StageConstraints(), force_local=True).model_copy(update={"execution_mode": "cached_demo"})
    return {"analysis": analysis, "audio_id": destination.name, "result": result, "disclosure": "Cached offline demo using a synthetic audio fixture and deterministic plan; not a fresh live model run."}


@app.post("/api/analyze")
def analyze(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".wav", ".mp3"}:
        raise HTTPException(415, "FORM currently accepts WAV and MP3 files")
    destination = UPLOADS / f"{uuid.uuid4().hex}{suffix}"
    max_bytes = int(os.getenv("FORM_MAX_UPLOAD_MB", "25")) * 1024 * 1024
    try:
        with destination.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        if destination.stat().st_size > max_bytes:
            destination.unlink(missing_ok=True)
            raise HTTPException(413, "Audio file is larger than the configured upload limit")
        result = analyze_audio(destination, file.filename or destination.name)
        return {"analysis": result, "audio_id": destination.name}
    except HTTPException:
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not decode/analyze this audio: {exc}") from exc


@app.post("/api/analyze-motion")
def analyze_reference_motion(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".mp4", ".mov", ".webm", ".avi"}:
        raise HTTPException(415, "FORM accepts MP4, MOV, WebM, and AVI reference videos")
    destination = UPLOADS / f"{uuid.uuid4().hex}{suffix}"
    max_bytes = 60 * 1024 * 1024
    try:
        with destination.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        if destination.stat().st_size > max_bytes:
            destination.unlink(missing_ok=True)
            raise HTTPException(413, "Reference video is larger than 60 MB")
        return {"motion_analysis": analyze_motion(destination, file.filename or destination.name)}
    except HTTPException:
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not analyze this reference video: {exc}") from exc


@app.post("/api/analyze-ensemble")
def analyze_ensemble_rehearsal(
    file: UploadFile = File(...),
    expected_dancers: int = Form(...),
    beat_times: str = Form("[]"),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".mp4", ".mov", ".webm", ".avi"}:
        raise HTTPException(415, "FORM accepts MP4, MOV, WebM, and AVI rehearsal videos")
    if not 2 <= expected_dancers <= 10:
        raise HTTPException(422, "Expected dancers must be between 2 and 10")
    destination = UPLOADS / f"{uuid.uuid4().hex}{suffix}"
    try:
        parsed_beats = json.loads(beat_times)
        if not isinstance(parsed_beats, list):
            raise ValueError("beat_times must be a JSON list")
        parsed_beats = [float(value) for value in parsed_beats]
        with destination.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        if destination.stat().st_size > 100 * 1024 * 1024:
            destination.unlink(missing_ok=True)
            raise HTTPException(413, "Rehearsal video is larger than 100 MB")
        return {"ensemble_analysis": analyze_ensemble(destination, file.filename or destination.name, expected_dancers, parsed_beats)}
    except HTTPException:
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not diagnose this rehearsal video: {exc}") from exc


@app.get("/api/audio/{audio_id}")
def audio_file(audio_id: str):
    if Path(audio_id).name != audio_id:
        raise HTTPException(400, "Invalid audio identifier")
    path = UPLOADS / audio_id
    if not path.exists():
        raise HTTPException(404, "Audio not found")
    return FileResponse(path)


@app.post("/api/plan", response_model=PlanResponse)
def plan(request: PlanRequest):
    try:
        return plan_choreography(request.analysis, request.constraints, request.previous_plan, request.motion_analysis)
    except Exception as exc:
        raise HTTPException(502, f"Planning failed: {exc}") from exc


@app.post("/api/revise", response_model=PlanRevisionResponse)
def revise_plan(request: PlanRevisionRequest):
    try:
        return revise_choreography(request.analysis, request.constraints, request.current_plan, request.instruction)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Conversational revision failed: {exc}") from exc


@app.post("/api/validate", response_model=ValidationResult)
def validate_edited_plan(request: ValidationRequest):
    """Revalidate a choreographer-edited plan without asking the model again."""
    return validate_plan(request.plan, request.constraints, motion_catalog=motion_catalog())


@app.post("/api/formations/generate")
def generate_formation_geometry(request: FormationGeometryRequest):
    """Generate safe target slots for a direct human formation edit."""
    positions = generate_positions(request.kind, request.constraints)
    if request.previous_positions:
        positions = assign_nearest(request.previous_positions, positions)
    return {"kind": request.kind, "positions": positions}


# Production serves the compiled React app from the same origin as the API.
# Vite continues to provide the frontend during local development.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

