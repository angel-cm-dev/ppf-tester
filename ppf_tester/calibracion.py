"""Calibrar la simulación con el teclado real.

Toca unas notas del kit en el PSR por MIDI, las graba, y compara su espectro y
su respuesta a la velocidad con la simulación. El resultado es una curva de
corrección (EQ) y una escala de velocidad que se aplican al motor de simulación.
"""
from __future__ import annotations

import numpy as np

import motor as M

BANDAS = [60, 125, 250, 500, 1000, 2000, 4000, 8000, 12000]
PREFERIDAS = [36, 38, 42, 45, 49, 51, 41, 46]


def _bandas_db(x: np.ndarray, sr: int = M.SR) -> np.ndarray:
    m = M.align_onset(x)
    m = (m.mean(axis=1) if m.ndim > 1 else m)[: int(sr * 0.8)]
    if len(m) < 256:
        return np.full(len(BANDAS), -120.0)
    X = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    out = []
    for c in BANDAS:
        sel = (f >= c / 1.41) & (f < c * 1.41)
        out.append(10 * np.log10(X[sel].mean() + 1e-20) if sel.any() else -120.0)
    return np.array(out)


def notas_para_calibrar(engine: M.Engine) -> list[int]:
    disp = sorted({n for _, _, lo, hi, _, _ in engine.voice.zones() for n in range(lo, min(hi, lo + 60) + 1)})
    elegidas = [n for n in PREFERIDAS if n in disp][:6]
    return elegidas or disp[:6]


def calibrar(engine: M.Engine, kit, port: int, canal: int, in_dev: int, log=lambda s: None) -> dict:
    """Devuelve {"eq": [(f, dB)...], "vel": escala, "detalle": [...], "notas": n}."""
    import midi_test
    notas = notas_para_calibrar(engine)
    vels = [45, 85, 120]
    waves_by_name = {w.name: w for w in engine.pack.waves.values()}
    log(f"Tocando {len(notas)} notas × {len(vels)} velocidades en el PSR…")
    hits, audio, sr = midi_test.run_test(kit, waves_by_name, port, canal, vels, in_dev, True, notas, log=log)
    if sr != M.SR:
        import dsp
    guardar_eq, guardar = engine.settings.cal_eq, engine.settings.cal_vel
    engine.settings.cal_eq, engine.settings.cal_vel = None, 1.0
    engine.invalidate()
    difs, pend_rec, pend_sim, detalle = [], [], [], []
    try:
        por_nota: dict[int, list] = {}
        for h in hits:
            if h.audio is None or h.latency_ms is None:
                continue
            rec = h.audio
            if sr != M.SR:
                rec = dsp.to_rate(rec, sr, M.SR)
            sim, _ = engine.render(h.note, h.vel)
            br, bs = _bandas_db(rec), _bandas_db(sim)
            d = br - bs
            d -= np.median(d)                       # solo la forma, no el volumen de la interfaz
            difs.append(d)
            por_nota.setdefault(h.note, []).append((h.vel, M.align_onset(rec), sim))
        for n, lst in por_nota.items():
            if len(lst) >= 2:
                lst.sort()
                (v0, r0, s0), (v1, r1, s1) = lst[0], lst[-1]
                rd = 20 * np.log10(max(np.abs(r1).max(), 1e-9) / max(np.abs(r0).max(), 1e-9))
                sd = 20 * np.log10(max(np.abs(s1).max(), 1e-9) / max(np.abs(s0).max(), 1e-9))
                if abs(sd) > 1:
                    pend_rec.append(rd)
                    pend_sim.append(sd)
                    detalle.append((n, rd, sd))
    finally:
        engine.settings.cal_eq, engine.settings.cal_vel = guardar_eq, guardar
        engine.invalidate()
    if not difs:
        raise RuntimeError("No llegó sonido del PSR. Revisa la voz en RIGHT 1, el canal MIDI y el cable de audio.")
    eq = np.clip(np.median(np.array(difs), axis=0), -12, 12)
    eq = np.convolve(np.pad(eq, 1, mode="edge"), [0.25, 0.5, 0.25], "valid")   # suavizar
    vel = float(np.clip(np.median(pend_rec) / np.median(pend_sim), 0.3, 2.0)) if pend_sim else 1.0
    return {"eq": [(f, round(float(g), 2)) for f, g in zip(BANDAS, eq)], "vel": round(vel, 3),
            "detalle": detalle, "notas": len({h.note for h in hits if h.latency_ms is not None})}
