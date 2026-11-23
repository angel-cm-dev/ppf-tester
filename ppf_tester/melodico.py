"""Voces melódicas (pianos, pads, cuerdas…) a partir de WAV.

- Detecta la nota de cada muestra (por el nombre o por su altura).
- Crea loops sin clics para sonidos sostenidos (pads, cuerdas, órganos).
- Reparte las muestras por el teclado (multisample) con capas de velocidad.
- Escribe el .ppf usando como plantilla una voz normal creada en Expansion Manager
  (se usa solo su estructura; su audio se reemplaza).
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
import uuid
from dataclasses import dataclass

import numpy as np

import dsp
from ppf_format import Pack, Resource, Wave, load_pack, note_name

SR = 44100
NOMBRES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11, "do": 0, "re": 2, "mi": 4, "fa": 5, "sol": 7, "la": 9, "si": 11}


# ------------------------------------------------------------------ altura
def altura(x: np.ndarray, sr: int = SR) -> float:
    """Frecuencia fundamental (Hz) por autocorrelación normalizada (tipo YIN). 0 si no hay tono."""
    m = np.asarray(x, dtype=np.float64)
    m = m.mean(axis=1) if m.ndim > 1 else m
    a = np.abs(m)
    if not len(a) or a.max() == 0:
        return 0.0
    on = int(np.argmax(a > a.max() * 0.1))
    seg = m[on + int(sr * 0.05): on + int(sr * 0.05) + int(sr * 0.25)]
    if len(seg) < 2048:
        seg = m[on: on + int(sr * 0.25)]
    if len(seg) < 1024:
        return 0.0
    seg = seg - seg.mean()
    W = len(seg) // 2
    tau_min, tau_max = int(sr / 2000), min(W - 1, int(sr / 27.5))
    # función de diferencia acumulada normalizada
    d = np.zeros(tau_max + 1)
    x0 = seg[:W]
    e0 = np.dot(x0, x0)
    for tau in range(1, tau_max + 1):
        x1 = seg[tau:tau + W]
        d[tau] = e0 + np.dot(x1, x1) - 2 * np.dot(x0, x1)
    cmnd = np.ones_like(d)
    acc = np.cumsum(d[1:])
    cmnd[1:] = d[1:] * np.arange(1, tau_max + 1) / np.maximum(acc, 1e-12)
    cand = np.where(cmnd[tau_min:] < 0.15)[0]
    if len(cand):
        t = cand[0] + tau_min
        while t + 1 <= tau_max and cmnd[t + 1] < cmnd[t]:
            t += 1
    else:
        t = int(np.argmin(cmnd[tau_min:]) + tau_min)
        if cmnd[t] > 0.4:
            return 0.0
    if 1 <= t < tau_max:   # interpolación parabólica
        a_, b_, c_ = cmnd[t - 1], cmnd[t], cmnd[t + 1]
        den = a_ - 2 * b_ + c_
        t = t + (0.5 * (a_ - c_) / den if den else 0)
    return float(sr / t) if t > 0 else 0.0


def hz_a_midi(f: float) -> float:
    return 69 + 12 * np.log2(f / 440.0) if f > 0 else 0.0


def nota_en_nombre(nombre: str) -> list[int]:
    """Notas MIDI posibles según el nombre (C3, C#3, Db3, Sol2, 060…). Devuelve
    las dos lecturas de octava (C3=60 de Yamaha y C4=60 científica) para decidir con el audio."""
    s = os.path.splitext(os.path.basename(nombre))[0].lower()
    m = re.search(r"(?<![a-z])(do|re|mi|fa|sol|la|si|[a-g])\s?(#|b|s|♯|♭)?\s?(-?\d)(?!\d)", s)
    if m:
        base = NOMBRES[m.group(1)]
        alt = m.group(2) or ""
        base += 1 if alt in ("#", "s", "♯") else -1 if alt in ("b", "♭") else 0
        octv = int(m.group(3))
        yam = (octv + 2) * 12 + base          # C3 = 60
        sci = (octv + 1) * 12 + base          # C4 = 60
        return [n for n in (yam, sci) if 0 <= n <= 127]
    m = re.search(r"(?<!\d)(\d{2,3})(?!\d)", s)
    if m and 12 <= int(m.group(1)) <= 120:
        return [int(m.group(1))]
    return []


def detectar_nota(nombre: str, x: np.ndarray, sr: int = SR) -> tuple[int, float, str]:
    """(nota MIDI, desafinación en cents respecto de esa nota, cómo se detectó)."""
    f = altura(x, sr)
    mid = hz_a_midi(f)
    cand = nota_en_nombre(nombre)
    if cand:
        if mid:
            n = min(cand, key=lambda c: abs(c - mid))
            # si el audio contradice el nombre por mucho, se confía en el nombre igual
            return n, float((mid - n) * 100) if abs(mid - n) < 1 else 0.0, "nombre + audio"
        return cand[0], 0.0, "nombre"
    if mid:
        n = int(round(mid))
        return n, float((mid - n) * 100), "audio"
    return 60, 0.0, "sin tono (C3)"


# ------------------------------------------------------------------ loops
@dataclass
class Loop:
    inicio: int
    fin: int
    calidad: float      # 0..1 (1 = transición perfecta)


def _cruces(m: np.ndarray, a: int, b: int) -> np.ndarray:
    seg = m[a:b]
    return np.where((seg[:-1] <= 0) & (seg[1:] > 0))[0] + a


def buscar_loop(x: np.ndarray, sr: int = SR, min_s: float = 0.5, periodo: float = 0.0) -> Loop | None:
    """Busca un tramo que se repita sin saltos en la parte sostenida del sonido."""
    m = np.asarray(x, dtype=np.float64).mean(axis=1)
    n = len(m)
    if n < sr * (min_s + 0.3):
        return None
    env = np.sqrt(np.convolve(m ** 2, np.ones(1024) / 1024, mode="same"))
    pk = env.max() or 1
    vivos = np.where(env > pk * 10 ** (-30 / 20))[0]
    if not len(vivos):
        return None
    fin_util = int(vivos[-1])
    a0 = int(n * 0.25)
    if fin_util - a0 < sr * min_s:
        a0 = max(0, fin_util - int(sr * min_s) - 1)
    ventana = 512
    finales = _cruces(m, max(a0 + int(sr * min_s), fin_util - int(sr * 1.0)), fin_util - ventana)
    inicios = _cruces(m, a0, max(a0 + 1, fin_util - int(sr * min_s)))
    if not len(finales) or not len(inicios):
        return None
    finales = finales[:: max(1, len(finales) // 40)]
    inicios = inicios[:: max(1, len(inicios) // 120)]
    mejor = None
    for e in finales:
        tras_fin = m[e - ventana:e]
        nf = np.linalg.norm(tras_fin) + 1e-12
        for s in inicios:
            if e - s < sr * min_s or s < ventana:
                continue
            antes = m[s - ventana:s]
            c = float(np.dot(antes, tras_fin) / (nf * (np.linalg.norm(antes) + 1e-12)))
            r = env[s] / max(env[e], 1e-12)
            score = c - 0.5 * abs(np.log2(max(r, 1e-6)))
            if mejor is None or score > mejor[0]:
                mejor = (score, s, e, c)
    if mejor is None:
        return None
    return Loop(int(mejor[1]), int(mejor[2]), float(max(0.0, mejor[3])))


def aplicar_loop(x: np.ndarray, loop: Loop, sr: int = SR, xfade_s: float = 0.08) -> np.ndarray:
    """Funde el final del loop con lo que hay antes del inicio (crossfade) y corta tras el fin."""
    y = np.asarray(x, dtype=np.float64)[: loop.fin].copy()
    L = min(int(sr * xfade_s), loop.inicio, (loop.fin - loop.inicio) // 2)
    if L > 16:
        t = np.linspace(0, 1, L)[:, None]
        g_out, g_in = np.cos(t * np.pi / 2), np.sin(t * np.pi / 2)
        y[loop.fin - L: loop.fin] = y[loop.fin - L: loop.fin] * g_out + x[loop.inicio - L: loop.inicio] * g_in
    return y


# ------------------------------------------------------------------ pads
def crear_pad(x: np.ndarray, sr: int = SR, ataque_s: float = 0.0, largo_max_s: float = 8.0) -> tuple[np.ndarray, Loop | None]:
    """Prepara un pad/ambiente: recorta, ataque suave opcional y loop sin clics."""
    y = np.asarray(x, dtype=np.float64)
    if sr != SR:
        y = dsp.to_rate(y, sr, SR)
    y = y[: int(SR * largo_max_s)]
    a = np.abs(y).max(axis=1)
    if a.max() > 0:
        on = int(np.argmax(a > a.max() * 10 ** (-50 / 20)))
        y = y[max(0, on - 32):]
    y = y * (10 ** (-1 / 20) / max(np.abs(y).max(), 1e-9))
    if ataque_s > 0:
        k = min(len(y), int(SR * ataque_s))
        y[:k] *= np.linspace(0, 1, k)[:, None] ** 2
    lp = buscar_loop(y, SR)
    if lp is not None:
        y = aplicar_loop(y, lp)
    return y, lp


# ------------------------------------------------------------------ multisample
@dataclass
class MuestraMel:
    path: str
    nombre: str
    x: np.ndarray
    nota: int
    cents: float
    como: str
    capa: float | None = None       # intensidad 0..1 si el nombre marca la capa
    loop: Loop | None = None
    usar: bool = True

    @property
    def dur(self) -> float:
        return len(self.x) / SR


def escanear(entrada, sostenido: bool = False, log=lambda s: None) -> list[MuestraMel]:
    import importar_wav as I
    items = [entrada] if isinstance(entrada, str) else list(entrada)
    paths = []
    for it in items:
        if os.path.isdir(it):
            for root, _d, files in os.walk(it):
                paths += [os.path.join(root, f) for f in sorted(files) if f.lower().endswith((".wav", ".wave"))]
        elif it.lower().endswith((".wav", ".wave")):
            paths.append(it)
    out = []
    for p in paths:
        try:
            x, sr = I.leer_wav(p)
        except Exception as e:  # noqa: BLE001
            log(f"No se pudo leer {os.path.basename(p)}: {e}")
            continue
        x = dsp.to_rate(x[:, :2], sr, SR) if sr != SR else x[:, :2]
        n, c, como = detectar_nota(p, x)
        capa = I.detectar_capa(os.path.basename(p))
        lp = buscar_loop(x) if sostenido else None
        out.append(MuestraMel(p, os.path.splitext(os.path.basename(p))[0], x, n, c, como, capa, lp))
        log(f"{os.path.basename(p)} → {note_name(n)} ({como})")
    return out


def zonas(muestras: list[MuestraMel]) -> list[tuple[int, int, int, int, MuestraMel]]:
    """Reparte el teclado: [(nota_lo, nota_hi, vel_lo, vel_hi, muestra)]."""
    import importar_wav as I
    activas = [m for m in muestras if m.usar]
    por_nota: dict[int, list[MuestraMel]] = {}
    for m in activas:
        por_nota.setdefault(m.nota, []).append(m)
    notas = sorted(por_nota)
    out = []
    for i, n in enumerate(notas):
        lo = 0 if i == 0 else (notas[i - 1] + n) // 2 + 1
        hi = 127 if i == len(notas) - 1 else (n + notas[i + 1]) // 2
        capas = sorted(por_nota[n], key=lambda m: (m.capa if m.capa is not None else 0.5,
                                                    float(np.sqrt(np.mean(m.x[: SR // 4] ** 2)))))
        for (vlo, vhi), m in zip(I.rangos(len(capas)), capas):
            out.append((lo, hi, vlo, vhi, m))
    return out


# ------------------------------------------------------------------ escribir .ppf
def es_plantilla_valida(pack: Pack) -> str | None:
    """None si sirve como plantilla de voz normal; si no, el motivo."""
    if not pack.voices:
        return "el archivo no tiene voces"
    v = pack.voices[0]
    if v.voice_type == "DRUM_KIT":
        return "es un drum kit: necesito una voz normal (piano, pad…) creada en Expansion Manager"
    if not v.elements:
        return "la voz no tiene elementos"
    if v.elements[0].waveform not in v.keybanks:
        return "la voz no tiene muestras en su primer elemento"
    return None


def _onda(nombre: str, x: np.ndarray, raiz: int, loop: Loop | None) -> Wave:
    frames = x.shape[0]
    inst = bytearray(20)
    inst[0] = raiz & 0x7F
    inst[3] = 127
    inst[4], inst[5] = 1, 127
    struct.pack_into(">hhh", inst, 8, 1 if loop else 0, 1, 2)
    mk = {1: (loop.inicio if loop else 0, "beg loop"), 2: (loop.fin if loop else frames, "end loop")}
    w = Wave(uid="", name=nombre[:31], channels=1, bits=16, rate=float(SR), frames=frames, samples=x[:, :1],
             markers=mk, inst=bytes(inst))
    w.order = [b"COMM", b"MARK", b"INST", b"SSND"]
    w._rate_raw = bytes.fromhex("400eac44000000000000")
    w._form_type = b"YTWV"
    w._comm_tail = b""
    return w


def _set(txt: str, tag: str, val, count: int = 1) -> str:
    return re.sub(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{val}</{tag}>", txt, count=count)


@dataclass
class OpcionesVoz:
    nombre: str = "Mi Voz"
    estereo: bool = False
    normalizar: bool = True
    sostenido: bool = False          # loops (pads, cuerdas, órganos)
    largo_max_s: float = 6.0


def construir(plantilla: Pack, muestras: list[MuestraMel], op: OpcionesVoz, salida: str) -> Pack:
    motivo = es_plantilla_valida(plantilla)
    if motivo:
        raise ValueError(f"Plantilla no válida: {motivo}")
    from ppf_format import voice_resource
    v = plantilla.voices[0]
    res = voice_resource(plantilla, v)
    xml = res.get(b"FBIN").rstrip(b"\0").decode("utf-8")
    wf_num = v.elements[0].waveform
    mw = re.search(rf'<waveform number="{wf_num}">.*?</waveform>', xml, re.S)
    if not mw:
        raise ValueError("No encontré la forma de onda del primer elemento en la plantilla.")
    wf = mw.group(0)
    kb_tpl = re.search(r"<keybank number=\"\d+\">.*?</keybank>", wf, re.S).group(0)
    lado = re.search(r"<sample position=\"\w+\">.*?</sample>", kb_tpl, re.S).group(0)
    ondas: dict[str, tuple] = {}
    hechas: dict[int, tuple] = {}

    def add(nombre, x, raiz, loop):
        w = _onda(nombre, x, raiz, loop)
        fbin = w.to_fbin()
        uid = hashlib.sha1(fbin).hexdigest()
        ondas.setdefault(uid, (w, fbin))
        return uid

    kbs = []
    for k, (lo, hi, vlo, vhi, m) in enumerate(zonas(muestras)):
        if id(m) not in hechas:
            y = m.x[: int(SR * op.largo_max_s)] if not m.loop else m.x
            lp = m.loop if op.sostenido else None
            if lp is not None and lp.fin <= len(y):
                y = aplicar_loop(y, lp)
            else:
                lp = None
                f = min(len(y), int(SR * 0.05))
                y = y.copy()
                y[-f:] *= np.linspace(1, 0, f)[:, None]
            if op.normalizar:
                y = y * (10 ** (-1 / 20) / max(np.abs(y).max(), 1e-9))
            y = np.clip(y, -1, 32767 / 32768)
            if op.estereo and y.shape[1] == 2:
                uids = (add(m.nombre + " L", y[:, :1], m.nota, lp), add(m.nombre + " R", y[:, 1:], m.nota, lp))
            else:
                u = add(m.nombre, y.mean(axis=1, keepdims=True), m.nota, lp)
                uids = (u, u)
            hechas[id(m)] = (uids, len(y), lp)
        uids, fr, lp = hechas[id(m)]
        b = re.sub(r'<keybank number="\d+">', f'<keybank number="{k}">', kb_tpl, count=1)
        cab, cuerpo = b.split("<sample", 1)
        cab = _set(cab, "noteLimitHi", note_name(hi))
        cab = _set(cab, "noteLimitLo", note_name(lo))
        cab = _set(cab, "velocityLimitHi", vhi)
        cab = _set(cab, "velocityLimitLo", vlo)
        cab = _set(cab, "centerNote", note_name(m.nota))
        cab = _set(cab, "tuneFine", f"{-m.cents:.6f}" if abs(m.cents) < 50 else "0.000000")
        cab = _set(cab, "samplingFrequency", f"{SR:.6f}")
        cab = _set(cab, "fixedPitch", "OFF")
        cab = _set(cab, "oneShot", "OFF" if lp else "ON")
        lados = []
        for pos, uid in (("LEFT", uids[0]), ("RIGHT", uids[1])):
            s = re.sub(r'<sample position="\w+">', f'<sample position="{pos}">', lado, count=1)
            s = _set(s, "waveFilePath", uid)
            s = _set(s, "sampleSize", fr + 4)
            s = _set(s, "loopStartPoint", lp.inicio if lp else 0)
            s = _set(s, "loopEndPoint", lp.fin if lp else fr)
            s = _set(s, "startPoint", 0)
            lados.append(s)
        kbs.append(cab + "\n   ".join(lados) + "\n  </keybank>")
    nuevo_wf = re.sub(r"<keybank number=\"\d+\">.*</keybank>", "\n  ".join(kbs), wf, count=1, flags=re.S)
    nuevo_wf = _set(nuevo_wf, "maxSampleCount", 2 * len(kbs))
    nuevo_wf = _set(nuevo_wf, "useStereoCh", "ON")
    xml = xml[:mw.start()] + nuevo_wf + xml[mw.end():]
    # el primer elemento cubre todo el teclado
    me = re.search(r'<voiceElement number="\d+"[^>]*>.*?</voiceElement>', xml, re.S)
    el = _set(_set(me.group(0), "noteLimitHi", "G8"), "noteLimitLo", "C-2")
    xml = xml[:me.start()] + el + xml[me.end():]

    nombre = re.sub(r"[^\w \-\.&']", "", op.nombre).strip()[:20] or "Mi Voz"
    referenciadas = set(re.findall(r"<waveFilePath>([^<]+)</waveFilePath>", xml))
    vuid = "{" + str(uuid.uuid4()) + "}"
    nuevos = [Resource(vuid, nombre, "uvf", [(b"EUID", vuid.encode()), (b"ETIT", nombre.encode("utf-8")), (b"EEXT", b"uvf"),
                                             (b"EICO", res.get(b"EICO") or b"T001"), (b"FBIN", xml.encode("utf-8"))])]
    for uid in sorted(ondas):
        w, fbin = ondas[uid]
        nuevos.append(Resource(uid, w.name, "APCp", [(b"EUID", uid.encode()), (b"ETIT", w.name.encode("utf-8")),
                                                     (b"EEXT", b"APCp"), (b"FBIN", fbin)]))
    # ondas de otros elementos de la plantilla que sigan en uso
    for r in plantilla.resources:
        if r.ext == "APCp" and r.uid in referenciadas and r.uid not in ondas:
            nuevos.append(r)
    puid = "{" + str(uuid.uuid4()) + "}"
    pack = Pack(salida, b"\0\0\0\0", [(b"EUID", puid.encode()), (b"ETIT", nombre.encode("utf-8"))], nuevos, [], {}, [])
    pack.save(salida)
    return load_pack(salida)


PLANTILLA_GUARDADA = "plantilla_voz.ppf"


def ruta_plantilla() -> str:
    import registro
    return os.path.join(registro.CARPETA, PLANTILLA_GUARDADA)


def guardar_plantilla(path: str) -> str:
    """Valida y recuerda la plantilla de voz normal del usuario."""
    p = load_pack(path)
    motivo = es_plantilla_valida(p)
    if motivo:
        raise ValueError(motivo)
    import shutil
    os.makedirs(os.path.dirname(ruta_plantilla()), exist_ok=True)
    shutil.copyfile(path, ruta_plantilla())
    return p.voices[0].name
