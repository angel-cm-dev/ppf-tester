"""Puente entre la web app (JavaScript) y el núcleo de PPF Tester (Python en Pyodide).

Todo devuelve JSON (texto) o bytes, para pasarlo fácil al hilo de la interfaz.
"""
from __future__ import annotations

import io
import json
import struct

import numpy as np

import analisis
import compat
import demo
import estilos
import grooves
import importar_wav as I
import motor
import ppf_format as P

ESTADO: dict = {"pack": None, "engine": None, "voz": 0, "estilo": None}


def _bytes(data) -> bytes:
    """Bytes desde JavaScript (Uint8Array) o desde Python."""
    if hasattr(data, "to_bytes"):
        return data.to_bytes()
    return bytes(data)


def _disp() -> set[int]:
    e = ESTADO["engine"]
    if e is None:
        return set()
    return {n for _, _, lo, hi, _, _ in e.voice.zones() for n in range(lo, hi + 1)}


def _nombre_nota(n: int) -> str:
    return estilos.nombre_nota(n)


# ------------------------------------------------------------------ kit
def abrir_kit(data, nombre: str) -> str:
    pack = P.load_pack_bytes(_bytes(data), nombre)
    if not pack.voices:
        raise ValueError("El pack no tiene voces.")
    ESTADO["pack"] = pack
    return elegir_voz(0)


def elegir_voz(i: int) -> str:
    pack = ESTADO["pack"]
    v = pack.voices[int(i)]
    ESTADO["voz"] = int(i)
    ESTADO["engine"] = motor.Engine(pack, v)
    ESTADO["engine"].settings.humanizar = False
    notas = {}
    for el, kb, lo, hi, vlo, vhi in v.zones():
        for n in range(lo, min(hi, lo + 60) + 1):
            d = notas.setdefault(n, {"nota": n, "capas": 0, "muestra": ""})
            d["capas"] += 1
            w = pack.waves.get(kb.samples[0].wave_uid) if kb.samples else None
            if w is not None and vhi == 127:
                d["muestra"] = w.name
    lista = []
    for n in sorted(notas):
        d = notas[n]
        d["nombre"] = I.GM.get(n) or estilos.PERCUSION.get(n) or d["muestra"] or P.note_name(n)
        d["tecla"] = P.note_name(n)
        lista.append(d)
    mem = analisis.memory_bytes(pack)
    info = {
        "nombre": pack.title if pack.title != "?" else pack.path.rsplit(".", 1)[0],
        "archivo": pack.path,
        "voces": [x.name for x in pack.voices],
        "voz": int(i),
        "tipo": v.voice_type,
        "muestras": len(pack.waves),
        "mb": round(mem / 1e6, 2),
        "notas": lista,
    }
    if ESTADO["estilo"] is not None:
        info["faltan"] = _faltan()
    return json.dumps(info)


def _recortar(x: np.ndarray, sr: int = motor.SR) -> np.ndarray:
    a = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    idx = np.where(a > 10 ** (-72 / 20))[0]
    if not len(idx):
        return x[:1]
    fin = min(len(x), idx[-1] + int(sr * 0.01), int(sr * 6))
    return x[:fin]


def plan_banco() -> str:
    """Qué renderizar: por nota, sus capas de velocidad reales y la curva de velocidad (dB) del teclado.
    La app renderiza una vez por capa y ajusta el volumen de cada golpe con la curva."""
    e = ESTADO["engine"]
    cortes: dict[int, set[int]] = {}
    elem: dict[int, object] = {}
    for el, kb, lo, hi, vlo, vhi in e.voice.zones():
        for n in range(lo, min(hi, lo + 60) + 1):
            cortes.setdefault(n, {1}).add(max(1, vlo))
            cortes[n].add(min(128, vhi + 1))
            elem.setdefault(n, el)
    plan = []
    for n in sorted(cortes):
        c = sorted(x for x in cortes[n] if 1 <= x <= 128)
        if c[-1] != 128:
            c.append(128)
        capas = [[a, b - 1, b - 1] for a, b in zip(c, c[1:]) if b > a]
        es = e.sound.get(elem[n].number, motor.ElementSound(elem[n].number))
        db = [round(float(e.velocity_db(es, max(1, v))), 2) for v in range(128)]
        plan.append({"nota": n, "capas": capas, "db": db})
    return json.dumps(plan)


def render_lote(pedidos_json: str):
    """pedidos: [[nota, velocidad], ...] -> (json meta, bytes float32 L/R intercalado).
    meta: [[nota, vel, inicio, frames, grupo], ...] (inicio en floats)."""
    e = ESTADO["engine"]
    meta, partes, pos = [], [], 0
    for n, v in json.loads(pedidos_json):
        buf, g = e.render(int(n), int(v))
        x = _recortar(np.asarray(buf, np.float32))
        flat = np.ascontiguousarray(x, np.float32).reshape(-1)
        meta.append([int(n), int(v), pos, len(x), int(g)])
        partes.append(flat)
        pos += len(flat)
    data = np.concatenate(partes).astype(np.float32).tobytes() if partes else b""
    return json.dumps(meta), data


# ------------------------------------------------------------------ revisión
def revisar() -> str:
    pack = ESTADO["pack"]
    v = pack.voices[ESTADO["voz"]]
    rep = analisis.analyze_voice(pack, v)
    probs = [{"nivel": p.level, "texto": p.text} for p in rep.problems]
    comp = [{"modelo": r.modelo, "estado": r.estado, "resumen": r.resumen, "detalles": r.detalles}
            for r in compat.revisar(pack)]
    return json.dumps({"problemas": probs, "compat": comp})


# ------------------------------------------------------------------ ritmos
def ritmos() -> str:
    disp = _disp()
    out = {}
    for nombre, (pasos, sub, notas) in grooves.PATRONES.items():
        ev = []
        for st, n, v in notas:
            m = grooves.adaptar(n, disp)
            if m is not None:
                ev.append([st, m, v])
        out[nombre] = {"pasos": pasos, "sub": sub, "eventos": ev}
    return json.dumps(out)


# ------------------------------------------------------------------ estilos
def _faltan() -> dict:
    est = ESTADO["estilo"]
    disp = _disp()
    f = estilos.faltantes(est, disp)
    total = sum(est.notas().values()) or 1
    return {"lista": [[_nombre_nota(n), c] for n, c in f],
            "pct": round(100 * sum(c for _, c in f) / total)}


def abrir_estilo(data, nombre: str) -> str:
    import os
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, nombre)
    with open(p, "wb") as f:
        f.write(_bytes(data))
    est = estilos.leer(p)
    ESTADO["estilo"] = est
    return estilo_json()


def estilo_json() -> str:
    est = ESTADO["estilo"]
    disp = _disp()
    mapa = {n: grooves.adaptar(n, disp) for n in est.notas()}
    secs = {}
    for s in est.ordenadas():
        sec = est.secciones[s]
        ev = [[t, mapa[n], v, ch] for t, n, v, ch in sec.eventos if mapa.get(n) is not None]
        secs[s] = {"largo": sec.largo, "compases": est.compases(s), "tipo": sec.tipo,
                   "etiqueta": estilos.etiqueta(s), "eventos": ev}
    return json.dumps({"nombre": est.nombre, "tempo": est.tempo, "compas": list(est.compas), "ppq": est.ppq,
                       "orden": est.ordenadas(), "secciones": secs,
                       "ganancia": {str(k): v for k, v in est.ganancia.items()},
                       "faltan": _faltan() if disp else None})


# ------------------------------------------------------------------ demo
def _wav16(x: np.ndarray, sr: int = motor.SR) -> bytes:
    y = (np.clip(x, -1, 1) * 32767).astype("<i2")
    b = io.BytesIO()
    n = y.size * 2
    b.write(b"RIFF" + struct.pack("<I", 36 + n) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, 2, sr, sr * 4, 4, 16) + b"data" + struct.pack("<I", n))
    b.write(y.tobytes())
    return b.getvalue()


def crear_demo(opciones_json: str) -> bytes:
    o = json.loads(opciones_json)
    e = motor.Engine(ESTADO["pack"], ESTADO["pack"].voices[ESTADO["voz"]])
    est = ESTADO["estilo"] if o.get("estilo") else None
    x = demo.demo_kit(e, o.get("ritmos", []), float(o.get("bpm", 76)), int(o.get("compases", 4)),
                      bool(o.get("recorrido", True)), est, o.get("bpm_estilo"))
    return _wav16(x)
