"""Procesado de audio para baterías: EQ, transient shaper, compresor, saturación."""
from __future__ import annotations

import numpy as np
from sig import lfilter, resample as _resample


# ------------------------------------------------------------------ EQ (RBJ)
def _norm(b, a):
    b, a = np.asarray(b, float), np.asarray(a, float)
    return b / a[0], a / a[0]


def hpf(x, sr, fc, q=0.707):
    w = 2 * np.pi * fc / sr; al = np.sin(w) / (2 * q); c = np.cos(w)
    b, a = _norm([(1 + c) / 2, -(1 + c), (1 + c) / 2], [1 + al, -2 * c, 1 - al])
    return lfilter(b, a, x, axis=0)


def lpf(x, sr, fc, q=0.707):
    fc = min(fc, sr * 0.45)
    w = 2 * np.pi * fc / sr; al = np.sin(w) / (2 * q); c = np.cos(w)
    b, a = _norm([(1 - c) / 2, 1 - c, (1 - c) / 2], [1 + al, -2 * c, 1 - al])
    return lfilter(b, a, x, axis=0)


def peak(x, sr, fc, gain_db, q=1.0):
    if abs(gain_db) < 0.05:
        return x
    A = 10 ** (gain_db / 40); w = 2 * np.pi * min(fc, sr * 0.45) / sr; al = np.sin(w) / (2 * q); c = np.cos(w)
    b, a = _norm([1 + al * A, -2 * c, 1 - al * A], [1 + al / A, -2 * c, 1 - al / A])
    return lfilter(b, a, x, axis=0)


def shelf(x, sr, fc, gain_db, high=True):
    if abs(gain_db) < 0.05:
        return x
    A = 10 ** (gain_db / 40); w = 2 * np.pi * min(fc, sr * 0.45) / sr; c = np.cos(w); s = np.sin(w)
    al = s / 2 * np.sqrt(2); sq = 2 * np.sqrt(A) * al
    if high:
        b = [A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq)]
        a = [(A + 1) - (A - 1) * c + sq, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sq]
    else:
        b = [A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq)]
        a = [(A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq]
    b, a = _norm(b, a)
    return lfilter(b, a, x, axis=0)


# ------------------------------------------------------------ envolventes
def _env(x, sr, ms):
    """Envolvente (seguidor de RMS con una constante de tiempo)."""
    m = np.sqrt(np.mean(x ** 2, axis=1)) if x.ndim > 1 else np.abs(x)
    a = np.exp(-1 / (sr * ms / 1000))
    return np.sqrt(np.maximum(lfilter([1 - a], [1, -a], m ** 2), 0)) + 1e-9


def transient(x, sr, amount):
    """amount > 0 realza el ataque; < 0 lo suaviza."""
    if abs(amount) < 0.01:
        return x
    fast, slow = _env(x, sr, 1.0), _env(x, sr, 25.0)
    ratio = np.clip(fast / slow, 0.25, 4.0)
    g = ratio ** (amount * 0.8)
    g = lfilter([0.05], [1, -0.95], g)          # suavizado anti-distorsión
    return x * g[:, None] if x.ndim > 1 else x * g


def compress(x, sr, ratio, thr_db, makeup=True):
    if ratio <= 1:
        return x
    pk = np.abs(x).max()
    if pk <= 0:
        return x
    env = _env(x, sr, 8.0)
    lvl = 20 * np.log10(env / pk)               # relativo al pico
    over = np.maximum(0, lvl - thr_db)
    gdb = -over * (1 - 1 / ratio)
    g = 10 ** (gdb / 20)
    y = x * g[:, None] if x.ndim > 1 else x * g
    if makeup:
        y = y * pk / max(np.abs(y).max(), 1e-9)
    return y


def saturate(x, drive):
    if drive <= 0:
        return x
    pk = np.abs(x).max()
    if pk <= 0:
        return x
    d = 1 + drive * 4
    y = np.tanh(d * x / pk) / np.tanh(d) * pk
    return (1 - drive) * x + drive * y


def to_rate(x, sr_in, sr_out=44100):
    if int(sr_in) == sr_out:
        return x
    return _resample(x, sr_in, sr_out)


# --------------------------------------------------------------- medidas
def rms_db(x, sr, ms=250):
    seg = x[: int(sr * ms / 1000)]
    v = np.sqrt(np.mean(seg ** 2)) if len(seg) else 0
    return 20 * np.log10(max(v, 1e-9))


def peak_db(x):
    return 20 * np.log10(max(float(np.abs(x).max()) if len(x) else 0, 1e-9))


def spectrum_db(x, sr, nbands=96, fmin=20, fmax=20000):
    m = x.mean(axis=1) if x.ndim > 1 else x
    m = m[: int(sr * 2)]
    if not len(m):
        return np.zeros(nbands), np.geomspace(fmin, fmax, nbands)
    X = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    edges = np.geomspace(fmin, fmax, nbands + 1)
    out = np.array([X[(f >= a) & (f < b)].mean() if np.any((f >= a) & (f < b)) else 0 for a, b in zip(edges, edges[1:])])
    db = 10 * np.log10(out + 1e-20)
    return db - db.max(), np.sqrt(edges[:-1] * edges[1:])
