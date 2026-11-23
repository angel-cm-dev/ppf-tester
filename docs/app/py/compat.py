"""Compatibilidad por modelo y ayuda con Expansion Manager.

Los avisos se basan en la memoria de expansión de cada modelo y en lo que
recomienda este programa para que un kit suene bien y deje sitio a otros packs
(capas de velocidad, estéreo y largo de las muestras). No reemplazan la prueba
en el teclado real.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

import modelos
from ppf_format import Pack, note_name

PLATOS = set(range(49, 60)) | {46}   # crash, ride, china, splash, hi-hat abierto (GM)


@dataclass
class Resultado:
    modelo: str
    estado: str                  # OK | AVISO | ERROR
    resumen: str
    detalles: list[str] = field(default_factory=list)


def _datos(pack: Pack) -> dict:
    v = pack.voices[0] if pack.voices else None
    capas: dict[int, set] = {}
    estereo_uids, uids_platos = set(), set()
    if v is not None:
        for el, kb, lo, hi, vlo, vhi in v.zones():
            for n in range(lo, hi + 1):
                capas.setdefault(n, set()).add(kb.samples[0].wave_uid)
            if len(kb.samples) == 2 and kb.samples[0].wave_uid != kb.samples[1].wave_uid:
                estereo_uids.update(s.wave_uid for s in kb.samples)
            if lo in PLATOS:
                uids_platos.update(s.wave_uid for s in kb.samples)
    ondas = list(pack.waves.values())
    mb = sum(w.frames * w.channels * 2 for w in ondas) / 1e6
    mb_st = sum(pack.waves[u].frames * 2 for u in estereo_uids if u in pack.waves) / 1e6
    largas = [w for w in ondas if w.duration > 6]
    rates = sorted({int(w.rate) for w in ondas if int(w.rate) != 44100})
    tipo = v.voice_type if v is not None else ""
    capas = {n: len(u) for n, u in capas.items()}   # muestras distintas por tecla
    return dict(capas=capas, mb=mb, mb_st=mb_st, largas=largas, rates=rates, tipo=tipo, platos=uids_platos)


def revisar(pack: Pack) -> list[Resultado]:
    """Un resultado por modelo, del más pequeño al más grande."""
    d = _datos(pack)
    out = []
    for m in modelos.MODELOS.values():
        det, estado = [], "OK"

        def sube(nuevo):
            nonlocal estado
            orden = ("OK", "AVISO", "ERROR")
            if orden.index(nuevo) > orden.index(estado):
                estado = nuevo

        mb = d["mb"]
        if mb > m.memoria_mb:
            sube("ERROR")
            det.append(f"No cabe: {mb:.1f} MB y el {m.nombre} tiene {m.memoria_mb:.0f} MB de expansión.")
        elif mb > m.kit_max_mb:
            sube("AVISO")
            det.append(f"{mb:.1f} MB ocupa el {mb / m.memoria_mb * 100:.0f} % de la memoria (recomendado ≤ {m.kit_max_mb:.0f} MB por kit).")
        muchas = sorted(n for n, c in d["capas"].items() if c > max(m.capas, 1) * 1)
        if muchas and d["tipo"] == "DRUM_KIT":
            if m.memoria_mb < 100:
                sube("AVISO")
                det.append(f"{len(muchas)} tecla(s) con más de {m.capas} capas de velocidad ({', '.join(note_name(n) for n in muchas[:6])}"
                           f"{'…' if len(muchas) > 6 else ''}): en el {m.nombre} conviene 2 capas.")
        if not m.capas_platos:
            pl = [n for n, c in d["capas"].items() if n in PLATOS and c > 1]
            if pl:
                sube("AVISO")
                det.append(f"Platos con capas ({', '.join(note_name(n) for n in sorted(pl)[:5])}): en el {m.nombre} es mejor una sola capa en platos.")
        if d["mb_st"] > 0 and m.memoria_mb < 100 and d["mb_st"] > mb * 0.4:
            sube("AVISO")
            det.append(f"{d['mb_st']:.1f} MB en muestras estéreo: en mono ocuparía la mitad.")
        if d["largas"] and m.memoria_mb < 100:
            sube("AVISO")
            det.append(f"{len(d['largas'])} muestra(s) de más de 6 s: acorta las colas para ahorrar memoria.")
        if d["rates"]:
            det.append("Muestras a " + ", ".join(f"{r / 1000:g} kHz" for r in d["rates"]) + ": el teclado trabaja a 44.1 kHz.")
        if not det:
            det.append(f"Entra sin problemas ({mb:.2f} MB de {m.memoria_mb:.0f} MB).")
        resumen = {"OK": "Compatible", "AVISO": "Compatible con recomendaciones", "ERROR": "No compatible"}[estado]
        out.append(Resultado(m.nombre, estado, resumen, det))
    return out


# ------------------------------------------------------------------ Expansion Manager
RUTAS_EM = [
    r"C:\Program Files\Yamaha\Expansion Manager\Expansion Manager.exe",
    r"C:\Program Files (x86)\Yamaha\Expansion Manager\Expansion Manager.exe",
    "/Applications/Expansion Manager.app",
]


def buscar_em() -> str | None:
    for p in RUTAS_EM:
        if os.path.exists(p):
            return p
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
        if base and os.path.isdir(os.path.join(base, "Yamaha")):
            for root, _dirs, files in os.walk(os.path.join(base, "Yamaha")):
                if "Expansion Manager.exe" in files:
                    return os.path.join(root, "Expansion Manager.exe")
    return shutil.which("Expansion Manager")


PASOS_EM = [
    "En Expansion Manager, importa el .ppf (Import Pack).",
    "Añade tu teclado con su archivo «Instrument Info» (se guarda desde el PSR a un USB).",
    "Exporta el «Pack Installation File» para tu teclado: es un archivo cifrado solo para ese PSR.",
    "Copia ese archivo a un USB e instálalo en el PSR desde Menu → Expansion → Pack Installation.",
]


def abrir_em(ppf: str | None = None) -> tuple[bool, str]:
    """Abre Expansion Manager (y el .ppf si lo acepta). Devuelve (ok, mensaje)."""
    exe = buscar_em()
    if exe is None:
        return False, "No encontré Expansion Manager. Descárgalo gratis desde la web de Yamaha."
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", exe] + ([ppf] if ppf else []))
        else:
            subprocess.Popen([exe] + ([ppf] if ppf else []), cwd=os.path.dirname(exe))
    except OSError as e:
        return False, f"No se pudo abrir Expansion Manager: {e}"
    return True, "Expansion Manager abierto. Si no carga el kit solo, usa «Pack Edit → Import Pack»."
