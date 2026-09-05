#!/usr/bin/env python3
"""Generate the built-in soundboard starter pack (Jason-approved set).

Usage: python3 make_effects.py <output_dir>
Requires: numpy, ffmpeg on PATH. Deterministic (seeded RNGs).
"""

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 48000


def write_wav(path, buf, peak=0.65):
    buf = buf / max(1e-9, np.abs(buf).max()) * peak
    pcm = (buf * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def t_axis(dur):
    return np.linspace(0, dur, int(SR * dur), endpoint=False)


def env_adsr(n, a, d, s_lvl, r):
    e = np.ones(n) * s_lvl
    a_n, d_n, r_n = int(SR * a), int(SR * d), int(SR * r)
    e[:a_n] = np.linspace(0, 1, a_n)
    e[a_n : a_n + d_n] = np.linspace(1, s_lvl, d_n)
    e[-r_n:] *= np.linspace(1, 0, r_n)
    return e


def saw_stack(freq_arr, t, harmonics=8):
    out = np.zeros_like(t)
    ph = 2 * np.pi * np.cumsum(freq_arr) / SR
    for h in range(1, harmonics + 1):
        out += np.sin(h * ph) / h
    return out


def airhorn():
    dur = 1.4
    t = t_axis(dur)
    f0 = 410 * (1 + 0.06 * np.exp(-t * 18))
    f0 = f0 * (1 + 0.012 * np.sin(2 * np.pi * 6.5 * t))
    sig = saw_stack(f0, t, 10) + 0.5 * saw_stack(f0 * 1.005, t, 6)
    return sig * env_adsr(len(t), 0.015, 0.05, 0.9, 0.25), 0.7


def rimshot():
    total = 1.6
    buf = np.zeros(int(SR * total))
    rng = np.random.default_rng(7)

    def hit_drum(at, f_start, f_end, dur, vol):
        t = t_axis(dur)
        f = np.linspace(f_start, f_end, len(t))
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22) * vol
        x += rng.standard_normal(len(t)) * np.exp(-t * 40) * vol * 0.35
        s = int(SR * at)
        buf[s : s + len(x)] += x

    def hit_snare(at, dur, vol):
        t = t_axis(dur)
        x = rng.standard_normal(len(t)) * np.exp(-t * 28) * vol
        x += np.sin(2 * np.pi * 190 * t) * np.exp(-t * 35) * vol * 0.6
        s = int(SR * at)
        buf[s : s + len(x)] += x

    def cymbal(at, dur, vol):
        t = t_axis(dur)
        n = np.diff(rng.standard_normal(len(t)), prepend=0)
        s = int(SR * at)
        buf[s : s + len(t)] += n * np.exp(-t * 4.5) * vol

    hit_drum(0.00, 180, 90, 0.25, 1.0)
    hit_drum(0.16, 150, 75, 0.25, 1.0)
    hit_snare(0.16, 0.2, 0.5)
    cymbal(0.34, 1.2, 0.8)
    return buf, 0.7


def sad_trombone():
    total = 2.6
    buf = np.zeros(int(SR * total))
    notes = [
        (0.00, 233.08, 0.42, 0),
        (0.45, 220.00, 0.42, 0),
        (0.90, 207.65, 0.42, 0),
        (1.35, 196.00, 1.15, 1),
    ]
    for at, f, dur, last in notes:
        t = t_axis(dur)
        fa = np.full(len(t), float(f))
        if last:
            fa = f * (1 - 0.06 * np.clip((t - 0.35) / 0.8, 0, 1))
            fa = fa * (1 + 0.02 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1))
        x = saw_stack(fa, t, 7)
        e = env_adsr(len(t), 0.04, 0.05, 0.85, 0.12 if not last else 0.5)
        s = int(SR * at)
        buf[s : s + len(x)] += x * e
    return buf, 0.6


def crickets():
    total = 3.0
    buf = np.zeros(int(SR * total))
    rng = np.random.default_rng(3)
    chirp_t = 0.0
    while chirp_t < total - 0.3:
        for p in range(4):
            at = chirp_t + p * 0.028
            t = t_axis(0.02)
            x = np.sin(2 * np.pi * 4300 * t) * np.sin(np.pi * t / 0.02) ** 2 * 0.8
            s = int(SR * at)
            buf[s : s + len(x)] += x
        chirp_t += 0.42 + rng.uniform(-0.05, 0.05)
    return buf, 0.35


def tada():
    total = 1.8
    buf = np.zeros(int(SR * total))

    def brass(at, f, dur, vol):
        t = t_axis(dur)
        x = saw_stack(np.full(len(t), float(f)), t, 6)
        e = env_adsr(len(t), 0.02, 0.06, 0.8, min(0.4, dur * 0.6))
        s = int(SR * at)
        buf[s : s + len(x)] += x * e * vol

    brass(0.00, 392.00, 0.22, 0.8)
    for f, v in [(523.25, 1.0), (659.25, 0.85), (783.99, 0.9), (1046.5, 0.6)]:
        brass(0.22, f, 1.4, v)
    t = t_axis(1.2)
    n = np.diff(np.random.default_rng(11).standard_normal(len(t)), prepend=0)
    s = int(SR * 0.22)
    buf[s : s + len(t)] += n * np.exp(-t * 6) * 0.25
    return buf, 0.65


def drumroll():
    total = 2.6
    buf = np.zeros(int(SR * total))
    rng = np.random.default_rng(5)
    at = 0.0
    while at < 1.9:
        t = t_axis(0.06)
        vol = 0.25 + 0.75 * (at / 1.9)
        x = rng.standard_normal(len(t)) * np.exp(-t * 60) * vol
        x += np.sin(2 * np.pi * 185 * t) * np.exp(-t * 70) * vol * 0.4
        s = int(SR * at)
        buf[s : s + len(x)] += x
        at += 0.055 - 0.012 * (at / 1.9)
    t = t_axis(0.7)
    n = np.diff(rng.standard_normal(len(t)), prepend=0)
    s = int(SR * 1.9)
    buf[s : s + len(t)] += n * np.exp(-t * 5) * 1.1
    return buf, 0.7


EFFECTS = {
    "airhorn": airhorn,
    "rimshot": rimshot,
    "sad_trombone": sad_trombone,
    "crickets": crickets,
    "tada": tada,
    "drumroll": drumroll,
}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in EFFECTS.items():
            buf, peak = fn()
            wav = Path(tmp) / f"{name}.wav"
            write_wav(wav, buf, peak)
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                 "-c:a", "libvorbis", "-q:a", "4", str(out / f"{name}.ogg")],
                check=True,
            )
            print(f"wrote {out / (name + '.ogg')}")


if __name__ == "__main__":
    main()
