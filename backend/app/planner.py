from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from openai import OpenAI
from .formations import assign_nearest, generate_positions
from .motion_library import list_motion_summaries, motion_catalog
from .models import (
    AudioAnalysis, ChoreographyPlan, DecisionLogEntry, Formation, MotionAnalysis,
    PlanResponse, PlanRevisionResponse, StageConstraints,
)
from .validation import validate_plan


MOVEMENTS = ["hold", "travel", "canon", "unison", "ripple", "turn", "level_change"]
DEFAULT_FORMATIONS = ["line", "v", "circle", "diagonal", "two_rows"]


def _compact_audio_context(analysis: AudioAnalysis) -> dict:
    """Keep model context musical while excluding dense UI-only signal curves."""
    return {
        "filename": analysis.filename,
        "duration": analysis.duration,
        "tempo": analysis.tempo,
        "beat_times": analysis.beat_times,
        "sections": [section.model_dump() for section in analysis.sections],
        "notes": analysis.notes,
    }


def _compact_motion_context(constraints: StageConstraints) -> list[dict]:
    summaries = list_motion_summaries()
    if constraints.preferred_motion_genres:
        allowed = set(constraints.preferred_motion_genres)
        summaries = [clip for clip in summaries if clip.genre in allowed]
    return [
        {
            "id": clip.id,
            "name": clip.name,
            "genre": clip.genre,
            "duration": clip.duration,
            "loopable": clip.loopable,
            "movement_family": clip.movement_family,
            "style": clip.style,
            "label_scope": clip.label_scope,
            "default_counts": clip.default_counts,
        }
        for clip in summaries
    ]


def _local_plan(analysis: AudioAnalysis, c: StageConstraints) -> ChoreographyPlan:
    section_count = max(2, len(analysis.sections))
    preferred = c.preferred_formations or DEFAULT_FORMATIONS
    # Start with a spacious configuration and avoid abrupt identity swaps.
    formations = []
    if analysis.sections:
        intervals = [(s.start, s.end, s.energy) for s in analysis.sections]
    else:
        width = analysis.duration / section_count
        intervals = [(i * width, (i + 1) * width, "medium") for i in range(section_count)]
    previous_positions = None
    available_clips = list_motion_summaries()
    if c.preferred_motion_genres:
        if c.motion_selection_mode == "sequence":
            # Sequence mode preserves the user's exact click order.
            preferred_clips = [
                clip
                for genre in c.preferred_motion_genres
                for clip in available_clips
                if clip.genre == genre
            ] or available_clips
        else:
            # Palette mode is an unordered inclusion set. The seed supplies a
            # safe distribution; the live agent may rearrange it musically.
            preferred_clips = [clip for clip in available_clips if clip.genre in c.preferred_motion_genres] or available_clips
    else:
        preferred_clips = available_clips
    # A motion palette is an explicit request to use several vocabularies in
    # one score. If the audio has fewer large sections than selected styles,
    # split its longest sections so every selected style receives a phrase.
    target_phrases = len(c.preferred_motion_genres)
    while target_phrases and len(intervals) < target_phrases:
        index = max(range(len(intervals)), key=lambda item: intervals[item][1] - intervals[item][0])
        start, end, energy = intervals.pop(index)
        midpoint = (start + end) / 2
        intervals[index:index] = [(start, midpoint, energy), (midpoint, end, energy)]
    for i, (start, end, energy) in enumerate(intervals):
        kind = preferred[i % len(preferred)]
        positions = generate_positions(kind, c)
        if previous_positions:
            positions = assign_nearest(previous_positions, positions)
        movement = "unison" if energy == "high" else "ripple" if energy == "medium" else "hold"
        clip = preferred_clips[i % len(preferred_clips)] if preferred_clips else None
        phrase_duration = end - start
        motion_speed = max(0.5, min(2.0, clip.duration / phrase_duration)) if clip else 1.0
        if clip and phrase_duration * motion_speed > clip.duration + 0.05:
            clip = None
            motion_speed = 1.0
        candidate = Formation(id=f"F{i + 1}", name=kind.replace("_", " ").title(), start=start, end=end, positions=positions, geometry_kind=kind, movement=movement, movement_description=f"{movement.replace('_', ' ').title()} phrase shaped to the {energy}-energy region.", rationale=f"Uses a {kind.replace('_', ' ')} to respond to the measured relative {energy} RMS energy while honoring stage dimensions.", motion_clip_id=clip.id if clip else None, motion_speed=round(motion_speed, 3), mirror_motion=bool(i % 2), phase_offset=0.35 if movement in {"canon", "ripple"} else 0.0, counts=max(1, round((end - start) * analysis.tempo / 60)) if analysis.tempo > 0 else None)
        # Try alternate requested shapes if the sampled transition is unsafe.
        trial = ChoreographyPlan(title="trial", creative_direction=c.mood, formations=[*formations, candidate])
        if formations and not validate_plan(trial, c, motion_catalog=motion_catalog()).valid:
            for alternate in [*preferred, *DEFAULT_FORMATIONS]:
                alt_positions = assign_nearest(previous_positions, generate_positions(alternate, c))
                alt_candidate = candidate.model_copy(update={"name": alternate.replace("_", " ").title(), "positions": alt_positions, "geometry_kind": alternate, "rationale": f"Selected {alternate.replace('_', ' ')} after deterministic path validation rejected a less feasible transition."})
                if validate_plan(ChoreographyPlan(title="trial", creative_direction=c.mood, formations=[*formations, alt_candidate]), c, motion_catalog=motion_catalog()).valid:
                    candidate = alt_candidate
                    break
            else:
                candidate = candidate.model_copy(update={"name": f"Sustained {formations[-1].name}", "positions": deepcopy(previous_positions), "geometry_kind": formations[-1].geometry_kind, "movement": "hold", "movement_description": "Hold and reshape levels in place; spatial travel was unsafe under the current constraints.", "rationale": "Preserved the prior safe geometry because sampled alternatives violated spacing or path constraints."})
        formations.append(candidate)
        previous_positions = candidate.positions
    return ChoreographyPlan(title="FORM Study", creative_direction=c.mood, formations=formations)


def _changes(previous: ChoreographyPlan | None, current: ChoreographyPlan) -> list[str]:
    if not previous:
        return []
    changes = []
    old = {f.id: f for f in previous.formations}
    for f in current.formations:
        before = old.get(f.id)
        if before and before.name != f.name:
            changes.append(f"{f.id}: {before.name} → {f.name}")
        elif before and before.positions != f.positions:
            changes.append(f"{f.id}: dancer positions adjusted for the new constraints")
    if len(previous.formations) != len(current.formations):
        changes.append(f"Section plan changed from {len(previous.formations)} to {len(current.formations)} formations")
    return changes or ["Timing and spatial assignments were recomputed; formation names were preserved"]


def _revision_changes(previous: ChoreographyPlan, current: ChoreographyPlan) -> list[str]:
    changes: list[str] = []
    old = {formation.id: formation for formation in previous.formations}
    for formation in current.formations:
        before = old.get(formation.id)
        if not before:
            changes.append(f"Added {formation.id}: {formation.name}")
            continue
        fields = []
        if before.name != formation.name or before.geometry_kind != formation.geometry_kind:
            fields.append(f"formation {before.name} to {formation.name}")
        if before.motion_clip_id != formation.motion_clip_id:
            fields.append("motion reference")
        if before.movement != formation.movement:
            fields.append(f"behavior to {formation.movement.replace('_', ' ')}")
        if before.positions != formation.positions:
            fields.append("dancer positions")
        if before.start != formation.start or before.end != formation.end:
            fields.append("timing")
        if before.motion_speed != formation.motion_speed or before.mirror_motion != formation.mirror_motion:
            fields.append("motion treatment")
        if fields:
            changes.append(f"{formation.id}: " + ", ".join(fields))
    removed = sorted(set(old) - {formation.id for formation in current.formations})
    changes.extend(f"Removed {formation_id}" for formation_id in removed)
    return changes or ["The agent preserved the current plan because the request did not require a safe structural change"]


def revise_choreography(
    analysis: AudioAnalysis,
    constraints: StageConstraints,
    current_plan: ChoreographyPlan,
    instruction: str,
) -> PlanRevisionResponse:
    started = time.perf_counter()
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("A live AI provider is required for conversational revision")
    max_attempts = max(1, min(4, int(os.getenv("FORM_MAX_AGENT_ATTEMPTS", "3"))))
    client = OpenAI(
        api_key=key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        timeout=max(10.0, min(300.0, float(os.getenv("FORM_PROVIDER_TIMEOUT_SECONDS", "90")))),
        max_retries=0,
    )
    tool = {
        "type": "function",
        "function": {
            "name": "propose_choreography_revision",
            "description": "Return the complete revised choreography plan after applying the choreographer's request.",
            "parameters": ChoreographyPlan.model_json_schema(),
        },
    }
    catalog = motion_catalog()
    system = (
        "You are FORM's conversational choreography co-director. Apply only the user's requested creative changes to the supplied current plan. "
        "Preserve unrelated phrases, stable dancer IDs, and valid timing. Use only listed motion_clip_id values. Never claim named-step recognition. "
        "Return the complete plan only through propose_choreography_revision. Deterministic validation checks bounds, spacing, travel, sampled path collisions, and motion duration. "
        "Use compact text: title at most 8 words, creative direction at most 60 words, formation names at most 6 words, and descriptions/rationales at most 12 words each. "
        "If validation returns errors, revise the smallest necessary part of the plan and call the tool again."
    )
    context = {
        "instruction": instruction,
        "audio": _compact_audio_context(analysis),
        "constraints": constraints.model_dump(),
        "current_plan": current_plan.model_dump(),
        "motion_library": _compact_motion_context(constraints),
    }
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(context)}]
    revised = None
    validation = None
    attempts = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=messages,
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "propose_choreography_revision"}},
            temperature=0.3,
            max_tokens=max(512, min(16000, int(os.getenv("FORM_MAX_OUTPUT_TOKENS", "6000")))),
        )
        message = completion.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        call = next((item for item in (message.tool_calls or []) if item.function.name == "propose_choreography_revision"), None)
        if not call:
            messages.append({"role": "user", "content": "Call propose_choreography_revision with the complete revised plan."})
            continue
        try:
            revised = ChoreographyPlan.model_validate_json(call.function.arguments)
            validation = validate_plan(revised, constraints, motion_catalog=catalog)
        except Exception as exc:
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps({"valid": False, "schema_error": str(exc)})})
            continue
        messages.append({"role": "tool", "tool_call_id": call.id, "content": validation.model_dump_json()})
        if validation.valid:
            break
        messages.append({"role": "user", "content": "Revise only what is needed to resolve every validator error, then call the tool again."})
    if revised is None or validation is None:
        raise RuntimeError("The live co-director did not return a parseable structured revision")
    changes = _revision_changes(current_plan, revised)
    return PlanRevisionResponse(
        revised_plan=revised,
        validation=validation,
        attempts=attempts,
        latency_ms=round((time.perf_counter() - started) * 1000),
        summary=f"FORM interpreted: {instruction.strip()}",
        changes=changes,
    )


def plan_choreography(analysis: AudioAnalysis, constraints: StageConstraints, previous: ChoreographyPlan | None = None, motion: MotionAnalysis | None = None, force_local: bool = False) -> PlanResponse:
    started = time.perf_counter()
    key = os.getenv("OPENAI_API_KEY")
    max_attempts = max(1, min(5, int(os.getenv("FORM_MAX_AGENT_ATTEMPTS", "3"))))
    max_output_tokens = max(512, min(16000, int(os.getenv("FORM_MAX_OUTPUT_TOKENS", "6000"))))
    provider_timeout = max(10.0, min(300.0, float(os.getenv("FORM_PROVIDER_TIMEOUT_SECONDS", "90"))))
    log: list[DecisionLogEntry] = []
    catalog = motion_catalog()
    if not key or force_local:
        plan = _local_plan(analysis, constraints)
        validation = validate_plan(plan, constraints, motion_catalog=catalog)
        log.append(DecisionLogEntry(attempt=1, phase="OBSERVE", message="Read measured audio features and user constraints."))
        reason = "Cached demo requested" if force_local else "No API key is configured"
        log.append(DecisionLogEntry(attempt=1, phase="PLAN", message=f"{reason}; used the deterministic local planner, clearly marked as fallback."))
        log.append(DecisionLogEntry(attempt=1, phase="VALIDATE", message=f"Checked bounds, spacing, travel speed, and sampled paths: {'passed' if validation.valid else 'failed'}.", validation=validation))
        return PlanResponse(plan=plan, validation=validation, attempts=1, latency_ms=round((time.perf_counter() - started) * 1000), execution_mode="local_fallback", decision_log=log, changes=_changes(previous, plan))

    client = OpenAI(
        api_key=key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        timeout=provider_timeout,
        max_retries=0,
    )
    tool = {"type": "function", "function": {"name": "submit_choreography_plan", "description": "Submit a complete choreography plan for deterministic spatial validation.", "parameters": ChoreographyPlan.model_json_schema()}}
    spatial_seed = _local_plan(analysis, constraints)
    spatial_seed_validation = validate_plan(spatial_seed, constraints, motion_catalog=catalog)
    system = "You are FORM, an expert group-dance planning agent. Return a plan only through submit_choreography_plan. Coordinates are meters from stage top-left. Use exactly the stable dancer IDs D1..Dn. A deterministic spatial-planning tool provides a seed plan that already accounts for bounds, spacing, travel, sampled path collisions, and motion-clip duration. Preserve every seed formation's start, end, dancer IDs, and coordinates verbatim when the seed is valid; focus your creative work on the title, direction, formation naming, movement vocabulary, motion-library selection, descriptions, and rationales. Do not replace safe coordinates merely to be more creative. When preferred_motion_genres is nonempty, use only those genres and include each at least once. In motion_selection_mode=palette, arrange them in whatever order best fits the music; in motion_selection_mode=sequence, preserve the user's exact listed order, repeating only after the list is exhausted. When a motion library is present, every formation must select a listed motion_clip_id and keep motion_speed within 0.5–2.0 so the non-looping clip covers the full formation. Treat AIST++ entries as genre-level motion studies. Treat label_scope=family_reference entries as curated examples of the named movement family, not evidence that FORM automatically recognized a step. When a reference-motion summary is present, use its high-motion moments as inspiration for timing and dynamics, but never claim that FORM recognized a named dance step. Use compact text: title at most 8 words, creative direction at most 60 words, formation names at most 6 words, and descriptions/rationales at most 12 words each. The application validates every submission; revise from every structured error."
    context = {
        "measured_audio_analysis": _compact_audio_context(analysis),
        "constraints": constraints.model_dump(),
        "previous_plan_to_preserve_where_valid": previous.model_dump() if previous else None,
        "deterministic_spatial_seed": spatial_seed.model_dump(),
        "spatial_seed_validation": spatial_seed_validation.model_dump(),
        "available_motion_library": _compact_motion_context(constraints),
        "reference_motion_summary": {
            "filename": motion.filename,
            "duration": motion.duration,
            "pose_coverage": motion.pose_coverage,
            "mean_motion_energy": motion.mean_motion_energy,
            "high_motion_times": motion.high_motion_times,
            "interpretation_limit": "Pose tracking and landmark displacement only; no named-step recognition.",
        } if motion else None,
    }
    messages = [{"role": "system", "content": system}, {"role": "user", "content": "OBSERVE then PLAN a synchronized choreography. Submit it for validation.\n" + json.dumps(context)}]
    plan = None
    validation = None
    for attempt in range(1, max_attempts + 1):
        log.append(DecisionLogEntry(attempt=attempt, phase="OBSERVE" if attempt == 1 else "REVISE", message="Interpreting audio/constraints." if attempt == 1 else "Revising from deterministic validation errors."))
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=messages,
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "submit_choreography_plan"}},
            temperature=0.35,
            max_tokens=max_output_tokens,
        )
        message = completion.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        call = next((x for x in (message.tool_calls or []) if x.function.name == "submit_choreography_plan"), None)
        if not call:
            log.append(DecisionLogEntry(attempt=attempt, phase="ACT", message="Model did not call the required submission tool."))
            messages.append({"role": "user", "content": "You must call submit_choreography_plan with a complete valid plan."})
            continue
        log.append(DecisionLogEntry(attempt=attempt, phase="ACT", message="Model called submit_choreography_plan with structured arguments."))
        try:
            plan = ChoreographyPlan.model_validate_json(call.function.arguments)
            validation = validate_plan(plan, constraints, motion_catalog=catalog)
        except Exception as exc:
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps({"valid": False, "schema_error": str(exc)})})
            log.append(DecisionLogEntry(attempt=attempt, phase="VALIDATE", message=f"Schema validation failed: {exc}"))
            continue
        log.append(DecisionLogEntry(attempt=attempt, phase="VALIDATE", message=f"Deterministic validation {'passed' if validation.valid else 'found violations'}.", validation=validation))
        messages.append({"role": "tool", "tool_call_id": call.id, "content": validation.model_dump_json()})
        if validation.valid:
            break
        messages.append({"role": "user", "content": "REVISE the plan to resolve every validator error, then call the tool again. Preserve valid preferences."})
    if plan is None or validation is None:
        plan = _local_plan(analysis, constraints)
        validation = validate_plan(plan, constraints, motion_catalog=catalog)
        mode = "local_fallback"
        log.append(DecisionLogEntry(attempt=max_attempts, phase="REVISE", message="Live model did not produce parseable tool output; returned the explicitly marked local fallback."))
    else:
        mode = "live_agent"
    return PlanResponse(plan=plan, validation=validation, attempts=min(max_attempts, len([x for x in log if x.phase in {"OBSERVE", "REVISE"}])), latency_ms=round((time.perf_counter() - started) * 1000), execution_mode=mode, decision_log=log, changes=_changes(previous, plan))

