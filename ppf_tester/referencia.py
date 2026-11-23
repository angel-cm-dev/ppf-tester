"""Comparar un kit con un kit de referencia: balance entre piezas y brillo."""
from __future__ import annotations

import numpy as np

import dsp
from mejora import NOMBRE_TIPO, clasificar
from ppf_format import Pack


def perfil(pack: Pack) -> dict[str, dict]:
    """Por tipo de pieza: nivel (dB, relativo al bombo o a la caja) y brillo (centroide espectral)."""
    if not pack.voices:
        return {}
    usos: dict[str, list[int]] = {}
    for el, kb, lo, hi, vlo, vhi in pack.voices[0].zones():
        if vhi < 100:
            continue                                 # solo la capa más fuerte
        uid = kb.samples[0].wave_uid
        usos.setdefault(uid, []).append(lo)
    tipos: dict[str, list] = {}
    for uid, notas in usos.items():
        w = pack.waves.get(uid)
        if w is None or not w.frames:
            continue
        t = clasificar(w.name, notas, w)
        x = w.samples
        m = x.mean(axis=1)[: int(w.rate * 1.5)]
        X = np.abs(np.fft.rfft(m * np.hanning(len(m)))) if len(m) > 64 else np.zeros(2)
        f = np.fft.rfftfreq(len(m), 1 / w.rate) if len(m) > 64 else np.zeros(2)
        cen = float((X * f).sum() / max(X.sum(), 1e-12))
        tipos.setdefault(t, []).append((dsp.rms_db(x, w.rate), cen, w.duration))
    out = {t: {"nivel": float(np.mean([v[0] for v in vs])), "brillo": float(np.mean([v[1] for v in vs])),
               "dur": float(np.mean([v[2] for v in vs])), "n": len(vs)} for t, vs in tipos.items()}
    ref = out.get("bombo") or out.get("caja")
    if ref:
        base = ref["nivel"]
        for v in out.values():
            v["rel"] = v["nivel"] - base
    else:
        for v in out.values():
            v["rel"] = 0.0
    return out


def comparar(mio: Pack, ref: Pack) -> list[dict]:
    a, b = perfil(mio), perfil(ref)
    filas = []
    for t in ("bombo", "caja", "tom", "hihat", "ride", "crash", "perc"):
        if t not in a and t not in b:
            continue
        fila = {"tipo": NOMBRE_TIPO[t], "mio": a.get(t), "ref": b.get(t), "consejos": []}
        if t in a and t in b:
            d = b[t]["rel"] - a[t]["rel"]
            if t not in ("bombo",) and abs(d) >= 2:
                fila["consejos"].append(f"{'sube' if d > 0 else 'baja'} {abs(d):.0f} dB respecto al bombo")
            br = (b[t]["brillo"] / max(a[t]["brillo"], 1) - 1) * 100
            if abs(br) >= 15:
                fila["consejos"].append(f"{'más' if br > 0 else 'menos'} brillo ({br:+.0f} %)")
            dd = b[t]["dur"] - a[t]["dur"]
            if abs(dd) > 0.4 and t in ("crash", "ride", "tom"):
                fila["consejos"].append(f"cola {'más larga' if dd > 0 else 'más corta'} ({dd:+.1f} s)")
        elif t in b:
            fila["consejos"].append("tu kit no tiene esta pieza")
        filas.append(fila)
    return filas
