from __future__ import annotations

import json
import time
from pathlib import Path
from app.models import AudioAnalysis, AudioFrame, MusicalSection, StageConstraints
from app.planner import plan_choreography


def analysis():
    return AudioAnalysis(filename="synthetic-evaluation-fixture", duration=30, tempo=120, beat_times=list(range(0, 30)), onset_envelope=[AudioFrame(time=0, value=0)], rms_envelope=[AudioFrame(time=0, value=0.5)], waveform=[AudioFrame(time=0, value=0)], sections=[MusicalSection(start=0, end=10, label="A", energy="low", mean_rms=.1, interpretation="fixture"), MusicalSection(start=10, end=20, label="B", energy="high", mean_rms=.8, interpretation="fixture"), MusicalSection(start=20, end=30, label="C", energy="medium", mean_rms=.4, interpretation="fixture")], notes=["Synthetic fixture; not measured audio."])


def main():
    cases = [
        ("baseline-6", StageConstraints(dancer_count=6)),
        ("three-dancers", StageConstraints(dancer_count=3)),
        ("ten-dancers", StageConstraints(dancer_count=10, stage_width=16)),
        ("compact-stage", StageConstraints(dancer_count=6, stage_width=8, stage_depth=6, min_spacing=.8)),
        ("strict-spacing", StageConstraints(dancer_count=6, stage_width=14, stage_depth=10, min_spacing=1.7)),
    ]
    rows = []
    for name, constraints in cases:
        start = time.perf_counter(); result = plan_choreography(analysis(), constraints)
        rows.append({"case": name, "valid": result.validation.valid, "attempts": result.attempts, "violations": [x.code for x in result.validation.issues], "latency_ms": round((time.perf_counter() - start) * 1000), "mode": result.execution_mode})
    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "fixture_disclosure": "Audio input is synthetic. Latency and validation results were measured in this run.", "pass_rate": sum(r["valid"] for r in rows) / len(rows), "cases": rows}
    Path("evaluation-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

