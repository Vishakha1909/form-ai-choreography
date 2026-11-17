"""Generate two original, copyright-safe rehearsal clips for FORM."""

from pathlib import Path

import numpy as np
from scipy.io import wavfile


SAMPLE_RATE = 44_100
DURATION = 30.0
RNG = np.random.default_rng(20261117)


def envelope(length: int, decay: float) -> np.ndarray:
    return np.exp(-np.arange(length) / (SAMPLE_RATE * decay))


def add_tone(track: np.ndarray, start: float, duration: float, frequency: float, volume: float,
             attack: float = 0.01, release: float = 0.08) -> None:
    begin = int(start * SAMPLE_RATE)
    count = min(int(duration * SAMPLE_RATE), len(track) - begin)
    if count <= 0:
        return
    time = np.arange(count) / SAMPLE_RATE
    shape = np.ones(count)
    attack_samples = min(int(attack * SAMPLE_RATE), count)
    release_samples = min(int(release * SAMPLE_RATE), count)
    if attack_samples:
        shape[:attack_samples] = np.linspace(0, 1, attack_samples)
    if release_samples:
        shape[-release_samples:] *= np.linspace(1, 0, release_samples)
    track[begin:begin + count] += volume * shape * np.sin(2 * np.pi * frequency * time)


def add_drum(track: np.ndarray, start: float, kind: str, volume: float = 1.0) -> None:
    begin = int(start * SAMPLE_RATE)
    duration = {"kick": 0.28, "snare": 0.18, "hat": 0.07, "tabla_low": 0.22, "tabla_high": 0.12}[kind]
    count = min(int(duration * SAMPLE_RATE), len(track) - begin)
    if count <= 0:
        return
    time = np.arange(count) / SAMPLE_RATE
    if kind == "kick":
        phase = 2 * np.pi * (62 * time + 46 * time * np.exp(-time * 22))
        sound = np.sin(phase) * envelope(count, 0.09)
    elif kind == "snare":
        sound = (0.75 * RNG.normal(size=count) + 0.25 * np.sin(2 * np.pi * 185 * time)) * envelope(count, 0.055)
    elif kind == "hat":
        sound = RNG.normal(size=count) * envelope(count, 0.018)
    elif kind == "tabla_low":
        phase = 2 * np.pi * (105 * time + 35 * time * np.exp(-time * 28))
        sound = np.sin(phase) * envelope(count, 0.075)
    else:
        sound = (np.sin(2 * np.pi * 330 * time) + 0.3 * RNG.normal(size=count)) * envelope(count, 0.035)
    track[begin:begin + count] += volume * sound


def classical_test() -> np.ndarray:
    track = np.zeros(int(DURATION * SAMPLE_RATE), dtype=np.float64)
    # A gentle Sa-Pa drone gives the test a classical tonal center.
    for start in np.arange(0, DURATION, 2.0):
        add_tone(track, start, 2.05, 146.83, 0.075, attack=0.12, release=0.20)
        add_tone(track, start, 2.05, 220.00, 0.045, attack=0.12, release=0.20)

    beat = 0.5  # 120 BPM, grouped as an eight-count cycle.
    scale = [293.66, 329.63, 392.00, 440.00, 392.00, 349.23, 329.63, 293.66]
    for index, start in enumerate(np.arange(0, DURATION, beat)):
        count = index % 8
        section_gain = 0.72 if start < 10 else (1.0 if start < 20 else 1.18)
        # A short high stroke on every count keeps the measured pulse explicit;
        # low strokes on 1 and 5 preserve the eight-count phrasing.
        add_drum(track, start, "tabla_high", 0.43 * section_gain)
        if count in (0, 4):
            add_drum(track, start, "tabla_low", 0.34 * section_gain)
        if start >= 10 and count in (2, 6):
            add_drum(track, start + beat / 2, "tabla_high", 0.20 * section_gain)
        add_tone(track, start, 0.34, scale[count], 0.075 * section_gain, attack=0.015, release=0.10)
    # Audible transition markers at section boundaries.
    for transition in (10.0, 20.0):
        for offset, frequency in enumerate((293.66, 392.0, 523.25)):
            add_tone(track, transition + offset * 0.12, 0.45, frequency, 0.13, release=0.20)
    return track


def hiphop_test() -> np.ndarray:
    track = np.zeros(int(DURATION * SAMPLE_RATE), dtype=np.float64)
    beat = 60 / 92  # 92 BPM.
    bass_notes = [55.0, 55.0, 65.41, 49.0]
    for index, start in enumerate(np.arange(0, DURATION, beat)):
        bar_beat = index % 4
        section_gain = 0.68 if start < 8 else (1.0 if start < 20 else 1.15)
        if bar_beat in (0, 2):
            add_drum(track, start, "kick", 0.50 * section_gain)
        if bar_beat in (1, 3):
            add_drum(track, start, "snare", 0.28 * section_gain)
        add_drum(track, start, "hat", 0.095 * section_gain)
        if start >= 8:
            add_drum(track, start + beat / 2, "hat", 0.07 * section_gain)
        add_tone(track, start, beat * 0.82, bass_notes[(index // 4) % 4], 0.20 * section_gain,
                 attack=0.01, release=0.12)
        if start >= 20 and bar_beat in (0, 2):
            add_tone(track, start, beat * 0.45, 220 * (2 ** ((index % 8) / 12)), 0.08,
                     attack=0.005, release=0.08)
    # Brief drop before each new section makes segmentation easy to see.
    for center in (8.0, 20.0):
        left = int((center - 0.18) * SAMPLE_RATE)
        right = int(center * SAMPLE_RATE)
        track[left:right] *= np.linspace(1, 0.05, right - left)
    return track


def write_track(path: Path, track: np.ndarray) -> None:
    peak = max(float(np.max(np.abs(track))), 1e-9)
    samples = np.int16(np.clip(track / peak * 0.88, -1, 1) * 32767)
    wavfile.write(path, SAMPLE_RATE, samples)


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "test_audio"
    output.mkdir(exist_ok=True)
    # FORM intentionally reports the strongly accented half-time pulse (~60 BPM)
    # while the percussion contains 120-BPM subdivisions.
    write_track(output / "form_classical_adavu_test_60bpm.wav", classical_test())
    write_track(output / "form_hiphop_test_92bpm.wav", hiphop_test())
    print(f"Created two 30-second WAV files in {output}")


if __name__ == "__main__":
    main()
