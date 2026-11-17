from __future__ import annotations

import math
from pathlib import Path
import librosa
import numpy as np
from .models import AudioAnalysis, AudioFrame, MusicalSection


def _downsample(times: np.ndarray, values: np.ndarray, limit: int = 360) -> list[AudioFrame]:
    if len(values) == 0:
        return []
    indexes = np.linspace(0, len(values) - 1, min(limit, len(values)), dtype=int)
    peak = float(np.max(np.abs(values))) or 1.0
    return [AudioFrame(time=round(float(times[i]), 3), value=round(float(values[i]) / peak, 4)) for i in indexes]


def analyze_audio(path: Path, filename: str) -> AudioAnalysis:
    y, sr = librosa.load(path, sr=22050, mono=True, duration=45.0)
    if len(y) < sr:
        raise ValueError("Audio must be at least one second long")
    duration = float(librosa.get_duration(y=y, sr=sr))
    hop = 512
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    # Estimate pulse from onset-envelope autocorrelation. This avoids the
    # platform-sensitive Numba gufunc used by librosa.beat.beat_track on some
    # Windows builds while still deriving tempo and beats from measured audio.
    centered = onset - np.mean(onset)
    autocorrelation = np.correlate(centered, centered, mode="full")[len(centered) - 1:]
    min_lag = max(1, int(60 * sr / (200 * hop)))
    max_lag = min(len(autocorrelation) - 1, int(60 * sr / (60 * hop)))
    if max_lag > min_lag and np.any(autocorrelation[min_lag:max_lag + 1] > 0):
        beat_lag = min_lag + int(np.argmax(autocorrelation[min_lag:max_lag + 1]))
        tempo = 60 * sr / (hop * beat_lag)
    else:
        tempo = 120.0
    period = 60.0 / float(tempo)
    onset_times_all = librosa.frames_to_time(np.arange(len(onset)), sr=sr, hop_length=hop)
    early = np.flatnonzero(onset_times_all <= min(4.0, duration))
    anchor_index = int(early[np.argmax(onset[early])]) if len(early) else 0
    anchor = float(onset_times_all[anchor_index])
    beat_times = np.arange(anchor, duration, period)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    boundaries = librosa.segment.agglomerative(chroma, k=max(2, min(5, math.ceil(duration / 10))))
    boundary_times = sorted(set([0.0, *librosa.frames_to_time(boundaries, sr=sr, hop_length=hop).tolist(), duration]))
    energy_low, energy_high = np.quantile(rms, [0.33, 0.67])
    sections = []
    for i, (start, end) in enumerate(zip(boundary_times, boundary_times[1:])):
        mask = (frame_times >= start) & (frame_times < end)
        mean = float(np.mean(rms[mask])) if np.any(mask) else 0.0
        energy = "low" if mean <= energy_low else "high" if mean >= energy_high else "medium"
        sections.append(MusicalSection(start=round(start, 3), end=round(end, 3), label=f"Section {chr(65 + i)}", energy=energy, mean_rms=round(mean, 5), interpretation=f"Heuristic {energy}-energy region based on relative RMS; boundary estimated from chroma change."))
    waveform_hop = max(1, len(y) // 360)
    wave = np.array([np.max(np.abs(y[i:i + waveform_hop])) for i in range(0, len(y), waveform_hop)])
    wave_times = np.linspace(0, duration, len(wave))
    onset_times = librosa.frames_to_time(np.arange(len(onset)), sr=sr, hop_length=hop)
    return AudioAnalysis(filename=filename, duration=round(duration, 3), tempo=round(float(tempo), 2), beat_times=[round(float(x), 3) for x in beat_times], onset_envelope=_downsample(onset_times, onset), rms_envelope=_downsample(frame_times, rms), waveform=_downsample(wave_times, wave), sections=sections, notes=["Onset strength and RMS are measured with librosa; tempo is estimated from onset autocorrelation and beat timestamps form an onset-anchored pulse grid.", "Section boundaries and energy labels are heuristic interpretations, not ground-truth musical form.", "Analysis is limited to the first 45 seconds."])

