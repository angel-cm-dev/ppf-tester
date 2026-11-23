"""Filtros y convolución con numpy puro (sustituye a scipy.signal para que el
ejecutable pese poco)."""
from __future__ import annotations

import numpy as np

_H_CACHE: dict = {}


def _nfft(n: int) -> int:
    return 1 << max(1, int(n - 1).bit_length())


def fftconvolve(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Convolución completa a lo largo del eje 0 (x puede ser 1D o 2D)."""
    x = np.asarray(x, float)
    h = np.asarray(h, float)
    n = x.shape[0] + h.shape[0] - 1
    N = _nfft(n)
    X = np.fft.rfft(x, N, axis=0)
    H = np.fft.rfft(h, N, axis=0)
    if x.ndim > 1 and h.ndim == 1:
        H = H[:, None]
    return np.fft.irfft(X * H, N, axis=0)[:n]


def _decay_len(a: np.ndarray) -> int:
    nz = [k for k in range(1, len(a)) if a[k] != 0]
    if not nz:
        return 1
    if len(nz) == 1:
        r = abs(a[nz[0]]) ** (1 / nz[0])
    else:
        r = float(np.max(np.abs(np.roots(a))))
    if r >= 1:
        return 1 << 30
    return int(np.ceil(np.log(1e-10) / np.log(r))) + len(a)


def impulse(b, a, length: int) -> np.ndarray:
    """Respuesta al impulso de un filtro IIR (b, a), recursiva por bloques."""
    b = np.asarray(b, float) / a[0]
    a = np.asarray(a, float) / a[0]
    key = (tuple(np.round(b, 15)), tuple(np.round(a, 15)), length)
    if key in _H_CACHE:
        return _H_CACHE[key]
    h = np.zeros(length)
    h[:min(len(b), length)] = b[:length]
    taps = [(k, a[k]) for k in range(1, len(a)) if a[k] != 0]
    if taps:
        D = min(k for k, _ in taps)
        if D == 1:
            for i in range(1, length):
                acc = h[i]
                for k, c in taps:
                    if i >= k:
                        acc -= c * h[i - k]
                h[i] = acc
        else:
            for i in range(D, length, D):
                j = min(i + D, length)
                blk = h[i:j].copy()
                for k, c in taps:
                    s0 = i - k
                    if j - k > 0:
                        lo = max(s0, 0)
                        blk[lo - s0:] -= c * h[lo:j - k]
                h[i:j] = blk
    if len(_H_CACHE) > 64:
        _H_CACHE.clear()
    _H_CACHE[key] = h
    return h


def lfilter(b, a, x, axis=0):
    """Equivalente a scipy.signal.lfilter (condiciones iniciales cero) sobre el eje 0."""
    x = np.asarray(x, float)
    n = x.shape[0]
    if n == 0:
        return x.copy()
    a = np.atleast_1d(np.asarray(a, float))
    b = np.atleast_1d(np.asarray(b, float))
    if len(a) == 1:
        h = b / a[0]
    else:
        L = min(n, _decay_len(a / a[0]))
        h = impulse(b, a, L)
    return fftconvolve(x, h)[:n]


def resample(x: np.ndarray, sr_in: float, sr_out: float) -> np.ndarray:
    """Cambio de frecuencia de muestreo por FFT (eje 0)."""
    x = np.asarray(x, float)
    n = x.shape[0]
    m = int(round(n * sr_out / sr_in))
    if m == n or n == 0:
        return x.copy()
    pad = int(0.05 * sr_in)            # evita que el final se mezcle con el inicio
    xp = np.concatenate([x, np.zeros((pad,) + x.shape[1:])], axis=0)
    mp = int(round(xp.shape[0] * sr_out / sr_in))
    X = np.fft.rfft(xp, axis=0)
    Y = np.zeros((mp // 2 + 1,) + X.shape[1:], complex)
    k = min(len(X), len(Y))
    Y[:k] = X[:k]
    return np.fft.irfft(Y, mp, axis=0)[:m] * (mp / xp.shape[0])
