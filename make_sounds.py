#!/usr/bin/env python3
"""Generate the Bear-Net notification sound set for Stoat's web client.

The public stoatchat/for-web Docker images ship silent placeholder sounds
(the real ones live in a private brand repo). This script renders a matched
family of soft sine chimes and writes them as .ogg files over the fallback
placeholders, so a rebuilt image has audible notification sounds.

Usage: python3 make_sounds.py <output_dir>
Requires: numpy, ffmpeg on PATH.
message_sound.ogg is NOT touched (upstream ships a real one).
"""

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 48000


def tone(freq, dur, vol=0.5, decay=4.5, attack=0.035):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    w = np.sin(2 * np.pi * freq * t)  # pure sine - the "round" voice
    env = np.minimum(t / attack, 1) * np.exp(-t * decay)
    return vol * w * env


def render(notes, path, tail=0.45, peak=0.5):
    total = max(s + d for s, _, d, _ in notes) + tail
    buf = np.zeros(int(SR * total))
    for start, freq, dur, vol in notes:
        s = int(SR * start)
        x = tone(freq, dur, vol)
        buf[s : s + len(x)] += x
    buf = buf / max(1e-9, np.abs(buf).max()) * peak
    pcm = (buf * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


A4, D5, G5, G4, E4, F5s = 440.00, 587.33, 783.99, 392.00, 329.63, 739.99

SOUNDS = {
    # on/off logic: rising = something starts, falling = something stops
    "user_join_voice": dict(notes=[(0.0, A4, 0.55, 0.9), (0.13, D5, 0.70, 1.0)]),
    "user_leave_voice": dict(notes=[(0.0, D5, 0.55, 0.9), (0.13, A4, 0.70, 0.85)]),
    "mute": dict(notes=[(0.0, G4, 0.40, 1.0)], peak=0.45),
    "unmute": dict(notes=[(0.0, D5, 0.40, 1.0)], peak=0.45),
    "deafen": dict(notes=[(0.0, A4, 0.35, 0.9), (0.09, E4, 0.50, 1.0)], peak=0.45),
    "undeafen": dict(notes=[(0.0, E4, 0.35, 0.9), (0.09, A4, 0.50, 1.0)], peak=0.45),
    "ringtone_incoming": dict(
        notes=[(0.00, D5, 0.4, 0.9), (0.14, G5, 0.5, 1.0),
               (0.75, D5, 0.4, 0.9), (0.89, G5, 0.5, 1.0)],
        tail=0.5,
    ),
    "ringtone_outgoing": dict(
        notes=[(0.00, A4, 0.4, 0.8), (0.14, D5, 0.5, 0.9),
               (0.85, A4, 0.4, 0.8), (0.99, D5, 0.5, 0.9)],
        tail=0.5, peak=0.42,
    ),
    "stream_start": dict(notes=[(0.0, A4, 0.4, 0.85), (0.11, D5, 0.45, 0.9), (0.22, F5s, 0.6, 1.0)]),
    "stream_end": dict(notes=[(0.0, F5s, 0.4, 0.85), (0.11, D5, 0.45, 0.9), (0.22, A4, 0.6, 1.0)]),
    "stream_viewer_join": dict(notes=[(0.0, G5, 0.30, 1.0)], tail=0.3, peak=0.4),
    "stream_viewer_leave": dict(notes=[(0.0, D5, 0.30, 1.0)], tail=0.3, peak=0.4),
    "user_moved": dict(notes=[(0.0, D5, 0.30, 0.9), (0.09, G4, 0.45, 1.0)], peak=0.45),
}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, spec in SOUNDS.items():
            wav = Path(tmp) / f"{name}.wav"
            render(spec["notes"], wav, tail=spec.get("tail", 0.45), peak=spec.get("peak", 0.5))
            ogg = out / f"{name}.ogg"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                 "-c:a", "libvorbis", "-q:a", "4", str(ogg)],
                check=True,
            )
            print(f"wrote {ogg}")
    print(f"{len(SOUNDS)} sounds written to {out}")


if __name__ == "__main__":
    main()
