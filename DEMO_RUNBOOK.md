# FORM presentation runbook

## Before class

1. Connect power and disable sleep/notification popups.
2. Join the classroom network, but keep the cached demo available as the offline fallback.
3. Start the backend and frontend in separate PowerShell windows using the README commands.
4. Run `powershell -ExecutionPolicy Bypass -File .\scripts\preflight.ps1` from the FORM root.
5. Open `http://localhost:5173`, load the final excerpt, and complete one live generation before presenting.
6. Keep the final excerpt in an easy-to-find local folder. Do not depend on a streaming URL.

## Eight-minute presentation

### 0:00–0:45 — Problem and idea

“Choreographing a group is not only creative. Every musical decision creates spatial and timing constraints. FORM turns measured musical features into an editable spatial score, then verifies whether the score is physically feasible.”

### 0:45–1:30 — Architecture

- FastAPI and librosa measure the audio.
- A tool-calling model proposes the creative plan.
- Deterministic code validates boundaries, spacing, speed, and intermediate collision paths.
- React renders the plan using the audio element's actual playback time.

Emphasize that measured features, heuristic interpretations, and creative suggestions are labeled separately.

### 1:30–4:30 — Live generation

1. Upload the prepared 25–35 second excerpt.
2. Point to tempo, beats, waveform, energy, and heuristic musical sections.
3. Select **Classical demo preset**, keep **Palette · AI arranges**, and choose the adavus you want included.
4. Select **Generate choreography**.
5. Point to `live agent`, the structured tool call, and `PLAN VALIDATED`.
6. Play 10–15 seconds and explain one formation choice while the dancers move with the audio.

### 4:30–6:15 — AI co-direction and human editing

1. Ask the **AI co-director** for one precise change, such as making only the middle phrase a canon.
2. Read the proposed diff and validation result, emphasizing that the plan has not changed yet; then accept it.
3. Select **Edit positions**, drag one numbered dancer, and show that direct edits revalidate without another model call. Use undo once.
4. Download the printable rehearsal sheet.
5. If time permits, increase minimum spacing and select **Replan with constraints** to show full agent-level adaptation.

### 6:15–7:15 — What makes it agentic

“The model does not receive a request and emit trusted JSON once. It observes measured audio and constraints, calls a structured planning tool, receives deterministic validation results, and revises when necessary. Invalid plans remain visibly invalid after the bounded attempt limit.”

### 7:15–8:00 — Rehearsal diagnosis, limitations, and close

If time and a prepared short team clip are available, upload it with **Diagnose team rehearsal video**. Click a timestamped flag to seek the overlaid video, then use **Ask AI how to adapt the choreography** to create a validated proposal from that observation. Say explicitly that timing uses detected musical beats, pose scores measure agreement within the group, spacing is image-space consistency, and dancer IDs are temporary tracks rather than biometric identities.

- Section labels are heuristic, not ground-truth musical form.
- Curated adavu names come from attributed source labels, not automatic recognition.
- Movement references animate joint landmarks rather than photorealistic motion capture.
- The current prototype uses top-down geometry and linear interpolated paths.
- Multi-dancer diagnosis is an MVP: crossings and occlusion can swap temporary IDs, a fixed camera and visible full bodies work best, and pose similarity does not determine whether choreography is artistically or technically correct.

Close with: “FORM keeps the artist in control while making the spatial consequences of creative choices inspectable.”

## Recovery matrix

| Failure | What to do | What to say |
|---|---|---|
| OpenRouter is slow or unavailable | Select **Load cached studio demo** | “This is the explicitly labeled cached fallback; I am not representing it as a fresh model run.” |
| Live plan remains invalid | Show the violations instead of retrying indefinitely | “The bounded agent failed honestly; the validator does not silently approve unsafe geometry.” |
| MP3 decoding fails | Use the prepared WAV copy | “The audio content is identical; WAV removes classroom codec variability.” |
| Browser audio is muted | Unmute the tab and use the play control again | “Animation follows the audio element itself, so pausing audio also pauses the spatial score.” |
| Rehearsal video tracks too few dancers | Use the prepared wide, fixed-camera clip or skip this optional step | “The system reports insufficient pose coverage instead of inventing dancers; this footage is outside its reliable capture conditions.” |
| Frontend is accidentally closed | Reopen `http://localhost:5173` | The backend and analyzed uploads remain available while its terminal stays running. |

## Do not do during the demo

- Do not paste or display the `.env` file.
- Do not improvise with a full-length song.
- Do not claim heuristic sections are objectively correct musical labels.
- Do not call a cached or deterministic result a live-agent run.
- Do not describe group-relative pose agreement as judging dance correctness, or image-space spacing as physical meters.
- Do not keep regenerating if a bounded run fails; use the failure to explain verification.

