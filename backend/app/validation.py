from __future__ import annotations

import math
from collections.abc import Mapping
from .models import ChoreographyPlan, MotionClipSummary, StageConstraints, ValidationIssue, ValidationResult


def _distance(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def validate_plan(
    plan: ChoreographyPlan,
    c: StageConstraints,
    sample_hz: int = 12,
    motion_catalog: Mapping[str, MotionClipSummary] | None = None,
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    expected = {f"D{i + 1}" for i in range(c.dancer_count)}
    samples = 0
    formations = sorted(plan.formations, key=lambda x: x.start)
    for f in formations:
        if motion_catalog and not f.motion_clip_id:
            issues.append(ValidationIssue(code="MISSING_MOTION_CLIP", message=f"{f.id} does not select a motion-library clip", formation_id=f.id))
        elif f.motion_clip_id and motion_catalog is not None:
            clip = motion_catalog.get(f.motion_clip_id)
            if clip is None:
                issues.append(ValidationIssue(code="UNKNOWN_MOTION_CLIP", message=f"{f.id} references unavailable motion {f.motion_clip_id}", formation_id=f.id, details={"motion_clip_id": f.motion_clip_id}))
            elif not clip.loopable and (f.end - f.start) * f.motion_speed > clip.duration + 0.05:
                issues.append(ValidationIssue(code="MOTION_TOO_SHORT", message=f"{f.id} outlasts motion clip {clip.name}", formation_id=f.id, details={"formation_seconds": round(f.end - f.start, 3), "available_seconds": round(clip.duration / f.motion_speed, 3)}))
        missing = expected - set(f.positions)
        if missing:
            issues.append(ValidationIssue(code="MISSING_DANCER", message=f"{f.id} is missing dancer positions", formation_id=f.id, dancer_ids=sorted(missing)))
        for dancer_id, p in f.positions.items():
            if not (0 <= p.x <= c.stage_width and 0 <= p.y <= c.stage_depth):
                issues.append(ValidationIssue(code="OUT_OF_BOUNDS", message=f"{dancer_id} is outside the stage in {f.id}", formation_id=f.id, dancer_ids=[dancer_id], details={"x": p.x, "y": p.y}))
        dancers = sorted(set(f.positions) & expected)
        for i, a_id in enumerate(dancers):
            for b_id in dancers[i + 1:]:
                dist = _distance(f.positions[a_id], f.positions[b_id])
                if dist + 1e-6 < c.min_spacing:
                    issues.append(ValidationIssue(code="MIN_SPACING", message=f"{a_id} and {b_id} are only {dist:.2f}m apart", formation_id=f.id, dancer_ids=[a_id, b_id], details={"distance": round(dist, 3), "required": c.min_spacing}))
    for index in range(1, len(formations)):
        previous, current = formations[index - 1], formations[index]
        transition_duration = max(0.0, current.start - previous.start)
        if current.start > previous.end + 0.05:
            issues.append(ValidationIssue(code="TIMELINE_GAP", message=f"Timeline gap before {current.id}", formation_id=current.id, details={"gap": round(current.start - previous.end, 3)}))
        shared = sorted(set(previous.positions) & set(current.positions) & expected)
        max_distance = max((_distance(previous.positions[d], current.positions[d]) for d in shared), default=0)
        if max_distance > c.max_speed * transition_duration + 1e-6:
            issues.append(ValidationIssue(code="INSUFFICIENT_TIME", message=f"Transition to {current.id} needs more time", formation_id=current.id, details={"distance": round(max_distance, 3), "available_seconds": round(transition_duration, 3), "max_speed": c.max_speed}))
        if max_distance > max(c.stage_width, c.stage_depth) * 0.8:
            issues.append(ValidationIssue(code="EXCESSIVE_DISTANCE", message=f"Transition to {current.id} contains excessive travel", formation_id=current.id, details={"distance": round(max_distance, 3)}))
        step_count = max(2, int(max(transition_duration, 0.25) * sample_hz))
        for step in range(1, step_count):
            alpha = step / step_count
            t = previous.start + transition_duration * alpha
            interpolated = {d: (previous.positions[d].x + (current.positions[d].x - previous.positions[d].x) * alpha, previous.positions[d].y + (current.positions[d].y - previous.positions[d].y) * alpha) for d in shared}
            samples += 1
            for i, a_id in enumerate(shared):
                for b_id in shared[i + 1:]:
                    ax, ay = interpolated[a_id]; bx, by = interpolated[b_id]
                    dist = math.hypot(ax - bx, ay - by)
                    if dist + 1e-6 < c.min_spacing:
                        issues.append(ValidationIssue(code="PATH_COLLISION", message=f"{a_id} and {b_id} conflict during transition", formation_id=current.id, dancer_ids=[a_id, b_id], time=round(t, 3), details={"distance": round(dist, 3), "required": c.min_spacing}))
                        break
                else:
                    continue
                break
    # Keep the response useful rather than flooding the agent/UI with duplicate sampled collisions.
    deduped = []
    seen = set()
    for issue in issues:
        key = (issue.code, issue.formation_id, tuple(issue.dancer_ids))
        if key not in seen:
            seen.add(key); deduped.append(issue)
    return ValidationResult(valid=not deduped, issues=deduped, samples_checked=samples)

