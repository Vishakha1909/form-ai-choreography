# FORM — AI Choreography Architect

FORM turns a 20–45 second MP3/WAV excerpt into an editable, validated group-dance plan with an audio-synchronized stage preview. An optional reference video supplies locally extracted body poses, while attributed libraries supply ten AIST++ genre studies and five curated Bharatanatyam adavu-family references.

## What is real vs. heuristic

- **Measured:** waveform, tempo estimate, beat timestamps, onset strength, and RMS energy are computed from uploaded audio with librosa.
- **Heuristic:** section boundaries use chroma-based agglomerative segmentation; energy labels compare section RMS to the excerpt's own distribution.
- **Motion library:** ten compact samples derived from AIST++ SMPL annotations cover Break, Pop, Lock, Waack, Middle Hip-Hop, LA-Style Hip-Hop, House, Krump, Street Jazz, and Ballet Jazz. These are genre-level studies, not named-step labels.
- **Curated adavus:** Thattadavu, Nattadavu, Ta Tei Tei Ta/Paraval, Kudithu Mettu, and Tha Hatha Jham/Theermaana are represented by locally extracted pose sequences from attributed Kalakshetra-style reference demonstrations. They are selectable family references, not automatic recognition results.
- **Pose-aware:** MediaPipe samples an optional MP4/MOV/WebM/AVI reference, extracts 17 display joints from its 33-keypoint pose model, and computes heuristic landmark motion energy. FORM does not claim named-step recognition.
- **Animated:** every dancer has a full-body skeleton. Agent-selected AIST++ motion or an uploaded reference replaces procedural joints and can be mirrored, speed-adjusted, or phased for canon/ripple phrases.
- **Motion-validated:** the deterministic validator rejects missing/unknown library IDs and non-looping clips that are too short for a planned phrase.
- **Human-editable:** after generation, the choreographer can drag dancers; change a phrase's formation, motion reference, behavior, speed, mirroring, name, or transition boundary; undo/redo; and revalidate without another model call.
- **AI co-director:** after generation, the choreographer can describe a revision in plain language. A live tool-calling model proposes a complete revised plan, deterministic validation checks it, and nothing changes until the user accepts the proposal. This path has no deterministic or cached fallback.
- **Rehearsal diagnosis (MVP):** an uploaded fixed-camera team video can be compared against the uploaded song's detected beats. FORM reports per-dancer timing offsets, joint-angle agreement, motion-energy consistency, image-space spacing consistency, a clickable sync timeline, timestamped flags, and a video review overlay built from downsampled pose snapshots. Temporary dancer IDs use centroid tracking, not identity recognition.
- **Diagnosis-to-plan loop:** selecting a warning seeks the rehearsal video to that moment. **Ask AI how to adapt the choreography** sends the uncertain observation, musical phrase, and current plan to the live co-director; the resulting plan remains a proposal until accepted.
- **Diagnosis confidence:** FORM reports unique temporary track IDs separately from the average number of dancers visible at once, complete-ensemble coverage, and observation confidence. Synchronization remains explicitly provisional when the detector cannot see enough of the expected ensemble.
- **Diagnosis limits:** pose agreement means similarity to the group, not dance correctness; spacing is measured in image space, not stage meters; dancer IDs can swap during crossings or occlusion; and results work best when every full body remains visible.
- **Exportable:** JSON preserves the complete editable plan, while an HTML rehearsal sheet summarizes timing, formation, motion vocabulary, behavior, and dancer coordinates for printing.
- **Agent mode:** with `OPENAI_API_KEY`, the bounded tool-call loop validates each model plan and returns structured errors for revision. Without it, the UI clearly labels the deterministic result `local fallback`.
- **Provider limits:** the supplied deployment configuration uses a compact 1200-token output ceiling and 120-second timeout, preventing OpenAI-compatible providers from reserving excessive output context or hanging indefinitely.

## Run locally (PowerShell)

Requirements: Python 3.12 recommended, Node 22+, and ffmpeg on PATH for broad MP3 compatibility.

```powershell
cd 'C:\00 Vishakha\vishakha\p\form'
Copy-Item .env.example .env
# Add OPENAI_API_KEY to .env for live agent mode (optional for local demo).

# This machine's installed 3.12 runtime is registered under the Astral tag:
py -V:Astral/CPython3.12.14 -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt

New-Item -ItemType Directory -Force -Path backend\models | Out-Null
curl.exe -L 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task' -o backend\models\pose_landmarker_full.task

cd frontend
npm install
cd ..
```

Terminal 1:

```powershell
cd 'C:\00 Vishakha\vishakha\p\form'
Get-Content .env | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') } }
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload
```

Terminal 2:

```powershell
cd 'C:\00 Vishakha\vishakha\p\form\frontend'
npm run dev
```

Open <http://localhost:5173>.

Before presenting, run the safe preflight check (it verifies that a key exists but never prints its value):

```powershell
cd 'C:\00 Vishakha\vishakha\p\form'
powershell -ExecutionPolicy Bypass -File .\scripts\preflight.ps1
```

See `DEMO_RUNBOOK.md` for the timed talk track and failure-recovery flow.

## Deploy as one Railway service

FORM includes a production Dockerfile that builds the Vite frontend and serves
it from FastAPI. Railway reads `railway.toml`, builds the image, and checks
`/api/health` before marking the deployment healthy.

1. Push this repository to GitHub and create a Railway project from it.
2. Add these Railway service variables; never commit the local `.env` file:

   - `OPENAI_API_KEY`
   - `OPENAI_MODEL=xiaomi/mimo-v2.6-flash`
   - `OPENAI_BASE_URL=https://openrouter.ai/api/v1`
   - `FORM_MAX_OUTPUT_TOKENS=1200`
   - `FORM_MAX_AGENT_ATTEMPTS=3`
   - `FORM_PROVIDER_TIMEOUT_SECONDS=120`

3. Generate a Railway public domain after the deployment becomes healthy.

Uploaded media uses the service's temporary filesystem. That is appropriate
for this short-lived class deployment; files disappear when the container is
replaced or redeployed.

## Optional: regenerate the AIST++ library

FORM bundles ten small derived samples and attribution; the original archive is not part of the app. To regenerate from the official motion-only archive after accepting its terms:

```powershell
New-Item -ItemType Directory -Force data\aistpp | Out-Null
curl.exe -L 'https://github.com/google/aistplusplus_dataset/releases/download/v1.0/motions.zip' -o data\aistpp\motions.zip
Expand-Archive data\aistpp\motions.zip data\aistpp\source -Force
.\.venv\Scripts\python.exe scripts\import_aistpp.py data\aistpp\source\motions backend\motion_library\aistpp
```

AIST++ annotations are published by Google LLC under CC BY 4.0. Source AIST dance videos have separate terms. FORM does not redistribute the SMPL body model.

## Tests and reproducible evaluation

```powershell
cd 'C:\00 Vishakha\vishakha\p\form'
.\.venv\Scripts\python -m pytest backend\tests -q
$env:PYTHONPATH='backend'
.\.venv\Scripts\python backend\evaluate.py
```

The evaluation writes `evaluation-results.json`. Its fixture is explicitly synthetic; pass rate, violations, attempts, and latency are measured during that run.

## 3–4 minute presentation flow

1. Upload a prepared 25–35 second excerpt and point out the measured waveform/beats vs. heuristic shaded sections.
2. Optionally upload a 5–15 second, full-body reference clip. Show pose coverage and explain that extraction stays local.
3. Apply the classical or mixed-style preset, then choose Palette mode or an Ordered sequence and generate the plan.
4. Play audio and show that formation positions and skeletal poses follow the audio element's actual `currentTime`.
5. Ask the **AI co-director** for one bounded change, inspect its validated diff, then accept it. Open **Edit positions** and drag one dancer to contrast AI-assisted and direct editing.
6. Optionally upload a short fixed-camera team rehearsal to **Diagnose team rehearsal video** and explain the timing/pose/spacing flags and limitations.
7. Download the rehearsal sheet. If networking/model access fails, select **Load cached studio demo**; it is visibly labeled `cached demo`, never presented as a fresh model run.

## Architecture

- `backend/app/audio.py`: measured features and disclosed heuristic segmentation.
- `backend/app/pose.py`: local MediaPipe video sampling, pose landmarks, coverage, and heuristic motion energy.
- `backend/app/ensemble.py`: multi-person pose tracking and disclosed timing, pose, motion, and image-space spacing diagnostics.
- `backend/app/motion_library.py`: attributed motion catalog and clip loading.
- `backend/app/planner.py`: live structured planning agent, conversational revision proposals, bounded validation loop, and labeled initial-plan fallback.
- `backend/app/validation.py`: bounds, spacing, speed, distance, sampled path collisions, and motion-clip availability/duration.
- `scripts/import_aistpp.py`: AIST++ SMPL annotation conversion to FORM's generic skeleton.
- `scripts/import_adavu_references.py`: selects high-coverage pose windows from the attributed adavu source manifest.
- `frontend/src/App.tsx`: upload, timeline, constraint editing, synchronized stage, validation/decision trace.

