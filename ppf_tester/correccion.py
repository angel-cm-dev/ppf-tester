"""Correcciones automaticas sobre las muestras de un pack.

Nunca modifica el archivo original: siempre se guarda un .ppf nuevo.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass

import numpy as np

import analisis as A
from ppf_format import Pack, Wave, replace_wave


@dataclass
class Opciones:
    quitar_dc: bool = True
    fade_inicio: bool = True        # micro fade-in si empieza con salto
    fade_final: bool = True         # fade-out si termina cortada
    recortar_final: bool = True     # quitar silencio sobrante al final
    recortar_inicio: bool = False   # quitar silencio inicial (cambia el "timing")
    normalizar_db: float | None = None   # p.ej. -1.0 (cambia el balance del kit)
    agrupar_hihat: bool = False
    umbral_recorte_db: float = -72.0


def _fade(n: int) -> np.ndarray:
    # curva coseno (suave, sin clic)
    return 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))


def _highpass(x: np.ndarray, sr: float, fc: float = 5.0) -> np.ndarray:
    """Filtro pasa-altos de 1 polo (quita DC sin afectar lo audible)."""
    a = np.exp(-2 * np.pi * fc / sr)
    from sig import lfilter
    return lfilter([1, -1], [1, -a], x, axis=0) * (1 + a) / 2


def fix_wave(w: Wave, rep: A.WaveReport, op: Opciones, one_shot: bool) -> tuple[Wave, list[str]]:
    x = w.samples.copy()
    sr = w.rate or 44100.0
    done: list[str] = []
    codes = {p.code for p in rep.problems}

    if op.quitar_dc and "dc" in codes:
        x = _highpass(x, sr)
        done.append("DC offset eliminado")

    absx = np.abs(x).max(axis=1)
    offset = 0
    # recorte inicial (opcional)
    if op.recortar_inicio and "sil_ini" in codes:
        idx = np.where(absx > 10 ** (A.SILENCE_DB / 20))[0]
        if len(idx):
            keep = max(0, idx[0] - int(sr * 0.0005))
            if keep > 0:
                x = x[keep:]
                offset = keep
                done.append(f"recortados {keep / sr * 1000:.0f} ms de silencio inicial")
                n = min(len(x), int(sr * 0.0005))
                x[:n] *= _fade(n)[:, None]
                absx = np.abs(x).max(axis=1)

    if op.fade_inicio and "clic_ini" in codes:
        n = min(len(x), max(8, int(sr * 0.001)))
        x[:n] *= _fade(n)[:, None]
        done.append("fade-in de 1 ms contra el clic inicial")

    # recorte final: solo en muestras one-shot sin loop
    if op.recortar_final and one_shot and w.loop_mode == 0:
        idx = np.where(absx > 10 ** (op.umbral_recorte_db / 20))[0]
        if len(idx):
            end = min(len(x), idx[-1] + int(sr * 0.02))
            if len(x) - end > sr * 0.03:
                saved = len(x) - end
                x = x[:end]
                n = min(len(x), int(sr * 0.03))
                x[-n:] *= _fade(n)[::-1][:, None]
                done.append(f"recortados {saved / sr * 1000:.0f} ms de silencio final (+ fade de 30 ms)")

    if op.fade_final and one_shot and "corte" in codes:
        n = min(len(x), int(sr * 0.005))
        x[-n:] *= _fade(n)[::-1][:, None]
        done.append("fade-out de 5 ms contra el corte final")

    if op.normalizar_db is not None:
        peak = np.abs(x).max()
        if peak > 0:
            g = 10 ** (op.normalizar_db / 20) / peak
            if abs(20 * np.log10(g)) > 0.1:
                x = x * g
                done.append(f"normalizado a {op.normalizar_db:.1f} dBFS ({20 * np.log10(g):+.1f} dB)")

    if not done:
        return w, done
    nw = copy.copy(w)
    nw.samples = x
    nw.markers = {}
    for k, (pos, nm) in w.markers.items():
        # un marcador que apuntaba al final sigue apuntando al nuevo final
        new = len(x) if pos >= w.frames else min(max(0, pos - offset), len(x))
        nw.markers[k] = (new, nm)
    return nw, done


def _set_alternate_group(pack: Pack, notes=(42, 44, 46), group: int = 1) -> bool:
    changed = False
    for r in pack.resources:
        if r.ext != "uvf":
            continue
        xml = r.get(b"FBIN").decode("utf-8")

        def sub(m):
            nonlocal changed
            if int(m.group(1)) not in notes:
                return m.group(0)
            changed = True
            return re.sub(r"<alternateGroup>\d+</alternateGroup>", f"<alternateGroup>{group}</alternateGroup>", m.group(0))

        xml = re.sub(r'<voiceElement number="(\d+)".*?</voiceElement>', sub, xml, flags=re.S)
        r.set(b"FBIN", xml.encode("utf-8"))
    return changed


def corregir(pack: Pack, op: Opciones) -> list[tuple[str, list[str]]]:
    """Aplica las correcciones dentro de 'pack' (en memoria). Devuelve el log."""
    one_shot = {}
    for v in pack.voices:
        for kbs in v.keybanks.values():
            for kb in kbs:
                for s in kb.samples:
                    one_shot[s.wave_uid] = one_shot.get(s.wave_uid, True) and kb.one_shot
    log = []
    for uid in list(pack.waves):
        w = pack.waves[uid]
        os_ = one_shot.get(uid, True)
        rep = A.analyze_wave(w, os_)
        nw, done = fix_wave(w, rep, op, os_)
        if done:
            replace_wave(pack, uid, nw)
            log.append((w.name, done))
    if op.agrupar_hihat and _set_alternate_group(pack):
        log.append(("Hi-hat (F#1/G#1/A#1)", ["mismo Alternate Group = 1: el cerrado corta al abierto"]))
    return log
