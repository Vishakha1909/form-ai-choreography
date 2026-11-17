"""Create a synthetic two-person rehearsal fixture from a local solo reference.

The second view is delayed by five frames so synchronization diagnosis has a
known, disclosed difference. This is for testing only, never presentation data.
"""

from collections import deque
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "adavus" / "raw" / "kvhAsLbOChc.mp4"
OUTPUT = ROOT / "data" / "test" / "ensemble_two_dancer_fixture.mp4"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(SOURCE))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open {SOURCE}")
    fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
    capture.set(cv2.CAP_PROP_POS_MSEC, 32_000)
    ok, first = capture.read()
    if not ok:
        raise RuntimeError("Could not read the source segment")
    height, width = first.shape[:2]
    pane_width = min(480, width)
    pane_height = round(height * pane_width / width)
    writer = cv2.VideoWriter(str(OUTPUT), cv2.VideoWriter_fourcc(*"mp4v"), fps, (pane_width * 2, pane_height))
    delay: deque[np.ndarray] = deque(maxlen=6)
    frame = first
    for _ in range(round(fps * 10)):
        resized = cv2.resize(frame, (pane_width, pane_height))
        delay.append(resized.copy())
        delayed = delay[0] if len(delay) == delay.maxlen else resized
        writer.write(np.hstack([resized, delayed]))
        ok, frame = capture.read()
        if not ok:
            break
    capture.release()
    writer.release()
    print(OUTPUT)


if __name__ == "__main__":
    main()
