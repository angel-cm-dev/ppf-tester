"""Ritmos para probar el kit en contexto (notas General MIDI)."""
from __future__ import annotations

import threading
import time

# Cada patrón: (pasos por compás, subdivisión por negra, lista de (paso, nota, velocidad))
K, S, CH, OH, PH, RD, CR, T1, T2, T3 = 36, 38, 42, 46, 44, 51, 49, 48, 45, 43


def _hh(n, step, vel_on=90, vel_off=60, note=CH):
    return [(i, note, vel_on if i % (2 * step) == 0 else vel_off) for i in range(0, n, step)]


T4 = 41   # tom de piso
B2, SS, RB = 35, 37, 53


def _shuffle(n, note=RD, v1=95, v2=65):
    """Ride con figura de tresillo (12 pasos por compás)."""
    return [(i, note, v1 if i % 3 == 0 else v2) for i in range(n) if i % 3 != 1]


PATRONES = {
    "Balada 4/4": (16, 4, [(0, K, 110), (8, K, 95), (10, K, 70), (4, S, 100), (12, S, 105)] + _hh(16, 2, 85, 55)),
    "Worship 4/4 (toms)": (16, 4, [(0, K, 115), (6, K, 85), (8, K, 105), (4, T2, 95), (12, S, 110), (0, CR, 100),
                                   (10, T3, 90), (14, T1, 80)] + _hh(16, 4, 90, 90, RD)),
    "Worship 6/8": (12, 3, [(0, K, 110), (6, K, 90), (6, S, 100), (0, CR, 100)] + _hh(12, 1, 80, 50, RD)),
    "Worship 6/8 (build)": (12, 3, [(0, K, 115), (3, K, 80), (6, S, 110), (9, K, 85), (11, S, 60)] + _hh(12, 1, 95, 70)),
    "Balada 12/8": (12, 3, [(0, K, 110), (6, S, 105), (8, K, 75), (9, K, 90)] + _hh(12, 1, 85, 55)),
    "Gospel shuffle": (12, 3, [(0, K, 110), (5, K, 70), (6, S, 110), (8, K, 85), (11, S, 50)] + _shuffle(12)),
    "Pop 4/4": (16, 4, [(0, K, 115), (6, K, 90), (8, K, 105), (4, S, 110), (12, S, 110), (15, S, 45)] + _hh(16, 2, 95, 65)),
    "Rock 4/4": (16, 4, [(0, K, 120), (8, K, 115), (10, K, 100), (4, S, 120), (12, S, 120), (0, CR, 110)] + _hh(16, 2, 110, 90, OH)),
    "Bossa / Latin": (16, 4, [(0, K, 100), (3, K, 80), (8, K, 100), (11, K, 80), (0, SS, 90), (3, SS, 85), (6, SS, 90),
                              (10, SS, 85), (13, SS, 90)] + _hh(16, 2, 75, 55)),
    "Fill de toms": (16, 4, [(i, [T1, T1, T1, T1, T2, T2, T2, T2, T3, T3, T3, T3, T4, T4, S, S][i], 85 + i * 2) for i in range(16)]
                     + [(0, K, 110), (8, K, 100)]),
    "Redoble de toms": (16, 4, [(i, [T1, T1, T2, T2, T3, T3, T3, T3][i // 2], 80 + i * 3) for i in range(16)] + [(0, K, 110)]),
    "Dinámica (pp → ff)": (16, 4, [(i, S, 10 + i * 7) for i in range(16)]),
}

FAMILIAS = {K: [36, 35], B2: [35, 36], SS: [37, 38], RB: [53, 51], T4: [41, 43, 45], S: [38, 40, 37], CH: [42, 44, 46], OH: [46, 42], PH: [44, 42], RD: [51, 59, 53, 49],
            CR: [49, 57, 55, 52, 51], T1: [48, 50, 47, 45], T2: [45, 47, 43, 41], T3: [43, 41, 45]}


def adaptar(nota: int, disponibles: set[int]) -> int | None:
    for n in FAMILIAS.get(nota, [nota]):
        if n in disponibles:
            return n
    return nota if nota in disponibles else None


class Reproductor:
    """Toca un patrón en bucle en un hilo aparte. 'tocar(nota, vel)' debe ser thread-safe."""

    def __init__(self, tocar, disponibles: set[int]):
        self.tocar = tocar
        self.disp = disponibles
        self._stop = threading.Event()
        self.th = None

    def start(self, nombre: str, bpm: float, swing: float = 0.0, metronomo=None):
        """swing 0..0.6 retrasa los contratiempos; metronomo(acento: bool) suena en cada pulso."""
        self.stop()
        pasos, sub, notas = PATRONES[nombre]
        evs = {}
        for st, n, v in notas:
            m = adaptar(n, self.disp)
            if m is not None:
                evs.setdefault(st, []).append((m, v))
        dt = 60.0 / bpm / sub
        self._stop.clear()

        def run():
            t0 = time.perf_counter()
            i = 0
            while not self._stop.is_set():
                st = i % pasos
                if metronomo is not None and st % sub == 0:
                    metronomo(st == 0)
                for n, v in evs.get(st, []):
                    self.tocar(n, v)
                i += 1
                # swing: el siguiente paso impar llega un poco tarde
                extra = swing * dt if (i % 2 == 1 and sub % 2 == 0) else 0.0
                wait = t0 + i * dt + extra - time.perf_counter()
                if wait > 0:
                    self._stop.wait(wait)

        self.th = threading.Thread(target=run, daemon=True)
        self.th.start()

    def stop(self):
        self._stop.set()
        if self.th:
            self.th.join(timeout=1)
            self.th = None


def click(acento: bool, sr: int = 44100):
    """Sonido del metrónomo (estéreo float32)."""
    import numpy as np
    n = int(sr * 0.05)
    t = np.arange(n) / sr
    f = 1800 if acento else 1200
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 90) * (0.55 if acento else 0.4)
    return np.stack([y, y], axis=1).astype(np.float32)
