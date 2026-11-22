"""Crear un drum kit .ppf a partir de una carpeta de WAV (cualquier pack).

1. escanear():   lee todos los WAV (PCM/float, mono/estéreo, cualquier frecuencia),
                 detecta la pieza por la ruta (carpetas + nombre) o por el sonido,
                 y descarta loops / demos.
2. agrupar():    junta las versiones de un mismo golpe (RD_K_1…RD_K_10) y las capas
                 de velocidad marcadas en el nombre (soft/hard, pp/ff, v1/v2…).
3. auto_kit():   propone un kit: una pieza por tecla General MIDI, con variantes en
                 las teclas secundarias (bombo 2, caja 2, crash 2…).
4. El usuario puede editar cada pieza (tecla, tipo, versión, capas, afinación).
5. planificar(): prepara el audio y ajusta el kit a la memoria del teclado.
6. construir():  escribe el .ppf (plantilla de drum kit de Expansion Manager).
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import struct
import sys
import uuid
from dataclasses import dataclass, field

import numpy as np

import dsp
import modelos
from ppf_format import Pack, Resource, Wave, load_pack, note_name

BASE = os.path.dirname(os.path.abspath(__file__))
PLANTILLAS = os.path.join(getattr(sys, "_MEIPASS", BASE), "plantillas")
SR = 44100

# ----------------------------------------------------------------- piezas
# tipo -> (nombre visible, notas GM preferidas, familia de proceso)
PIEZAS = {
    "kick": ("Bombo", [36, 35], "bombo"),
    "snare": ("Caja", [38, 40], "caja"),
    "rim": ("Aro / Side stick", [37], "caja"),
    "clap": ("Palmas", [39], "caja"),
    "tom": ("Tom", [50, 48, 47, 45, 43, 41], "tom"),
    "hh_closed": ("Hi-hat cerrado", [42], "hihat"),
    "hh_pedal": ("Hi-hat pedal", [44], "hihat"),
    "hh_open": ("Hi-hat abierto", [46], "hihat"),
    "crash": ("Crash", [49, 57], "crash"),
    "ride": ("Ride", [51, 59], "ride"),
    "bell": ("Campana del ride", [53], "ride"),
    "splash": ("Splash", [55], "crash"),
    "china": ("China", [52], "crash"),
    "tamb": ("Pandereta", [54], "perc"),
    "cowbell": ("Cencerro", [56], "perc"),
    "shaker": ("Shaker", [70, 82], "perc"),
    "perc": ("Percusión", [60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 72, 73, 74, 75, 76, 77, 78, 79], "perc"),
}
TIPOS = list(PIEZAS)

GM = {35: "Bombo 2", 36: "Bombo", 37: "Side stick", 38: "Caja", 39: "Palmas", 40: "Caja 2", 41: "Tom piso grave",
      42: "Hi-hat cerrado", 43: "Tom piso agudo", 44: "Hi-hat pedal", 45: "Tom grave", 46: "Hi-hat abierto",
      47: "Tom medio grave", 48: "Tom medio agudo", 49: "Crash 1", 50: "Tom agudo", 51: "Ride", 52: "China",
      53: "Campana ride", 54: "Pandereta", 55: "Splash", 56: "Cencerro", 57: "Crash 2", 59: "Ride 2", 70: "Maracas"}


def nombre_tecla(n: int) -> str:
    return f"{note_name(n)} · {GM[n]}" if n in GM else note_name(n)


REGLAS = [  # (regex sobre ruta+nombre en minúsculas, tipo) — el orden importa
    (r"sleigh|cascabel|jingle", "perc"),
    (r"stick.?hit|\bsticks\b|block|woodblock|clave", "perc"),
    (r"ride.?bell|campana.?ride|\bcup\b|\bbell\b(?!s)", "bell"),
    (r"(hi.?hat|\bhh\b|hat|chimbal|cimbal|charles|contratiempo).*(open|abiert|aberto|\bop\b|\bo\b)|\bohh?\b|open.?h", "hh_open"),
    (r"(hi.?hat|\bhh\b|hat|chimbal|cimbal|charles).*(pedal|foot|pie|\bpd\b|chick)|pedal.?h|\bphh\b", "hh_pedal"),
    (r"hi.?hat|\bhh\b|\bchh\b|\bhat\b|chimbal|cimbal|charles|contratiempo", "hh_closed"),
    (r"splash", "splash"),
    (r"china", "china"),
    (r"\bride\b|condu[cç][aã]o|conducci[oó]n", "ride"),
    (r"crash|prato|plato|cymbal|platillo|\bcym", "crash"),
    (r"side.?stick|cross.?stick|\brim|\baro\b|\bxstick", "rim"),
    (r"clap|palma", "clap"),
    (r"kick|bumbo|bombo|\bbd\b|bass.?drum|\bkik\b", "kick"),
    (r"snare|caixa|caja|tarola|redoblante|\bsd\b|\bsnr\b", "snare"),
    (r"\btoms?\b|surdo|floor|\bft\b|timbal", "tom"),
    (r"tamb|pandeiro|pandero|pandereta", "tamb"),
    (r"cowbell|cencerro", "cowbell"),
    (r"shak|maraca|ganz|egg", "shaker"),
    (r"percus", "perc"),
]
EXCLUIR = r"\d+\s?bpm|\bloop|\bdemo\b|\bbonus\b|\bgroove\b|\bfill\b|\bsong\b|\bbeat\b"

CAPA_TOKENS = [  # (regex, intensidad 0..1)
    (r"\b(ppp|ghost|fantasma)\b", 0.05), (r"\bpp\b", 0.15), (r"\b(p|soft|suave|piano|low|lo|light|ligero)\b", 0.25),
    (r"\bmp\b", 0.4), (r"\b(mf|med|medium|medio|mid|mezzo)\b", 0.55), (r"\b(f|forte|hard|fuerte|loud|hi|high|alto)\b", 0.8),
    (r"\bff+\b", 0.95), (r"\b(accent|acento|max)\b", 1.0),
]
ALTURA_WORDS = r"hi|high|mid|medium|med|low|lo|alto|bajo|medio|agudo|grave|floor"
TOM_ALTURA = [(r"\b(hi|high|alto|agudo|rack ?1|tom ?1)\b", 0), (r"\b(mid|medio|medium|rack ?2|tom ?2)\b", 1),
              (r"\b(low|lo|bajo|grave|tom ?3)\b", 2), (r"\b(floor|ft|surdo|base|piso)\b", 3)]


# ----------------------------------------------------------------- lectura
def leer_wav(path: str) -> tuple[np.ndarray, int]:
    """Lee WAV PCM 8/16/24/32 bits o float 32/64 (también WAVE_FORMAT_EXTENSIBLE)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("no es un archivo WAV")
    p, fmt, raw = 12, None, None
    while p + 8 <= len(data):
        cid = data[p:p + 4]
        n = struct.unpack("<I", data[p + 4:p + 8])[0]
        body = data[p + 8:p + 8 + n]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            raw = body
        p += 8 + n + (n & 1)
    if fmt is None or raw is None:
        raise ValueError("WAV sin bloques fmt/data")
    tag, ch, sr, _, _align, bits = struct.unpack("<HHIIHH", fmt[:16])
    if tag == 0xFFFE and len(fmt) >= 26:
        tag = struct.unpack("<H", fmt[24:26])[0]
    bps = bits // 8
    raw = raw[:len(raw) - len(raw) % (bps * ch)]
    if tag == 3:
        x = np.frombuffer(raw, "<f4" if bits == 32 else "<f8").astype(np.float64)
    elif tag == 1:
        if bits == 8:
            x = (np.frombuffer(raw, np.uint8).astype(np.float64) - 128) / 128
        elif bits == 16:
            x = np.frombuffer(raw, "<i2") / 32768.0
        elif bits == 24:
            b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
            v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            x = np.where(v >= 1 << 23, v - (1 << 24), v) / 8388608.0
        elif bits == 32:
            x = np.frombuffer(raw, "<i4") / 2147483648.0
        else:
            raise ValueError(f"{bits} bits no soportado")
    else:
        raise ValueError(f"formato WAV {tag} no soportado (usa PCM o float)")
    return x.reshape(-1, ch).astype(np.float64), sr


# ----------------------------------------------------------------- análisis
def _limpio(texto: str) -> str:
    s = os.path.splitext(texto)[0].lower()
    s = re.sub(r"[_\-\.\(\)\[\]/\\]+", " ", s)
    s = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def detectar_tipo(ruta_rel: str, x, sr) -> tuple[str, bool]:
    """(tipo, seguro). Por la ruta y el nombre; si no, por el sonido."""
    s = _limpio(ruta_rel)
    for rx, t in REGLAS:
        if re.search(rx, s):
            return t, True
    if x is None or not len(x):
        return "perc", False
    db, f = dsp.spectrum_db(x, sr, 48)
    pw = 10 ** (db / 10)
    cen = float((f * pw).sum() / pw.sum())
    dur = len(x) / sr
    if cen < 180:
        return "kick", False
    if cen < 500:
        return ("tom" if dur > 0.35 else "kick"), False
    if cen < 2500:
        return "snare", False
    return ("crash" if dur > 1.2 else "hh_closed"), False


def _proteger(s: str) -> str:
    return re.sub(rf"\b({ALTURA_WORDS})\b", lambda m: f"Z{m.group(1).upper()}Z", s)


def _restaurar(s: str) -> str:
    return re.sub(r"Z([A-Z]+)Z", lambda m: m.group(1).lower(), s)


def detectar_capa(nombre: str, tipo: str = "") -> float | None:
    s = _limpio(nombre)
    if tipo == "tom":                     # en los toms, hi/mid/low es la altura del tom
        s = _proteger(s)
    for rx, v in CAPA_TOKENS:
        if re.search(rx, s):
            return v
    m = re.search(r"\b(?:v|vel|velocity|layer|capa)\s?(\d{1,3})\b", s)
    if m:
        k = int(m.group(1))
        return min(1.0, k / (127 if k > 10 else 10))
    return None


def base_nombre(nombre: str, tipo: str = "") -> str:
    """Nombre sin capa, round robin ni número final: lo que comparten las versiones de un golpe."""
    s = _limpio(nombre)
    if tipo == "tom":
        s = _proteger(s)
    s = re.sub(r"\b(?:rr|round robin|alt|var|take)\s?\d*\b", " ", s)
    s = re.sub(r"\b(?:v|vel|velocity|layer|capa)\s?\d{1,3}\b", " ", s)
    for rx, _ in CAPA_TOKENS:
        s = re.sub(rx, " ", s)
    s = re.sub(r"\s\d+$", "", re.sub(r"\s+", " ", s).strip())
    return _restaurar(s.strip())


def altura_hz(x: np.ndarray, sr: int) -> float:
    m = x.mean(axis=1)[: int(sr * 0.5)]
    if len(m) < 256:
        return 0.0
    X = np.abs(np.fft.rfft(m * np.hanning(len(m))))
    f = np.fft.rfftfreq(len(m), 1 / sr)
    band = (f > 40) & (f < 450)
    return float(f[band][np.argmax(X[band])]) if band.any() else 0.0


def decaimiento_s(x: np.ndarray, sr: int) -> float:
    a = np.abs(x).max(axis=1)
    if not len(a) or a.max() == 0:
        return 0.0
    idx = np.where(a > a.max() * 10 ** (-40 / 20))[0]
    return float(idx[-1] / sr) if len(idx) else 0.0


def _num(s: str) -> int:
    m = re.findall(r"\d+", os.path.splitext(os.path.basename(s))[0])
    return int(m[-1]) if m else 0


@dataclass
class Archivo:
    path: str
    rel: str                 # ruta relativa a la carpeta importada
    nombre: str
    x: np.ndarray            # audio a 44.1 kHz
    canales: int
    sr_orig: int
    tipo: str
    seguro: bool
    capa: float | None
    base: str
    pico_db: float
    rms_db: float
    altura: float
    decae: float
    excluido: str = ""       # motivo si no se usa (loop, error…)

    @property
    def dur(self) -> float:
        return len(self.x) / SR


@dataclass
class Grupo:
    """Versiones de un mismo golpe (o capas de velocidad marcadas en el nombre)."""
    tipo: str
    clave: str
    archivos: list[Archivo]
    capas_en_nombre: bool = False

    @property
    def nombre(self) -> str:
        partes = [c for c in os.path.dirname(self.archivos[0].rel).replace("\\", "/").split("/") if c] if self.archivos else []
        carpeta = partes[-1] if partes else ""
        if carpeta and len(partes) > 1 and not any(re.search(rx, _limpio(carpeta)) for rx, _ in REGLAS):
            carpeta = f"{partes[-2]} {carpeta}"     # "Snare/Processed" -> "Snare Processed"
        b = self.archivos[0].base if self.archivos else ""
        txt = carpeta or b or PIEZAS[self.tipo][0]
        if b and carpeta and b.replace(" ", "") not in carpeta.lower().replace(" ", "") and len(b) < 14 and not re.fullmatch(r"[a-z]{1,3}( [a-z]{1,3})*", b):
            txt = f"{carpeta} {b}"
        if self.tipo == "hh_open" and not re.search(r"open|abiert|aberto", txt.lower()):
            txt += " abierto"
        return txt.strip().title()[:24]

    def por_volumen(self) -> list[Archivo]:
        if self.capas_en_nombre:
            return sorted(self.archivos, key=lambda a: (a.capa if a.capa is not None else 0.5, a.rms_db))
        return sorted(self.archivos, key=lambda a: a.rms_db)


@dataclass
class Pieza:
    """Una tecla del kit."""
    nota: int
    tipo: str
    grupo: Grupo
    version: int = 0          # índice en grupo.archivos (versión principal / capa más fuerte)
    capas: int = 1            # nº de capas de velocidad
    afinacion: int = 0        # semitonos
    usar: bool = True
    copia_de: int | None = None   # nota cuya muestra reutiliza (sin memoria extra)

    @property
    def nombre(self) -> str:
        return self.grupo.nombre

    @property
    def max_capas(self) -> int:
        return len(self.grupo.archivos)

    def seleccion(self, max_capas: int | None = None) -> list[Archivo]:
        """Archivos de suave a fuerte para esta tecla."""
        n = max(1, min(self.capas, max_capas or self.capas, len(self.grupo.archivos)))
        if self.grupo.capas_en_nombre:
            orden = self.grupo.por_volumen()
            return _repartir(orden, n)
        principal = self.grupo.archivos[min(self.version, len(self.grupo.archivos) - 1)]
        if n == 1:
            return [principal]
        # capas a partir de versiones: la principal es la más fuerte; el resto, las más suaves
        resto = [a for a in self.grupo.por_volumen() if a is not principal and a.rms_db <= principal.rms_db + 0.5]
        if len(resto) < n - 1:
            resto = [a for a in self.grupo.por_volumen() if a is not principal]
        return sorted(_repartir(resto, n - 1), key=lambda a: a.rms_db) + [principal]


def _repartir(lst, n):
    if len(lst) <= n:
        return list(lst)
    idx = sorted({round(k * (len(lst) - 1) / max(1, n - 1)) for k in range(n)})
    return [lst[i] for i in idx]


def escanear(entrada, log=lambda s: None, progreso=lambda i, n: None) -> list[Archivo]:
    items = [entrada] if isinstance(entrada, str) else list(entrada)
    paths = []
    for it in items:
        if os.path.isdir(it):
            for root, dirs, files in os.walk(it):
                dirs.sort()
                for f in sorted(files, key=lambda s: (_limpio(re.sub(r"\d+", "", s)), _num(s))):
                    if f.lower().endswith((".wav", ".wave")):
                        paths.append((os.path.join(root, f), os.path.relpath(os.path.join(root, f), it)))
        elif it.lower().endswith((".wav", ".wave")):
            paths.append((it, os.path.basename(it)))
    out = []
    for k, (p, rel) in enumerate(paths):
        progreso(k, len(paths))
        nombre = os.path.basename(p)
        rel_l = _limpio(rel)
        try:
            x, sr = leer_wav(p)
            ch = min(2, x.shape[1])
            x = x[:, :2]
            dur = len(x) / max(sr, 1)
            excl = ""
            if re.search(EXCLUIR, rel_l) or dur > 12:
                excl = "loop o demo (no es un golpe)"
            x44 = dsp.to_rate(x, sr, SR) if not excl else x[: int(sr * 0.1)]
            tipo, seguro = detectar_tipo(rel, x44, SR)
            pk = float(np.abs(x44).max()) if len(x44) else 0
            rms = float(np.sqrt(np.mean(x44[: int(SR * 0.25)] ** 2))) if len(x44) else 0
            out.append(Archivo(p, rel, nombre, x44, ch, sr, tipo, seguro, detectar_capa(nombre, tipo), base_nombre(nombre, tipo),
                               20 * np.log10(max(pk, 1e-9)), 20 * np.log10(max(rms, 1e-9)), altura_hz(x44, SR),
                               decaimiento_s(x44, SR), excl))
            log(f"Leído {rel}")
        except Exception as e:  # noqa: BLE001
            out.append(Archivo(p, rel, nombre, np.zeros((0, 1)), 1, 0, "perc", False, None, "", -120, -120, 0, 0,
                               excluido=f"no se pudo leer: {e}"))
    progreso(len(paths), len(paths))
    return out


def agrupar(archivos: list[Archivo]) -> list[Grupo]:
    grupos: dict[tuple, Grupo] = {}
    for a in archivos:
        if a.excluido:
            continue
        carpeta = _limpio(os.path.dirname(a.rel))
        clave = (a.tipo, carpeta, a.base)
        g = grupos.setdefault(clave, Grupo(a.tipo, " | ".join(clave), []))
        g.archivos.append(a)
    out = list(grupos.values())
    for g in out:
        g.archivos.sort(key=lambda a: (_num(a.nombre), a.nombre))
        g.capas_en_nombre = sum(a.capa is not None for a in g.archivos) >= 2 and len({a.capa for a in g.archivos}) >= 2
    # hi-hat sin marcas: separar cerrado / abierto por duración
    nuevos = []
    for g in out:
        if g.tipo == "hh_closed" and not g.capas_en_nombre and len(g.archivos) >= 4:
            largos = [a for a in g.archivos if a.decae > 0.6]
            cortos = [a for a in g.archivos if a.decae <= 0.6]
            if largos and cortos:
                g.archivos = cortos
                for a in largos:
                    a.tipo = "hh_open"
                nuevos.append(Grupo("hh_open", g.clave + " | abierto", largos))
    return out + nuevos


def _orden_tom(g: Grupo):
    s = _limpio(g.archivos[0].rel)
    for rx, k in TOM_ALTURA:
        if re.search(rx, s):
            return (k, -g.archivos[0].altura)
    return (1.5, -g.archivos[0].altura)


def auto_kit(grupos: list[Grupo], completar_gm: bool = True) -> list[Pieza]:
    """Propone un kit: cada tipo en sus teclas GM; las teclas secundarias usan otras versiones."""
    piezas: list[Pieza] = []
    usadas: set[int] = set()
    por_tipo: dict[str, list[Grupo]] = {}
    for g in grupos:
        por_tipo.setdefault(g.tipo, []).append(g)

    def poner(nota, tipo, g, version=0, afin=0):
        piezas.append(Pieza(nota, tipo, g, version=version, afinacion=afin,
                            capas=min(3, len(g.archivos)) if g.capas_en_nombre else 1))
        usadas.add(nota)

    # toms: de agudo a grave sobre 50, 48, 47, 45, 43, 41
    toms = sorted(por_tipo.get("tom", []), key=_orden_tom)
    slots = PIEZAS["tom"][1]
    if toms:
        n = len(toms)
        idx = [round(k * (len(slots) - 1) / max(1, n - 1)) for k in range(n)] if n > 1 else [2]
        for g, k in zip(toms, idx[:len(slots)]):
            poner(slots[k], "tom", g)
    for tipo in TIPOS:
        if tipo == "tom":
            continue
        gs = por_tipo.get(tipo, [])
        notas = PIEZAS[tipo][1]
        for k, g in enumerate(gs):
            libres = [n for n in notas if n not in usadas] or [n for n in PIEZAS["perc"][1] if n not in usadas]
            if libres:
                poner(libres[0], tipo, g)
        # teclas secundarias con otra versión del mismo golpe (bombo 2, caja 2, crash 2, ride 2)
        if completar_gm and gs and tipo in ("kick", "snare", "crash", "ride"):
            g0 = gs[0]
            for n in notas:
                if n not in usadas and len(g0.archivos) > 1:
                    poner(n, tipo, g0, version=1)
    if completar_gm and toms:
        hechos = [p for p in piezas if p.tipo == "tom"]
        for n in slots:
            if n not in usadas:
                src = min(hechos, key=lambda p: abs(p.nota - n))
                st = max(-7, min(7, round((n - src.nota) * 0.7)))
                piezas.append(Pieza(n, "tom", src.grupo, version=src.version, afinacion=src.afinacion + st, copia_de=src.nota))
                usadas.add(n)
    if completar_gm:
        hh = next((p for p in piezas if p.tipo == "hh_closed"), None)
        if hh is not None and 44 not in usadas:
            piezas.append(Pieza(44, "hh_pedal", hh.grupo, version=hh.version, afinacion=-1, copia_de=hh.nota))
    return sorted(piezas, key=lambda p: p.nota)


# ----------------------------------------------------------------- opciones
@dataclass
class OpcionesImport:
    nombre: str = "Mi Kit"
    modelo: str = modelos.POR_DEFECTO
    estereo_platos: bool = True
    procesar: bool = True
    intensidad: float = 0.5
    dinamica_natural: bool = False
    hihat_grupo: bool = True


LARGO_MAX = {"bombo": 1.6, "caja": 1.8, "tom": 2.5, "hihat": 1.6, "ride": 5.0, "crash": 5.0, "perc": 2.0}


def _preparar(x: np.ndarray, mono: bool, largo: float, tail_db: float) -> np.ndarray:
    y = x.mean(axis=1, keepdims=True) if mono and x.shape[1] > 1 else x.copy()
    a = np.abs(y).max(axis=1)
    if not len(a) or a.max() == 0:
        return y
    pk = a.max()
    on = np.where(a > pk * 10 ** (-50 / 20))[0]
    start = max(0, on[0] - int(SR * 0.001)) if len(on) else 0
    y, a = y[start:], a[start:]
    tail = np.where(a > pk * 10 ** (tail_db / 20))[0]
    end = min(len(y), (tail[-1] if len(tail) else len(y)) + int(SR * 0.02), int(SR * largo))
    y = y[:end].copy()
    n = min(len(y), int(SR * 0.03))
    if n > 1:
        y[-n:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, n)))[:, None]
    m = min(len(y), 24)
    y[:m] *= np.linspace(0, 1, m)[:, None]
    return y


def rangos(n: int) -> list[tuple[int, int]]:
    if n <= 1:
        return [(1, 127)]
    fijos = {2: [79], 3: [55, 99], 4: [40, 70, 100], 5: [32, 56, 80, 104]}
    cortes = fijos.get(n) or [round(127 * k / n) for k in range(1, n)]
    out, lo = [], 1
    for c in cortes:
        out.append((lo, c))
        lo = c + 1
    out.append((lo, 127))
    return out


@dataclass
class Plan:
    piezas: list[Pieza]
    audio: dict                    # (id(Archivo), mono) -> np.ndarray
    capas: dict                    # nota -> [(vlo, vhi, clave_audio)]
    mb: float
    pasos: list[str] = field(default_factory=list)


def planificar(piezas: list[Pieza], op: OpcionesImport, log=lambda s: None) -> Plan:
    """Prepara el audio y ajusta capas/colas a la memoria del modelo."""
    from mejora import procesar
    m = modelos.MODELOS[op.modelo]
    activas = [p for p in piezas if p.usar]
    tope_capas = 2 if m.memoria_mb < 100 else 4
    estereo = op.estereo_platos and m.memoria_mb >= 100
    factor, tail_db = 1.0, -60.0
    pasos: list[str] = []
    for intento in range(10):
        audio, capas_map = {}, {}
        for p in activas:
            fam = PIEZAS[p.tipo][2]
            sel = p.seleccion(tope_capas)
            mono = not (estereo and (fam in ("crash", "ride") or p.tipo == "hh_open"))
            claves = []
            pk_fuerte = None
            for a in sel:
                k = (id(a), mono, round(factor, 2), tail_db)
                if k not in audio:
                    y = _preparar(a.x, mono, LARGO_MAX[fam] * factor, tail_db)
                    if op.procesar and len(y) > 32:
                        y = procesar(y, SR, fam, op.intensidad)
                    audio[k] = y
                claves.append(k)
            pk_fuerte = max((np.abs(audio[k]).max() for k in claves if len(audio[k])), default=1) or 1
            capas_map[p.nota] = []
            for (lo, hi), k in zip(rangos(len(claves)), claves):
                y = audio[k]
                ref = pk_fuerte if op.dinamica_natural else max(np.abs(y).max(), 1e-9)
                kk = k + (op.dinamica_natural and round(float(pk_fuerte), 4),)
                if kk not in audio:
                    audio[kk] = np.clip(y * (10 ** (-0.5 / 20) / ref), -1, 32767 / 32768)
                capas_map[p.nota].append((lo, hi, kk))
        usadas = {k for v in capas_map.values() for _, _, k in v}
        mb = sum(audio[k].shape[0] * audio[k].shape[1] * 2 for k in usadas) / 1e6
        if mb <= m.kit_max_mb or intento == 9:
            break
        if estereo:
            estereo = False
            pasos.append("platos en mono")
        elif factor > 0.55:
            factor = round(factor - 0.15, 2)
            tail_db += 6
            pasos.append(f"colas más cortas ({factor * 100:.0f} %)")
        elif tope_capas > 1:
            tope_capas -= 1
            pasos.append(f"máximo {tope_capas} capa(s)")
        else:
            factor = round(factor * 0.8, 2)
            pasos.append("colas aún más cortas")
        log(f"Ajustando a la memoria del {m.nombre}: {pasos[-1]}")
    audio = {k: v for k, v in audio.items() if k in usadas}
    return Plan(piezas, audio, capas_map, mb, pasos)


# ----------------------------------------------------------------- escribir
_INST_CHUNK = bytes.fromhex("3c00000000000000000000010002000000000000")
_RATE_44100 = bytes.fromhex("400eac44000000000000")


def _onda(nombre: str, x: np.ndarray) -> Wave:
    w = Wave(uid="", name=nombre[:31], channels=1, bits=16, rate=float(SR), frames=x.shape[0], samples=x[:, :1],
             markers={1: (0, "beg loop"), 2: (x.shape[0], "end loop")}, inst=_INST_CHUNK)
    w.order = [b"COMM", b"MARK", b"INST", b"SSND"]
    w._rate_raw = _RATE_44100
    w._form_type = b"YTWV"
    w._comm_tail = b""
    return w


def _sub_elemento(xml: str, nota: int, bloque: str, tag: str, valor: str) -> str:
    em = re.search(rf'<voiceElement number="{nota}"[^>]*>.*?</voiceElement>', xml, re.S)
    if not em:
        return xml
    el = em.group(0)
    if bloque:
        bm = re.search(rf"<{bloque}\b.*?</{bloque}>", el, re.S)
        nb = re.sub(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{valor}</{tag}>", bm.group(0), count=1)
        el = el[:bm.start()] + nb + el[bm.end():]
    else:
        el = re.sub(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{valor}</{tag}>", el, count=1)
    return xml[:em.start()] + el + xml[em.end():]


def construir(plan: Plan, op: OpcionesImport, salida: str) -> Pack:
    xml = gzip.decompress(open(os.path.join(PLANTILLAS, "drum_kit.xml.gz"), "rb").read()).decode("utf-8")
    kb_tpl = open(os.path.join(PLANTILLAS, "keybank.xml"), encoding="utf-8").read()
    nombre = re.sub(r"[^\w \-\.&']", "", op.nombre).strip()[:20] or "Mi Kit"
    xml = xml.replace("{NAME}", nombre)
    ondas: dict[str, tuple] = {}
    por_clave: dict = {}

    def add(n, x):
        w = _onda(n, x)
        fbin = w.to_fbin()
        uid = hashlib.sha1(fbin).hexdigest()
        ondas.setdefault(uid, (w, fbin))
        return uid

    activas = [p for p in plan.piezas if p.usar and p.nota in plan.capas]
    for p in activas:
        capas = plan.capas[p.nota]
        lay = []
        for k, (lo, hi, clave) in enumerate(capas):
            if clave not in por_clave:
                y = plan.audio[clave]
                tag = f"{p.nombre[:22]} v{k + 1}" if len(capas) > 1 else p.nombre[:26]
                if y.shape[1] == 2:
                    por_clave[clave] = (add(tag + " L", y[:, :1]), add(tag + " R", y[:, 1:]), y.shape[0])
                else:
                    u = add(tag, y)
                    por_clave[clave] = (u, u, y.shape[0])
            l_uid, r_uid, fr = por_clave[clave]
            lay.append((lo, hi, l_uid, r_uid, fr))
        kbs = []
        for k, (lo, hi, l_uid, r_uid, fr) in enumerate(lay):
            b = kb_tpl.replace('<keybank number="0">', f'<keybank number="{k}">', 1)
            b = re.sub(r"<velocityLimitHi>\d+</velocityLimitHi>", f"<velocityLimitHi>{hi}</velocityLimitHi>", b, count=1)
            b = re.sub(r"<velocityLimitLo>\d+</velocityLimitLo>", f"<velocityLimitLo>{lo}</velocityLimitLo>", b, count=1)
            b = b.replace("{WAVE}", l_uid, 1).replace("{WAVE}", r_uid, 1)
            b = re.sub(r"<sampleSize>\d+</sampleSize>", f"<sampleSize>{fr + 4}</sampleSize>", b)
            b = re.sub(r"<loopEndPoint>\d+</loopEndPoint>", f"<loopEndPoint>{fr}</loopEndPoint>", b)
            kbs.append(b)
        m = re.search(rf'<waveform number="{p.nota}">.*?</waveform>', xml, re.S)
        wf = m.group(0)
        wf = re.sub(r"<maxSampleCount>\d+</maxSampleCount>", f"<maxSampleCount>{2 * len(lay)}</maxSampleCount>", wf, count=1)
        wf = re.sub(r"<useStereoCh>\w+</useStereoCh>", "<useStereoCh>ON</useStereoCh>", wf, count=1)
        wf = wf.replace("</waveform>", "".join(kbs) + " </waveform>")
        xml = xml[:m.start()] + wf + xml[m.end():]
        if p.afinacion:
            xml = _sub_elemento(xml, p.nota, "pitchBlock", "tuneCoarse", str(int(p.afinacion)))
    if op.hihat_grupo:
        hh = [p.nota for p in activas if p.tipo.startswith("hh_")]
        if len(hh) > 1:
            for n in hh:
                xml = _sub_elemento(xml, n, "drumSetup", "alternateGroup", "1")

    vuid = "{" + str(uuid.uuid4()) + "}"
    res = [Resource(vuid, nombre, "uvf", [(b"EUID", vuid.encode()), (b"ETIT", nombre.encode("utf-8")), (b"EEXT", b"uvf"),
                                          (b"EICO", b"T009"), (b"FBIN", xml.encode("utf-8"))])]
    for uid in sorted(ondas):
        w, fbin = ondas[uid]
        res.append(Resource(uid, w.name, "APCp", [(b"EUID", uid.encode()), (b"ETIT", w.name.encode("utf-8")),
                                                  (b"EEXT", b"APCp"), (b"FBIN", fbin)]))
    puid = "{" + str(uuid.uuid4()) + "}"
    pack = Pack(salida, b"\0\0\0\0", [(b"EUID", puid.encode()), (b"ETIT", nombre.encode("utf-8"))], res, [], {}, [])
    pack.save(salida)
    return load_pack(salida)


def crear_kit(entrada, salida: str, op: OpcionesImport, log=print):
    """Todo en uno (línea de comandos)."""
    archivos = escanear(entrada, log)
    grupos = agrupar(archivos)
    if not grupos:
        raise RuntimeError("No encontré golpes WAV válidos en esa carpeta.")
    piezas = auto_kit(grupos)
    plan = planificar(piezas, op, log)
    pack = construir(plan, op, salida)
    return archivos, grupos, plan, pack
