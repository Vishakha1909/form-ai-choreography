import pytest

from app.formations import generate_positions
from app.models import ChoreographyPlan, Formation, Point, StageConstraints
from app.motion_library import motion_catalog
from app.validation import validate_plan


def formation(fid, start, positions):
    return Formation(id=fid, name=fid, start=start, end=start + 4, positions=positions, movement="travel", movement_description="test", rationale="test")


def test_generated_line_is_valid_on_demo_stage():
    c = StageConstraints(dancer_count=6, stage_width=12, stage_depth=8, min_spacing=1.2)
    plan = ChoreographyPlan(title="test", creative_direction="test", formations=[formation("F1", 0, generate_positions("line", c))])
    assert validate_plan(plan, c).valid


@pytest.mark.parametrize("kind", [
    "line", "v", "inverted_v", "circle", "semicircle", "diagonal",
    "two_rows", "two_columns", "staggered", "diamond", "box", "cross",
])
def test_every_formation_is_complete_and_valid_on_demo_stage(kind):
    c = StageConstraints(dancer_count=6, stage_width=12, stage_depth=8, min_spacing=1.2)
    positions = generate_positions(kind, c)
    assert set(positions) == {f"D{i}" for i in range(1, 7)}
    plan = ChoreographyPlan(title="test", creative_direction="test", formations=[formation("F1", 0, positions)])
    assert validate_plan(plan, c).valid


def test_detects_out_of_bounds_and_spacing():
    c = StageConstraints(dancer_count=3, stage_width=8, stage_depth=6, min_spacing=1.0)
    positions = {"D1": Point(x=-1, y=2), "D2": Point(x=3, y=3), "D3": Point(x=3.2, y=3)}
    result = validate_plan(ChoreographyPlan(title="x", creative_direction="x", formations=[formation("F1", 0, positions)]), c)
    assert {x.code for x in result.issues} >= {"OUT_OF_BOUNDS", "MIN_SPACING"}


def test_detects_crossing_paths_between_valid_endpoints():
    c = StageConstraints(dancer_count=3, stage_width=10, stage_depth=8, min_spacing=0.8, max_speed=10)
    start = {"D1": Point(x=2, y=4), "D2": Point(x=8, y=4), "D3": Point(x=5, y=7)}
    end = {"D1": Point(x=8, y=4), "D2": Point(x=2, y=4), "D3": Point(x=5, y=7)}
    plan = ChoreographyPlan(title="x", creative_direction="x", formations=[formation("F1", 0, start), formation("F2", 2, end)])
    result = validate_plan(plan, c)
    assert "PATH_COLLISION" in {x.code for x in result.issues}
    assert result.samples_checked > 0


def test_detects_insufficient_transition_time():
    c = StageConstraints(dancer_count=3, stage_width=10, stage_depth=8, min_spacing=0.5, max_speed=1)
    start = {"D1": Point(x=1, y=1), "D2": Point(x=2, y=2), "D3": Point(x=3, y=3)}
    end = {"D1": Point(x=9, y=1), "D2": Point(x=8, y=2), "D3": Point(x=7, y=3)}
    result = validate_plan(ChoreographyPlan(title="x", creative_direction="x", formations=[formation("F1", 0, start), formation("F2", 1, end)]), c)
    assert "INSUFFICIENT_TIME" in {x.code for x in result.issues}


def test_motion_library_ids_and_duration_are_deterministically_validated():
    c = StageConstraints(dancer_count=3, stage_width=10, stage_depth=8, min_spacing=0.5)
    positions = {"D1": Point(x=2, y=2), "D2": Point(x=5, y=2), "D3": Point(x=8, y=2)}
    catalog = motion_catalog()
    missing = validate_plan(ChoreographyPlan(title="x", creative_direction="x", formations=[formation("F1", 0, positions)]), c, motion_catalog=catalog)
    assert "MISSING_MOTION_CLIP" in {x.code for x in missing.issues}
    unknown_formation = formation("F1", 0, positions).model_copy(update={"motion_clip_id": "not-a-real-clip"})
    unknown = validate_plan(ChoreographyPlan(title="x", creative_direction="x", formations=[unknown_formation]), c, motion_catalog=catalog)
    assert "UNKNOWN_MOTION_CLIP" in {x.code for x in unknown.issues}
    clip_id = next(iter(catalog))
    too_long = unknown_formation.model_copy(update={"motion_clip_id": clip_id, "end": 30.0, "motion_speed": 1.0})
    duration = validate_plan(ChoreographyPlan(title="x", creative_direction="x", formations=[too_long]), c, motion_catalog=catalog)
    assert "MOTION_TOO_SHORT" in {x.code for x in duration.issues}

