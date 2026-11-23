"""Herramientas de sonido de la versión 5:

- Mezcla de micrófonos (close / overhead / room) al importar kits multi-micrófono.
- Sala (reverb corta) integrada en la muestra.
- Capas suaves sintéticas con un modelo de timbre por velocidad.
- Nivel de referencia por pieza (similar al de los kits del teclado).
- Detección de problemas de fase en muestras estéreo.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace

import numpy as np

import dsp

SR = 44100

# ------------------------------------------------------------------ micrófonos
# (regex sobre la ruta en minúsculas, tipo de micrófono). El orden importa.
MICS = [
    (r"\b(room|rooms|sala|ambien(?:t|te|ce)?|amb|far|distant)\b", "room"),
    (r"\b(oh|ohs|overheads?|over|aereos?|a[eé]reos?|top ?mics?)\b", "oh"),
    (r"\b(bottom|bot|btm|abajo|resonan(?:t|te|cia)?|reso|out(?:side)?)\b", "close2"),
    (r"\b(close|cl|dry|direct|directo|seco|top|in(?:side)?|spot|sm ?57|d112|beta ?91|beta ?52)\b", "close"),
]
MIC_NOMBRE = {"close": "Cercano", "close2": "Cercano 2 (abajo/afuera)", "oh": "Overheads", "room": "Sala"}
_MIC_TOKENS = r"\b(room|rooms|sala|ambient|ambiente|ambience|amb|far|distant|oh|ohs|overheads?|over|aereos?|top ?mics?|" \
              r"bottom|bot|btm|abajo|resonant|resonante|reso|out|outside|close|cl|dry|direct|directo|seco|top|in|inside|spot)\b"


def detectar_mic(rel: str) -> str | None:
    """Tipo de micrófono según carpetas y nombre (None = no indica micrófono)."""
    s = re.sub(r"[_\-\.\(\)\[\]/\\]+", " ", os.path.splitext(rel)[0].lower())
    for rx, m in MICS:
        if re.search(rx, s):
            return m
    return None


def quitar_mic(texto: str) -> str:
    s = re.sub(r"[_\-\.\(\)\[\]/\\]+", " ", texto.lower())
    return re.sub(r"\s+", " ", re.sub(_MIC_TOKENS, " ", s)).strip()


@dataclass
class MezclaMics:
    """Ganancias de cada micrófono (lineal). ambiente 0..1 mueve overheads y sala."""
    ambiente: float = 0.4
    cercano2: float = 0.5

    def ganancia(self, mic: str) -> float:
        a = float(np.clip(self.ambiente, 0, 1))
        return {"close": 1.0, "close2": self.cercano2, "oh": 0.15 + 0.85 * a, "room": 1.1 * a}.get(mic, 1.0)


def mezclar_mics(archivos: list, mezcla: MezclaMics, sr: int = SR) -> list:
    """Junta en un solo golpe los archivos que solo difieren en el micrófono.

    Recibe objetos Archivo (importar_wav). Devuelve una lista nueva: los golpes
    multi-micrófono se reemplazan por su mezcla; los demás quedan igual.
    """
    grupos: dict[tuple, list] = {}
    sueltos = []
    for a in archivos:
        mic = getattr(a, "mic", None)
        if a.excluido or mic is None:
            sueltos.append(a)
            continue
        carpeta = quitar_mic(os.path.dirname(a.rel))
        nombre = quitar_mic(os.path.splitext(a.nombre)[0])
        grupos.setdefault((a.tipo, carpeta, nombre), []).append(a)
    out = list(sueltos)
    for clave, lst in grupos.items():
        mics = {a.mic for a in lst}
        if len(lst) < 2 or len(mics) < 2:
            out.extend(lst)
            continue
        comp = [(a.x, a.mic) for a in lst]
        y = _mezcla(comp, mezcla)
        ch = y.shape[1]
        base = min(lst, key=lambda a: ("close", "close2", "oh", "room").index(a.mic))
        nuevo = replace(base, x=y, canales=ch, mic="mezcla",
                        nombre=base.nombre, rel=base.rel,
                        pico_db=20 * np.log10(max(float(np.abs(y).max()), 1e-9)),
                        rms_db=20 * np.log10(max(float(np.sqrt(np.mean(y[: int(sr * 0.25)] ** 2))), 1e-9)))
        nuevo.mics = sorted(mics)
        nuevo.componentes = comp
        out.append(nuevo)
    return out


def _mezcla(comp, mezcla: MezclaMics) -> np.ndarray:
    n = max(len(x) for x, _ in comp)
    ch = 2 if any(x.shape[1] == 2 for x, _ in comp) else 1
    y = np.zeros((n, ch))
    for x, mic in comp:
        x = x if x.shape[1] == ch else np.repeat(x[:, :1], ch, axis=1)
        y[: len(x)] += x * mezcla.ganancia(mic)
    pk = np.abs(y).max()
    if pk > 0.99:
        y *= 0.99 / pk
    return y


_CACHE_MEZCLA: dict = {}


def audio_archivo(a, ambiente: float) -> np.ndarray:
    """Audio de un golpe; si es multi-micrófono, mezclado con el ambiente pedido."""
    comp = getattr(a, "componentes", None)
    if not comp:
        return a.x
    k = (id(a), round(float(ambiente), 2))
    if k not in _CACHE_MEZCLA:
        if len(_CACHE_MEZCLA) > 256:
            _CACHE_MEZCLA.clear()
        _CACHE_MEZCLA[k] = _mezcla(comp, MezclaMics(ambiente))
    return _CACHE_MEZCLA[k]


def hay_multimic(archivos: list) -> bool:
    mics = {getattr(a, "mic", None) for a in archivos if not a.excluido}
    return len(mics - {None}) >= 2


# ------------------------------------------------------------------ sala
_IR_SALA: dict = {}


def _ir_sala(sr: float, tam: float, ch: int) -> np.ndarray:
    """Sala corta: reflexiones tempranas + cola de ruido que decae (RT60 0.3–0.9 s)."""
    key = (sr, round(tam, 2), ch)
    if key in _IR_SALA:
        return _IR_SALA[key]
    rng = np.random.default_rng(7)
    rt = 0.3 + 0.6 * tam
    n = int(sr * rt * 1.2)
    t = np.arange(n) / sr
    ir = np.zeros((n, ch))
    for c in range(ch):
        cola = rng.standard_normal(n) * np.exp(-6.91 * t / rt)
        cola[: int(sr * 0.012)] = 0
        er = np.zeros(n)
        for k in range(10):
            d = int(sr * (0.003 + 0.0035 * k * (1 + tam)) * (1 + 0.07 * c))
            if d < n:
                er[d] += (0.8 ** k) * (1 if (k + c) % 2 else -1)
        ir[:, c] = er + cola * 0.35
    ir = dsp.lpf(ir, sr, 9000 - 4000 * tam)
    ir /= np.sqrt((ir ** 2).sum(axis=0, keepdims=True)) + 1e-12
    _IR_SALA[key] = ir
    return ir


def sala(x: np.ndarray, sr: float, cantidad: float, tam: float = 0.5) -> np.ndarray:
    """Añade una sala corta a la muestra (cantidad 0..1). Alarga la cola lo justo."""
    if cantidad <= 0.001 or len(x) < 32:
        return x
    x = np.asarray(x, dtype=np.float64)
    ch = x.shape[1]
    tam = float(np.clip(tam, 0, 1))
    ir = _ir_sala(sr, tam, ch)
    xp = np.vstack([x, np.zeros((len(ir), ch))])
    wet = np.stack([dsp_conv(xp[:, c], ir[:, c])[: len(xp)] for c in range(ch)], axis=1)
    wet = dsp.hpf(wet, sr, 180)          # la sala no ensucia los graves
    rms = lambda v: float(np.sqrt(np.mean(v[: int(sr * 0.3)] ** 2))) + 1e-12
    y = xp + wet * (rms(x) / rms(wet)) * 0.6 * float(cantidad)
    pk_dry = np.abs(x).max() or 1
    pk = np.abs(y).max()
    if pk > pk_dry:
        y *= pk_dry / pk
    a = np.abs(y).max(axis=1)
    idx = np.where(a > pk_dry * 10 ** (-66 / 20))[0]
    end = min(len(y), (idx[-1] if len(idx) else len(y)) + int(sr * 0.01))
    y = y[:end].copy()
    f = min(len(y), int(sr * 0.04))
    if f > 1:
        y[-f:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, f)))[:, None]
    return y


def dsp_conv(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    import sig
    return sig.fftconvolve(x, h)


# ------------------------------------------------------------------ capas suaves
CORTE = {"bombo": 2200, "caja": 3200, "tom": 2600, "hihat": 4500, "ride": 4500, "crash": 4000, "perc": 3600}


def capa_suave(x: np.ndarray, sr: float, tipo: str, factor: float, touch_db: float = -12.0) -> np.ndarray:
    """Golpe suave sintetizado a partir del fuerte, con un modelo de timbre por velocidad.

    factor: 1 = la capa más suave, 0.5 = intermedia. Un golpe suave real tiene:
    menos agudos (el parche/plato vibra menos), un ataque más blando y menos
    "crack", menos sustain relativo en los platos y algo más de cuerpo relativo.
    """
    f = float(np.clip(factor, 0.05, 1.0))
    y = np.asarray(x, dtype=np.float64)
    pk0 = np.abs(y).max()
    if pk0 == 0 or len(y) < 64:
        return y.copy()
    # 1) brillo: corte que baja con la suavidad, con pendiente de 24 dB/oct
    fc = CORTE.get(tipo, 3500) * (1 / f) ** 0.9
    fc = min(fc, sr * 0.45)
    y = dsp.lpf(dsp.lpf(y, sr, fc, 0.6), sr, fc * 1.25, 0.6)
    # 2) menos "aire" en platos y cajas
    if tipo in ("hihat", "ride", "crash", "caja"):
        y = dsp.shelf(y, sr, 7000, -6.0 * f, high=True)
    # 3) cuerpo relativo
    cuerpo = {"bombo": 70, "caja": 220, "tom": 140}.get(tipo)
    if cuerpo:
        y = dsp.peak(y, sr, cuerpo, 2.0 * f, 0.9)
    # 4) ataque más blando: transitorio reducido y rampa de 1-4 ms
    y = dsp.transient(y, sr, -0.6 * f)
    n = int(sr * (0.001 + 0.003 * f))
    on = int(np.argmax(np.abs(y).max(axis=1) > pk0 * 0.05))
    if 0 < n < len(y) - on:
        y[on:on + n] *= np.linspace(0.35 + 0.4 * (1 - f), 1, n)[:, None]
    # 5) platos: el golpe suave se apaga antes
    if tipo in ("ride", "crash", "hihat"):
        t = np.arange(len(y)) / sr
        y = y * np.exp(-t * (0.6 * f))[:, None]
    pk = np.abs(y).max()
    y = y * (pk0 / pk) if pk > 0 else y
    # 6) cola que no se oiría a esa velocidad
    thr = pk0 * 10 ** ((-74 - touch_db) / 20)
    a = np.abs(y).max(axis=1)
    idx = np.where(a > thr)[0]
    if len(idx):
        end = min(len(y), idx[-1] + int(sr * 0.02))
        y = y[:end].copy()
        k = min(len(y), int(sr * 0.03))
        if k > 1:
            y[-k:] *= (0.5 - 0.5 * np.cos(np.linspace(np.pi, 0, k)))[:, None]
    return y


# ------------------------------------------------------------------ nivel de referencia
# RMS de los primeros 250 ms (dBFS) y pico máximo, por familia: valores típicos de
# kits de fábrica de teclados arranger, para que el kit no salte al cambiar de voz.
NIVEL_REF = {"bombo": -13.0, "caja": -14.0, "tom": -15.0, "hihat": -24.0, "ride": -22.0, "crash": -19.0, "perc": -20.0}
TECHO_DB = -0.5


def ganancia_referencia(x: np.ndarray, sr: float, tipo: str) -> float:
    """dB a aplicar para acercar la muestra al nivel de referencia sin saturar."""
    actual = dsp.rms_db(x, sr)
    g = NIVEL_REF.get(tipo, -18.0) - actual
    return float(min(g, TECHO_DB - dsp.peak_db(x)))


# ------------------------------------------------------------------ fase estéreo
@dataclass
class Fase:
    correlacion: float          # -1..1 (1 = idénticos, 0 = sin relación, <0 = invertidos)
    perdida_graves_db: float    # cuánto bajan los graves (<200 Hz) al sumar a mono
    invertido: bool

    @property
    def problema(self) -> str | None:
        if self.invertido:
            return "un canal está invertido de fase: en mono casi desaparece"
        if self.perdida_graves_db >= 3:
            return f"pierde {self.perdida_graves_db:.0f} dB de graves al sumarse a mono (desfase entre micrófonos)"
        if self.correlacion < 0.1:
            return "canales casi sin relación: en mono suena hueco"
        return None


def fase(l: np.ndarray, r: np.ndarray, sr: float = SR) -> Fase:
    n = min(len(l), len(r), int(sr * 0.5))
    a = np.asarray(l[:n], dtype=np.float64).ravel()
    b = np.asarray(r[:n], dtype=np.float64).ravel()
    if n < 64 or not a.any() or not b.any():
        return Fase(1.0, 0.0, False)
    corr = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    la = dsp.lpf(a[:, None], sr, 200)[:, 0]
    lb = dsp.lpf(b[:, None], sr, 200)[:, 0]
    e_sep = (np.mean(la ** 2) + np.mean(lb ** 2)) / 2
    e_mono = np.mean(((la + lb) / 2) ** 2)
    perdida = float(10 * np.log10((e_sep + 1e-15) / (e_mono + 1e-15)))
    return Fase(corr, max(0.0, perdida), corr < -0.5)


def corregir_fase(l: np.ndarray, r: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
    """Si un canal está invertido lo da vuelta; si hay retardo entre canales, lo alinea."""
    f = fase(l, r)
    if f.invertido:
        return l, -r, "canal derecho invertido corregido"
    n = min(len(l), len(r), int(SR * 0.2))
    a, b = l[:n].ravel(), r[:n].ravel()
    lag_max = int(SR * 0.002)
    best, lag = -2.0, 0
    for k in range(-lag_max, lag_max + 1):
        if k >= 0:
            c = np.dot(a[k:], b[: n - k])
        else:
            c = np.dot(a[: n + k], b[-k:])
        if c > best:
            best, lag = c, k
    if lag == 0:
        return l, r, ""
    rr = np.roll(r, lag, axis=0)
    if lag > 0:
        rr[:lag] = 0
    else:
        rr[lag:] = 0
    return l, rr, f"canales alineados ({abs(lag) / SR * 1000:.2f} ms)"
