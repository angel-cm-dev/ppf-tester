"""Mejora de calidad del kit: procesado por pieza, balance, afinación de toms,
capas de velocidad ligeras y control de memoria según el modelo de teclado."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

import numpy as np

import correccion as C
import dsp
import modelos
from ppf_format import (Pack, Wave, add_wave, edit_element, remove_unused_waves, reparse_voices,
                        replace_wave, set_velocity_layers)

TIPOS = ("bombo", "caja", "tom", "hihat", "ride", "crash", "perc")
NOMBRE_TIPO = {"bombo": "Bombo", "caja": "Caja", "tom": "Tom", "hihat": "Hi-hat", "ride": "Ride",
               "crash": "Crash/Plato", "perc": "Percusión"}

# palabras clave (español, portugués, inglés)
CLAVES = [
    ("hihat", r"hi.?hat|\bhh\b|chimbal|cimbal|charles|contratiempo"),
    ("ride", r"ride|condu[cç][aã]o|conducci[oó]n|campana|bell"),
    ("crash", r"crash|prato|plato|splash|china|cymbal|platillo"),
    ("bombo", r"kick|bumbo|bombo|\bbd\b|bass ?drum"),
    ("caja", r"snare|caixa|caja|tarola|redoblante|\bsd\b|rim|aro"),
    ("tom", r"\btom|surdo|floor"),
]
# mapa General MIDI de batería
GM = {35: "bombo", 36: "bombo", 37: "caja", 38: "caja", 40: "caja", 39: "perc",
      41: "tom", 43: "tom", 45: "tom", 47: "tom", 48: "tom", 50: "tom",
      42: "hihat", 44: "hihat", 46: "hihat", 49: "crash", 52: "crash", 55: "crash", 57: "crash",
      51: "ride", 53: "ride", 59: "ride"}


def clasificar(nombre: str, notas: list[int], w: Wave) -> str:
    low = nombre.lower()
    for t, rx in CLAVES:
        if re.search(rx, low):
            return t
    for n in notas:
        if n in GM:
            return GM[n]
    # por espectro
    db, f = dsp.spectrum_db(w.samples, w.rate, 32)
    cen = float((f * 10 ** (db / 10)).sum() / (10 ** (db / 10)).sum())
    if cen < 150:
        return "bombo"
    if cen < 400:
        return "tom"
    return "crash" if w.duration > 1 else "perc"


# Cadenas de procesado por tipo. Cantidades en dB a intensidad 1.0
CADENAS = {
    "bombo": dict(hpf=30, eq=[("peak", 55, 2.0, 1.0), ("peak", 350, -4.0, 1.2), ("peak", 3500, 4.0, 1.5)],
                  trans=0.5, comp=(3.0, -12), sat=0.15),
    "caja": dict(hpf=70, eq=[("peak", 200, 2.0, 1.0), ("peak", 900, -2.0, 1.5), ("peak", 5000, 3.0, 1.0),
                             ("high", 10000, 3.0, 0)], trans=0.4, comp=(3.0, -14), sat=0.10),
    "tom": dict(hpf=40, eq=[("peak", 400, -4.0, 1.0), ("peak", 4000, 5.0, 1.2), ("high", 9000, 2.0, 0)],
                trans=0.6, comp=(2.5, -14), sat=0.10),
    "hihat": dict(hpf=300, eq=[("peak", 3000, -1.0, 1.5), ("high", 10000, 2.0, 0)], trans=0.2, comp=None, sat=0.0),
    "ride": dict(hpf=250, eq=[("peak", 2500, -1.5, 1.2), ("high", 8000, 4.0, 0)], trans=0.2, comp=None, sat=0.0),
    "crash": dict(hpf=250, eq=[("peak", 3000, -2.0, 1.2), ("high", 9000, 3.0, 0)], trans=0.0, comp=None, sat=0.0),
    "perc": dict(hpf=60, eq=[("high", 8000, 2.0, 0)], trans=0.3, comp=(2.0, -14), sat=0.05),
}
# nivel RMS objetivo (primeros 250 ms) relativo al bombo
BALANCE = {"bombo": 0.0, "caja": 0.0, "tom": -2.0, "hihat": -10.0, "ride": -10.0, "crash": -6.0, "perc": -6.0}
# corte del filtro para capas suaves (Hz)
CORTE_SUAVE = {"bombo": 2500, "caja": 3500, "tom": 3000, "hihat": 5000, "ride": 5000, "crash": 4500, "perc": 4000}
PRIORIDAD_CAPAS = ["caja", "bombo", "tom", "hihat", "perc", "ride", "crash"]


def procesar(x: np.ndarray, sr: float, tipo: str, intensidad: float) -> np.ndarray:
    c = CADENAS[tipo]
    k = float(np.clip(intensidad, 0, 1.5))
    pk0 = np.abs(x).max()
    y = dsp.hpf(x, sr, c["hpf"])
    for kind, fc, g, q in c["eq"]:
        y = dsp.shelf(y, sr, fc, g * k, high=True) if kind == "high" else dsp.peak(y, sr, fc, g * k, q)
    y = dsp.transient(y, sr, c["trans"] * k)
    if c["comp"]:
        r, thr = c["comp"]
        y = dsp.compress(y, sr, 1 + (r - 1) * k, thr)
    y = dsp.saturate(y, c["sat"] * k)
    # micro fade-in para no crear clic con el filtro
    n = min(len(y), 16)
    y[:n] *= np.linspace(0, 1, n)[:, None]
    pk = np.abs(y).max()
    return y * (pk0 / pk) if pk > 0 else y


def _with(w: Wave, x: np.ndarray) -> Wave:
    nw = copy.copy(w)
    nw.samples = x
    nw.markers = {k: (len(x) if pos >= w.frames else min(pos, len(x)), nm) for k, (pos, nm) in w.markers.items()}
    return nw


def capa_suave(x: np.ndarray, sr: float, tipo: str, factor: float, touch_db: float) -> np.ndarray:
    """Golpe más suave a partir del fuerte (modelo de timbre por velocidad, ver sonido.py)."""
    import sonido
    return sonido.capa_suave(x, sr, tipo, factor, touch_db)


@dataclass
class OpcionesMejora:
    modelo: str = modelos.POR_DEFECTO
    correcciones: bool = True
    procesado: bool = True
    intensidad: float = 1.0
    balance: bool = True
    afinar_toms: bool = True
    hihat: bool = True
    abrir_filtro: bool = True
    corte_hz: float = 16000.0
    capas: str = "auto"            # auto | 0 | 2 | 3
    nivel_teclado: bool = False    # nivel de referencia por pieza (en vez del balance relativo)
    sala: float = 0.0              # sala integrada (0..1)
    sala_tam: float = 0.4
    fase: bool = True              # corregir fase de muestras estéreo


@dataclass
class Fila:
    nombre: str
    tipo: str
    notas: list[int]
    cambios: list[str] = field(default_factory=list)
    antes: np.ndarray | None = None
    despues: np.ndarray | None = None


def _mb(pack) -> float:
    return sum(w.frames * w.channels * 2 for w in pack.waves.values()) / 1e6


def mejorar(pack: Pack, op: OpcionesMejora, log=lambda s: None) -> tuple[list[Fila], list[str], float, float]:
    """Aplica todas las mejoras sobre 'pack' (en memoria)."""
    mb0 = _mb(pack)
    modelo = modelos.MODELOS[op.modelo]
    avisos: list[str] = []
    if not pack.voices:
        return [], ["El pack no tiene voces."], mb0, mb0
    voice = pack.voices[0]
    original = {uid: w.samples.copy() for uid, w in pack.waves.items()}

    def uso():
        u: dict[str, list[int]] = {}
        for el, kb, lo, hi, vlo, vhi in pack.voices[0].zones():
            for s in kb.samples:
                u.setdefault(s.wave_uid, [])
                if lo not in u[s.wave_uid]:
                    u[s.wave_uid].append(lo)
        return u

    filas: dict[str, Fila] = {}
    for uid, notas in uso().items():
        w = pack.waves[uid]
        filas[w.name] = Fila(w.name, clasificar(w.name, notas, w), sorted(notas), antes=original[uid])

    # 1. correcciones básicas
    if op.correcciones:
        log("Correcciones básicas (DC, clics, silencio final)…")
        for name, done in C.corregir(pack, C.Opciones()):
            if name in filas:
                filas[name].cambios += done

    # 2. procesado por pieza
    by_name = {w.name: uid for uid, w in pack.waves.items()}
    if op.procesado:
        log("Procesado por pieza (EQ, ataque, compresión, saturación)…")
        for name, f in filas.items():
            uid = by_name[name]
            w = pack.waves[uid]
            y = procesar(w.samples, w.rate, f.tipo, op.intensidad)
            by_name[name] = replace_wave(pack, uid, _with(w, y))
            f.cambios.append(f"cadena «{NOMBRE_TIPO[f.tipo]}» al {op.intensidad * 100:.0f} %")

    # 2b. sala integrada
    if op.sala > 0:
        import sonido
        log("Sala integrada…")
        for name, f in filas.items():
            uid = by_name[name]
            w = pack.waves[uid]
            amt = op.sala * (0.5 if f.tipo in ("crash", "ride", "hihat") else 1.0)
            by_name[name] = replace_wave(pack, uid, _with(w, sonido.sala(w.samples, w.rate, amt, op.sala_tam)))
            f.cambios.append(f"sala {op.sala * 100:.0f} %")

    # 2c. fase de las muestras estéreo (L y R distintas)
    if op.fase:
        import sonido
        pares = set()
        for el, kb, lo, hi, vlo, vhi in pack.voices[0].zones():
            if len(kb.samples) == 2 and kb.samples[0].wave_uid != kb.samples[1].wave_uid:
                pares.add((kb.samples[0].wave_uid, kb.samples[1].wave_uid))
        for lu, ru in pares:
            wl, wr = pack.waves.get(lu), pack.waves.get(ru)
            if wl is None or wr is None:
                continue
            l, r, msg = sonido.corregir_fase(wl.samples, wr.samples)
            if msg:
                nuevo = replace_wave(pack, ru, _with(wr, r))
                for k, v in list(by_name.items()):
                    if v == ru:
                        by_name[k] = nuevo
                if wl.name in filas:
                    filas[wl.name].cambios.append(msg)
                reparse_voices(pack)

    # 3a. nivel de referencia (como los kits del teclado)
    if op.nivel_teclado:
        import sonido
        log("Nivel de referencia por pieza…")
        for name, f in filas.items():
            uid = by_name[name]
            w = pack.waves[uid]
            g = sonido.ganancia_referencia(w.samples, w.rate, f.tipo)
            if abs(g) >= 0.5:
                by_name[name] = replace_wave(pack, uid, _with(w, w.samples * 10 ** (g / 20)))
                f.cambios.append(f"nivel de referencia {g:+.1f} dB")

    # 3. balance del kit
    if op.balance and not op.nivel_teclado:
        log("Balance del kit…")
        lv = {n: dsp.rms_db(pack.waves[by_name[n]].samples, pack.waves[by_name[n]].rate) for n in filas}
        ref = [lv[n] for n, f in filas.items() if f.tipo == "bombo"] or [lv[n] for n, f in filas.items() if f.tipo == "caja"]
        if ref:
            ref_db = max(ref)
            for name, f in filas.items():
                uid = by_name[name]
                w = pack.waves[uid]
                target = ref_db + BALANCE[f.tipo]
                g = target - lv[name]
                head = -0.5 - dsp.peak_db(w.samples)
                g = min(g, head)
                if abs(g) >= 0.5:
                    by_name[name] = replace_wave(pack, uid, _with(w, w.samples * 10 ** (g / 20)))
                    f.cambios.append(f"nivel {g:+.1f} dB")
                    if g == head and target - lv[name] > head + 1:
                        avisos.append(f"'{name}' sigue {target - lv[name] - head:.0f} dB bajo: súbelo con el volumen de la nota.")

    # 4. afinar notas que repiten la misma muestra
    reparse_voices(pack)
    voice = pack.voices[0]
    if op.afinar_toms:
        for name, f in filas.items():
            if len(f.notas) < 2 or f.tipo not in ("tom", "bombo"):
                continue
            notas = sorted(f.notas)
            pasos = [0, -2, -4, -5, -7, -9] if f.tipo == "tom" else [0, -1, -2]
            for i, n in enumerate(reversed(notas)):
                st = pasos[min(i, len(pasos) - 1)]
                if st and edit_element(pack, voice, n, "pitchBlock", "tuneCoarse", st):
                    f.cambios.append(f"{_nn(n)} afinado {st:+d} st")

    # 5. hi-hat
    if op.hihat:
        notes_hh = [n for f in filas.values() if f.tipo == "hihat" for n in f.notas]
        if len(notes_hh) > 1:
            for n in notes_hh:
                edit_element(pack, voice, n, "drumSetup", "alternateGroup", 1)
            for f in filas.values():
                if f.tipo == "hihat":
                    f.cambios.append("grupo de corte del hi-hat")

    # 6. filtro de la voz
    if op.abrir_filtro:
        notas = sorted({n for f in filas.values() for n in f.notas})
        for n in notas:
            edit_element(pack, voice, n, "filterBlock", "dcfCutoff", float(op.corte_hz))
        avisos.append(f"Filtro paso-bajo abierto a {op.corte_hz:.0f} Hz en las teclas del kit (verifícalo en Expansion Manager).")

    reparse_voices(pack)
    voice = pack.voices[0]

    # 7. capas de velocidad (dentro del presupuesto de memoria del modelo)
    ncapas = modelo.capas if op.capas == "auto" else int(op.capas)
    if ncapas >= 2:
        log(f"Capas de velocidad ({ncapas}) para {modelo.nombre}…")
        rangos = [(1, 79), (80, 127)] if ncapas == 2 else [(1, 55), (56, 99), (100, 127)]
        from motor import parse_sound
        sound, _ = parse_sound(voice)
        presupuesto = modelo.kit_max_mb
        hechos = set()
        orden = sorted(filas.values(), key=lambda f: PRIORIDAD_CAPAS.index(f.tipo))
        for f in orden:
            if f.tipo in ("ride", "crash") and not modelo.capas_platos and op.capas == "auto":
                continue
            # formas de onda que usan esta muestra
            uid = by_name[f.nombre]
            wfs = []
            for el, kb, lo, hi, vlo, vhi in voice.zones():
                if kb.samples[0].wave_uid == uid and (vlo, vhi) == (1, 127) and kb.waveform not in wfs:
                    if len(voice.keybanks.get(kb.waveform, [])) == 1:
                        wfs.append((kb.waveform, el.number))
            if not wfs:
                continue
            w = pack.waves[uid]
            es = sound.get(wfs[0][1])
            capas_uid = []
            extra = 0.0
            for i, (vlo, vhi) in enumerate(rangos[:-1]):
                factor = 1.0 if i == 0 else 0.5
                tdb = float(es.touch_db[vhi] * es.touch_sens) if es is not None and es.touch_db is not None else 40 * np.log10(vhi / 127)
                y = capa_suave(w.samples, w.rate, f.tipo, factor, tdb)
                capas_uid.append((vlo, vhi, y))
                extra += y.shape[0] * y.shape[1] * 2 / 1e6
            if _mb(pack) + extra > presupuesto:
                avisos.append(f"Sin capas para '{f.nombre}': superaría {presupuesto:.0f} MB recomendados para un kit en {modelo.nombre}.")
                continue
            layers = []
            for i, (vlo, vhi, y) in enumerate(capas_uid):
                nuid = add_wave(pack, w, y.astype(np.float64), f"{f.nombre} v{i + 1}")
                layers.append((vlo, vhi, nuid))
            layers.append((rangos[-1][0], rangos[-1][1], uid))
            for wf, _ in wfs:
                set_velocity_layers(pack, voice, wf, layers)
            hechos.add(f.nombre)
            f.cambios.append(f"{ncapas} capas de velocidad (+{extra:.2f} MB)")
        reparse_voices(pack)

    remove_unused_waves(pack)
    reparse_voices(pack)
    for f in filas.values():
        uid = by_name.get(f.nombre)
        if uid in pack.waves:
            f.despues = pack.waves[uid].samples
    mb1 = _mb(pack)
    return list(filas.values()), avisos, mb0, mb1


def _nn(n):
    from ppf_format import note_name
    return note_name(n)


CUERPO_HZ = {"bombo": 70, "caja": 200, "tom": 130, "hihat": 600, "ride": 500, "crash": 400, "perc": 300}


def ajuste_fino(x: np.ndarray, sr: float, tipo: str, golpe: float, cuerpo: float, brillo: float) -> np.ndarray:
    """golpe/cuerpo/brillo en -1..1. Mantiene el pico original."""
    pk0 = np.abs(x).max()
    y = x
    if abs(golpe) > 0.01:
        y = dsp.transient(y, sr, golpe * 0.9)
    if abs(cuerpo) > 0.01:
        y = dsp.peak(y, sr, CUERPO_HZ.get(tipo, 200), cuerpo * 6, 0.9)
    if abs(brillo) > 0.01:
        y = dsp.shelf(y, sr, 6000, brillo * 6, high=True)
    pk = np.abs(y).max()
    return y * (pk0 / pk) if pk > 0 else y


PLANTILLAS = {
    "Worship suave": dict(intensidad=0.6, correcciones=True, procesado=True, balance=True, afinar_toms=True,
                          hihat=True, abrir_filtro=True, capas="auto"),
    "Worship moderno": dict(intensidad=1.0, correcciones=True, procesado=True, balance=True, afinar_toms=True,
                            hihat=True, abrir_filtro=True, capas="auto"),
    "Rock potente": dict(intensidad=1.3, correcciones=True, procesado=True, balance=True, afinar_toms=True,
                         hihat=True, abrir_filtro=True, capas="auto"),
    "Natural (mínimo)": dict(intensidad=0.3, correcciones=True, procesado=True, balance=False, afinar_toms=False,
                             hihat=True, abrir_filtro=False, capas="0"),
    "Solo limpieza": dict(intensidad=0.0, correcciones=True, procesado=False, balance=False, afinar_toms=False,
                          hihat=False, abrir_filtro=False, capas="0"),
}


def mejorar_carpeta(carpeta: str, salida: str, op: "OpcionesMejora", log=lambda s: None) -> list[tuple[str, str]]:
    """Mejora todos los .ppf de una carpeta. Devuelve [(archivo, resultado)]."""
    import os
    from ppf_format import load_pack
    os.makedirs(salida, exist_ok=True)
    res = []
    archivos = sorted(f for f in os.listdir(carpeta) if f.lower().endswith(".ppf"))
    for i, f in enumerate(archivos):
        log(f"[{i + 1}/{len(archivos)}] {f}")
        try:
            pack = load_pack(os.path.join(carpeta, f))
            if not pack.voices:
                res.append((f, "sin voces, omitido"))
                continue
            filas, avisos, mb0, mb1 = mejorar(pack, op)
            out = os.path.join(salida, os.path.splitext(f)[0] + f"_PRO_{op.modelo.replace('PSR-', '')}.ppf")
            pack.save(out)
            chk = load_pack(out)
            res.append((f, "error de verificación" if chk.errors else f"OK · {mb0:.2f} → {mb1:.2f} MB"))
        except Exception as e:  # noqa: BLE001
            res.append((f, f"error: {e}"))
    return res
