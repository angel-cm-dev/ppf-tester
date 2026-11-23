"""Set del teclado (varios packs a la vez) y comparación de dos versiones de un kit."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

import dsp
import modelos
from ppf_format import Pack, load_pack, note_name


# ------------------------------------------------------------------ set
@dataclass
class PackInfo:
    path: str
    titulo: str
    mb: float
    voces: list[str]
    tipos: list[str]
    ondas: int
    error: str = ""


def info(path: str) -> PackInfo:
    try:
        p = load_pack(path)
    except Exception as e:  # noqa: BLE001
        return PackInfo(path, os.path.basename(path), 0.0, [], [], 0, f"no se pudo leer: {e}")
    mb = sum(w.frames * w.channels * 2 for w in p.waves.values()) / 1e6
    return PackInfo(path, p.title, mb, [v.name for v in p.voices], [v.voice_type for v in p.voices], len(p.waves),
                    "; ".join(p.errors))


@dataclass
class EstadoSet:
    modelo: str
    total_mb: float
    memoria_mb: float
    estado: str          # OK | AVISO | ERROR
    texto: str
    sobran_mb: float


def estado_set(packs: list[PackInfo], modelo: str) -> EstadoSet:
    m = modelos.MODELOS[modelo]
    total = sum(p.mb for p in packs)
    libre = m.memoria_mb - total
    if total > m.memoria_mb:
        est, txt = "ERROR", f"No cabe: faltan {-libre:.1f} MB. Quita un pack o reduce alguno con «Mejorar kit»."
    elif total > m.memoria_mb * 0.9:
        est, txt = "AVISO", f"Cabe justo: quedan {libre:.1f} MB libres."
    else:
        est, txt = "OK", f"Cabe todo: quedan {libre:.1f} MB libres ({libre / m.memoria_mb * 100:.0f} %)."
    return EstadoSet(m.nombre, total, m.memoria_mb, est, txt, libre)


def que_quitar(packs: list[PackInfo], modelo: str) -> list[PackInfo]:
    """Sugerencia: los packs más grandes que habría que quitar para que entre el resto."""
    m = modelos.MODELOS[modelo]
    total = sum(p.mb for p in packs)
    fuera = []
    for p in sorted(packs, key=lambda p: -p.mb):
        if total <= m.memoria_mb:
            break
        fuera.append(p)
        total -= p.mb
    return fuera


# ------------------------------------------------------------------ comparar versiones
@dataclass
class DifNota:
    nota: int
    estado: str                    # igual | cambiada | nueva | quitada
    cambios: list[str] = field(default_factory=list)


def _notas(pack: Pack) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not pack.voices:
        return out
    v = pack.voices[0]
    for el, kb, lo, hi, vlo, vhi in v.zones():
        for n in range(lo, hi + 1):
            d = out.setdefault(n, {"capas": [], "el": el})
            d["capas"].append((vlo, vhi, tuple(s.wave_uid for s in kb.samples)))
    for n, d in out.items():
        d["capas"].sort()
        uid = d["capas"][-1][2][0]
        w = pack.waves.get(uid)
        d["fuerte"] = w
        d["uids"] = {u for _, _, us in d["capas"] for u in us}
        d["mb"] = sum(pack.waves[u].frames * 2 for u in d["uids"] if u in pack.waves) / 1e6
    return out


def _nivel(w) -> float:
    return dsp.rms_db(w.samples, w.rate) if w is not None and len(w.samples) else -120.0


def comparar(a: Pack, b: Pack) -> tuple[list[DifNota], dict]:
    """Diferencias de B respecto de A (A = versión anterior, B = nueva)."""
    na, nb = _notas(a), _notas(b)
    difs = []
    for n in sorted(set(na) | set(nb)):
        if n not in nb:
            difs.append(DifNota(n, "quitada", ["la tecla ya no suena"]))
            continue
        if n not in na:
            w = nb[n]["fuerte"]
            difs.append(DifNota(n, "nueva", [f"«{w.name if w else '?'}» · {len(nb[n]['capas'])} capa(s)"]))
            continue
        x, y = na[n], nb[n]
        c = []
        if len(x["capas"]) != len(y["capas"]):
            c.append(f"capas {len(x['capas'])} → {len(y['capas'])}")
        elif [(lo, hi) for lo, hi, _ in x["capas"]] != [(lo, hi) for lo, hi, _ in y["capas"]]:
            c.append("rangos de velocidad distintos")
        wa, wb = x["fuerte"], y["fuerte"]
        if (wa.uid if wa else None) != (wb.uid if wb else None):
            if wa is not None and wb is not None and wa.name != wb.name:
                c.append(f"muestra «{wa.name}» → «{wb.name}»")
            dl = _nivel(wb) - _nivel(wa)
            if abs(dl) >= 0.5:
                c.append(f"nivel {dl:+.1f} dB")
            if wa is not None and wb is not None and abs(wb.duration - wa.duration) >= 0.05:
                c.append(f"duración {wa.duration:.2f} → {wb.duration:.2f} s")
            if wa is not None and wb is not None:
                ca, cb = _brillo(wa), _brillo(wb)
                if abs(cb - ca) / max(ca, 1) > 0.08:
                    c.append(f"brillo {_hz(ca)} → {_hz(cb)}")
            if not c:
                c.append("audio procesado")
        ea, eb = x["el"], y["el"]
        for attr, nom, fmt in (("tune_coarse", "afinación", "{:+d} st"), ("volume", "volumen", "{:+.1f} dB"),
                               ("pan", "paneo", "{:+.0f}"), ("alternate_group", "grupo de corte", "{}")):
            va, vb = getattr(ea, attr), getattr(eb, attr)
            if va != vb:
                c.append(f"{nom} {fmt.format(va)} → {fmt.format(vb)}")
        difs.append(DifNota(n, "cambiada" if c else "igual", c))
    mba = sum(w.frames * w.channels * 2 for w in a.waves.values()) / 1e6
    mbb = sum(w.frames * w.channels * 2 for w in b.waves.values()) / 1e6
    tot = {"mb_a": mba, "mb_b": mbb, "nuevas": sum(d.estado == "nueva" for d in difs),
           "quitadas": sum(d.estado == "quitada" for d in difs), "cambiadas": sum(d.estado == "cambiada" for d in difs),
           "iguales": sum(d.estado == "igual" for d in difs)}
    return difs, tot


def _hz(f: float) -> str:
    return f"{f / 1000:.1f} kHz" if f >= 1000 else f"{f:.0f} Hz"


def _brillo(w) -> float:
    x = w.samples.mean(axis=1)[: int(w.rate * 0.3)]
    if len(x) < 256:
        return 0.0
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / w.rate)
    return float((f * X).sum() / (X.sum() + 1e-12))


def informe_html(difs: list[DifNota], tot: dict, nombre_a: str, nombre_b: str, colores: dict) -> str:
    col = {"nueva": colores["OK"], "quitada": colores["ERROR"], "cambiada": colores["AVISO"], "igual": colores["mut"]}
    filas = "".join(
        f"<tr><td style='padding:3px 12px 3px 0; font-weight:700'>{note_name(d.nota)}</td>"
        f"<td style='padding-right:12px; color:{col[d.estado]}'>{d.estado}</td><td>{', '.join(d.cambios)}</td></tr>"
        for d in difs if d.estado != "igual")
    cab = (f"<p><b>A</b> {nombre_a} · {tot['mb_a']:.2f} MB &nbsp;→&nbsp; <b>B</b> {nombre_b} · {tot['mb_b']:.2f} MB "
           f"({tot['mb_b'] - tot['mb_a']:+.2f} MB)</p>"
           f"<p style='color:{colores['mut']}'>{tot['cambiadas']} cambiadas · {tot['nuevas']} nuevas · {tot['quitadas']} quitadas · "
           f"{tot['iguales']} iguales</p>")
    return cab + (f"<table cellspacing=0>{filas}</table>" if filas else f"<p style='color:{colores['OK']}'>Los dos kits suenan igual.</p>")
