"""Lectura y escritura de archivos .ppf de Yamaha Expansion Manager.

Estructura (descifrada a partir de archivos reales):

    "XPFH" + 4 bytes (flags)
    bloques: TAG(4) + LONGITUD(4, big-endian) + DATOS + relleno hasta multiplo de 4
        EUID  id del pack (GUID)
        ETIT  titulo del pack
        BLOB  contenedor de un recurso:
            EUID  id (GUID para voces, SHA-1 del FBIN para ondas)
            ETIT  nombre
            EEXT  tipo: "uvf" = voz (XML), "APCp" = onda
            EICO  icono (solo voces)
            FBIN  contenido

Las ondas son AIFF con tipo de FORM "YTWV" (COMM, MARK, INST, SSND, PCM 16 bit BE).
"""
from __future__ import annotations

import hashlib
import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import numpy as np

MAGIC = b"XPFH"


# ----------------------------------------------------------------- utilidades
def _pad4(n: int) -> int:
    return (-n) % 4


def read_chunks(data: bytes, start: int, end: int) -> list[tuple[bytes, bytes]]:
    out = []
    o = start
    while o + 8 <= end:
        tag = data[o:o + 4]
        n = struct.unpack(">I", data[o + 4:o + 8])[0]
        if o + 8 + n > end:
            raise ValueError(f"Bloque {tag!r} truncado en offset {o}")
        out.append((tag, data[o + 8:o + 8 + n]))
        o += 8 + n + _pad4(n)
    return out


def write_chunks(chunks: list[tuple[bytes, bytes]]) -> bytes:
    parts = []
    for tag, body in chunks:
        parts.append(tag + struct.pack(">I", len(body)) + body + b"\0" * _pad4(len(body)))
    return b"".join(parts)


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(midi: int) -> str:
    """Nombre de nota al estilo Yamaha (C3 = 60, C-2 = 0)."""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 2}"


def parse_note(name: str) -> int:
    m = re.fullmatch(r"([A-G]#?)(-?\d+)", name.strip())
    if not m:
        raise ValueError(f"Nota invalida: {name}")
    return NOTE_NAMES.index(m.group(1)) + (int(m.group(2)) + 2) * 12


# 80-bit IEEE extended (frecuencia de muestreo en COMM)
def ext80_to_float(b: bytes) -> float:
    exp = ((b[0] & 0x7F) << 8) | b[1]
    mant = int.from_bytes(b[2:10], "big")
    if exp == 0 and mant == 0:
        return 0.0
    v = mant * 2.0 ** (exp - 16383 - 63)
    return -v if b[0] & 0x80 else v


# ---------------------------------------------------------------------- ondas
@dataclass
class Wave:
    uid: str                  # SHA-1 del FBIN
    name: str
    channels: int
    bits: int
    rate: float
    frames: int
    samples: np.ndarray       # float64 en [-1, 1), forma (frames, canales)
    markers: dict[int, tuple[int, str]]   # id -> (posicion, nombre)
    inst: bytes | None        # bloque INST crudo
    other_chunks: list[tuple[bytes, bytes]] = field(default_factory=list)
    order: list[bytes] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.frames / self.rate if self.rate else 0.0

    @property
    def loop_mode(self) -> int:
        """playMode del sustain loop del INST (0 = sin loop)."""
        if not self.inst or len(self.inst) < 10:
            return 0
        return struct.unpack(">h", self.inst[8:10])[0]

    @property
    def loop_points(self) -> tuple[int, int] | None:
        if not self.inst or self.loop_mode == 0:
            return None
        beg_id, end_id = struct.unpack(">hh", self.inst[10:14])
        if beg_id in self.markers and end_id in self.markers:
            return self.markers[beg_id][0], self.markers[end_id][0]
        return None

    # -- (de)serializacion
    @classmethod
    def from_fbin(cls, uid: str, name: str, fbin: bytes) -> "Wave":
        if fbin[:4] != b"FORM":
            raise ValueError(f"Onda {name}: no es FORM")
        form_type = fbin[8:12]
        if form_type not in (b"YTWV", b"AIFF"):
            raise ValueError(f"Onda {name}: tipo {form_type!r} no soportado")
        chunks = []
        p = 12
        while p + 8 <= len(fbin):
            t = fbin[p:p + 4]
            n = struct.unpack(">I", fbin[p + 4:p + 8])[0]
            chunks.append((t, fbin[p + 8:p + 8 + n]))
            p += 8 + n + (n & 1)
        d = dict(chunks)
        comm = d[b"COMM"]
        ch, frames, bits = struct.unpack(">hIh", comm[:8])
        rate = ext80_to_float(comm[8:18])
        if bits != 16:
            raise ValueError(f"Onda {name}: {bits} bits no soportado")
        ssnd = d[b"SSND"]
        off = struct.unpack(">I", ssnd[:4])[0]
        raw = np.frombuffer(ssnd[8 + off:8 + off + frames * ch * 2], dtype=">i2")
        samples = raw.astype(np.float64).reshape(-1, ch) / 32768.0
        markers = {}
        if b"MARK" in d:
            m = d[b"MARK"]
            count = struct.unpack(">H", m[:2])[0]
            q = 2
            for _ in range(count):
                mid, pos = struct.unpack(">hI", m[q:q + 6])
                ln = m[q + 6]
                nm = m[q + 7:q + 7 + ln].decode("latin-1")
                q += 7 + ln
                if (ln + 1) % 2:
                    q += 1
                markers[mid] = (pos, nm)
        w = cls(uid, name, ch, bits, rate, frames, samples, markers, d.get(b"INST"))
        w.order = [t for t, _ in chunks]
        w.other_chunks = [(t, b) for t, b in chunks if t not in (b"COMM", b"MARK", b"INST", b"SSND")]
        w._comm_tail = comm[18:]
        w._form_type = form_type
        return w

    def to_fbin(self) -> bytes:
        pcm = np.clip(np.round(self.samples * 32768.0), -32768, 32767).astype(">i2").tobytes()
        frames = self.samples.shape[0]
        # COMM: conservar bytes de frecuencia originales
        comm = struct.pack(">hIh", self.channels, frames, self.bits) + self._rate_bytes() + getattr(self, "_comm_tail", b"")
        mark = struct.pack(">H", len(self.markers))
        for mid, (pos, nm) in sorted(self.markers.items()):
            nb = nm.encode("latin-1")
            mark += struct.pack(">hI", mid, min(pos, frames)) + bytes([len(nb)]) + nb
            if (len(nb) + 1) % 2:
                mark += b"\0"
        built = {b"COMM": comm, b"MARK": mark, b"SSND": b"\0" * 8 + pcm}
        if self.inst is not None:
            built[b"INST"] = self.inst
        other = dict(self.other_chunks)
        body = b""
        for t in self.order:
            b = built.get(t, other.get(t))
            if b is None:
                continue
            body += t + struct.pack(">I", len(b)) + b + (b"\0" if len(b) & 1 else b"")
        form = getattr(self, "_form_type", b"YTWV") + body
        return b"FORM" + struct.pack(">I", len(form)) + form

    def _rate_bytes(self) -> bytes:
        raw = getattr(self, "_rate_raw", None)
        if raw:
            return raw
        # convertir float -> 80-bit
        r = self.rate
        exp = int(np.floor(np.log2(r)))
        mant = int(r / 2.0 ** (exp - 63))
        return struct.pack(">H", exp + 16383) + mant.to_bytes(8, "big")


# ---------------------------------------------------------------------- voces
@dataclass
class SampleRef:
    position: str        # LEFT / RIGHT / MONO
    wave_uid: str
    sample_size: int
    loop_start: int
    loop_end: int


@dataclass
class KeyBank:
    waveform: int
    note_lo: int
    note_hi: int
    vel_lo: int
    vel_hi: int
    one_shot: bool
    fixed_pitch: bool
    center_note: int
    samples: list[SampleRef]


@dataclass
class Element:
    number: int
    note_lo: int
    note_hi: int
    vel_lo: int
    vel_hi: int
    waveform: int
    volume: float
    pan: float
    tune_coarse: int = 0
    tune_fine: float = 0.0
    pitch_coarse: int = 64
    alternate_group: int = 0


@dataclass
class Voice:
    uid: str
    name: str
    icon: str
    xml_bytes: bytes
    voice_type: str
    elements: list[Element]
    keybanks: dict[int, list[KeyBank]]   # waveform -> keybanks

    def zones(self):
        """Zonas sonoras: (nota, rango vel, keybank, elemento)."""
        for el in self.elements:
            for kb in self.keybanks.get(el.waveform, []):
                lo = max(el.note_lo, kb.note_lo)
                hi = min(el.note_hi, kb.note_hi)
                vlo = max(el.vel_lo, kb.vel_lo)
                vhi = min(el.vel_hi, kb.vel_hi)
                if lo <= hi and vlo <= vhi:
                    yield el, kb, lo, hi, vlo, vhi


def _txt(node, tag, default=""):
    x = node.find(tag)
    return x.text.strip() if x is not None and x.text else default


def parse_voice(uid: str, name: str, icon: str, xml_bytes: bytes) -> Voice:
    root = ET.fromstring(xml_bytes.rstrip(b"\0"))
    vtype = _txt(root, "voiceType")
    elements = []
    common = root.find("voiceCommon")
    for el in (common.findall("voiceElement") if common is not None else []):
        osc = el.find("blockComposition/oscillatorBlock")
        elements.append(Element(
            number=int(el.get("number")),
            note_lo=parse_note(_txt(el, "noteLimitLo", "C-2")),
            note_hi=parse_note(_txt(el, "noteLimitHi", "G8")),
            vel_lo=int(_txt(el, "velocityLimitLo", "1")),
            vel_hi=int(_txt(el, "velocityLimitHi", "127")),
            waveform=int(_txt(osc, "waveformNum", "-1")) if osc is not None else -1,
            volume=float(_txt(el, "volume", "0")),
            pan=float(_txt(el, "pan", "0")),
            tune_coarse=int(float(_txt(el, ".//pitchBlock/tuneCoarse", _txt(el, "tuneCoarse", "0")))),
            tune_fine=float(_txt(el, ".//pitchBlock/tuneFine", _txt(el, "tuneFine", "0"))),
            pitch_coarse=int(_txt(el, ".//pitchCoarse", "64")),
            alternate_group=int(_txt(el, ".//alternateGroup", "0")),
        ))
    keybanks: dict[int, list[KeyBank]] = {}
    for wf in root.findall("waveform"):
        num = int(wf.get("number"))
        for kb in wf.findall("keybank"):
            refs = []
            for s in kb.findall("sample"):
                path = _txt(s, "waveFilePath")
                if not path:
                    continue
                refs.append(SampleRef(
                    position=s.get("position", "MONO"),
                    wave_uid=path,
                    sample_size=int(_txt(s, "sampleSize", "0")),
                    loop_start=int(_txt(s, "loopStartPoint", "0")),
                    loop_end=int(_txt(s, "loopEndPoint", "0")),
                ))
            if not refs:
                continue
            keybanks.setdefault(num, []).append(KeyBank(
                waveform=num,
                note_lo=parse_note(_txt(kb, "noteLimitLo", "C-2")),
                note_hi=parse_note(_txt(kb, "noteLimitHi", "G8")),
                vel_lo=int(_txt(kb, "velocityLimitLo", "1")),
                vel_hi=int(_txt(kb, "velocityLimitHi", "127")),
                one_shot=_txt(kb, "oneShot", "OFF") == "ON",
                fixed_pitch=_txt(kb, "fixedPitch", "OFF") == "ON",
                center_note=parse_note(_txt(kb, "centerNote", "C3")),
                samples=refs,
            ))
    return Voice(uid, name, icon, xml_bytes, vtype, elements, keybanks)


# ----------------------------------------------------------------------- pack
@dataclass
class Resource:
    uid: str
    name: str
    ext: str
    chunks: list[tuple[bytes, bytes]]   # bloques internos del BLOB, en orden

    def get(self, tag: bytes) -> bytes | None:
        for t, b in self.chunks:
            if t == tag:
                return b
        return None

    def set(self, tag: bytes, value: bytes):
        for i, (t, _) in enumerate(self.chunks):
            if t == tag:
                self.chunks[i] = (t, value)
                return
        self.chunks.append((tag, value))


@dataclass
class Pack:
    path: str
    header_flags: bytes
    top: list[tuple[bytes, bytes]]          # bloques de nivel superior (no BLOB)
    resources: list[Resource]
    voices: list[Voice]
    waves: dict[str, Wave]
    errors: list[str]

    @property
    def title(self) -> str:
        for t, b in self.top:
            if t == b"ETIT":
                return b.decode("utf-8", "replace")
        return "?"

    def save(self, path: str):
        with open(path, "wb") as f:
            f.write(self.to_bytes())

    def to_bytes(self) -> bytes:
        out = MAGIC + self.header_flags
        chunks = list(self.top)
        for r in self.resources:
            body = write_chunks(r.chunks)
            # Yamaha no cuenta el relleno del ultimo bloque interno en la longitud del BLOB
            last = len(r.chunks[-1][1]) if r.chunks else 0
            body = body[:len(body) - _pad4(last)]
            chunks.append((b"BLOB", body))
        out += write_chunks(chunks)
        return out


def load_pack(path: str) -> Pack:
    with open(path, "rb") as f:
        data = f.read()
    return load_pack_bytes(data, path)


def load_pack_bytes(data: bytes, path: str = "") -> Pack:
    if data[:4] != MAGIC:
        raise ValueError("No es un archivo .ppf de Yamaha Expansion Manager (falta 'XPFH').")
    flags = data[4:8]
    top, resources, voices, waves, errors = [], [], [], {}, []
    for tag, body in read_chunks(data, 8, len(data)):
        if tag != b"BLOB":
            top.append((tag, body))
            continue
        inner = read_chunks(body, 0, len(body))
        d = dict(inner)
        uid = d.get(b"EUID", b"").decode("ascii", "replace")
        name = d.get(b"ETIT", b"").decode("utf-8", "replace")
        ext = d.get(b"EEXT", b"").decode("ascii", "replace")
        res = Resource(uid, name, ext, inner)
        resources.append(res)
        fbin = d.get(b"FBIN", b"")
        try:
            if ext == "uvf":
                voices.append(parse_voice(uid, name, d.get(b"EICO", b"").decode("ascii", "replace"), fbin))
            elif ext == "APCp":
                if hashlib.sha1(fbin).hexdigest() != uid:
                    errors.append(f"Onda '{name}': el ID no coincide con su contenido (archivo posiblemente dañado).")
                w = Wave.from_fbin(uid, name, fbin)
                comm = fbin[fbin.find(b"COMM") + 8:]
                w._rate_raw = comm[8:18]
                waves[uid] = w
        except Exception as e:  # noqa: BLE001
            errors.append(f"Recurso '{name}' ({ext}): no se pudo leer: {e}")
    return Pack(path, flags, top, resources, voices, waves, errors)


# --------------------------------------------------- reemplazo de una onda
def replace_wave(pack: Pack, old_uid: str, new_wave: Wave):
    """Sustituye una onda en el pack: recalcula el SHA-1 y actualiza el XML."""
    fbin = new_wave.to_fbin()
    new_uid = hashlib.sha1(fbin).hexdigest()
    old = pack.waves[old_uid]
    delta = new_wave.samples.shape[0] - old.frames
    new_frames = new_wave.samples.shape[0]
    for r in pack.resources:
        if r.ext == "APCp" and r.uid == old_uid:
            r.uid = new_uid
            r.set(b"EUID", new_uid.encode("ascii"))
            r.set(b"FBIN", fbin)
    for r in pack.resources:
        if r.ext != "uvf":
            continue
        xml = r.get(b"FBIN").decode("utf-8")

        def fix_sample(m: re.Match) -> str:
            block = m.group(0)
            if f"<waveFilePath>{old_uid}</waveFilePath>" not in block:
                return block
            block = block.replace(old_uid, new_uid)

            def adj(tag, fn):
                nonlocal block
                block = re.sub(rf"<{tag}>(\d+)</{tag}>", lambda mm: f"<{tag}>{fn(int(mm.group(1)))}</{tag}>", block, count=1)

            adj("sampleSize", lambda v: max(1, v + delta))
            adj("loopEndPoint", lambda v: min(v, new_frames) if delta < 0 else (new_frames if v == old.frames else v))
            adj("loopStartPoint", lambda v: min(v, max(0, new_frames - 1)))
            return block

        xml = re.sub(r"<sample position=\"[A-Z]+\">.*?</sample>", fix_sample, xml, flags=re.S)
        r.set(b"FBIN", xml.encode("utf-8"))
    new_wave.uid = new_uid
    new_wave.frames = new_frames
    del pack.waves[old_uid]
    pack.waves[new_uid] = new_wave
    return new_uid


# ------------------------------------------------------- edición del XML
def voice_resource(pack: Pack, voice: Voice) -> Resource:
    for r in pack.resources:
        if r.ext == "uvf" and r.uid == voice.uid:
            return r
    raise KeyError(voice.name)


def reparse_voices(pack: Pack):
    vs = []
    for r in pack.resources:
        if r.ext == "uvf":
            vs.append(parse_voice(r.uid, r.name, (r.get(b"EICO") or b"").decode("ascii", "replace"), r.get(b"FBIN")))
    pack.voices = vs


def _sub_first(text: str, tag: str, value: str) -> tuple[str, bool]:
    new, n = re.subn(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{value}</{tag}>", text, count=1)
    return new, n > 0


def edit_element(pack: Pack, voice: Voice, number: int, block: str | None, tag: str, value) -> bool:
    """Cambia un parámetro de un elemento (tecla) de la voz.

    block=None  -> parámetro directo del elemento (antes de <blockComposition>)
    block='pitchBlock' / 'filterBlock' / 'amplitudeBlock' / 'panBlock' / 'drumSetup'
    """
    r = voice_resource(pack, voice)
    xml = r.get(b"FBIN").decode("utf-8")
    m = re.search(rf'<voiceElement number="{number}"[^>]*>.*?</voiceElement>', xml, re.S)
    if not m:
        return False
    el = m.group(0)
    val = f"{value:.6f}" if isinstance(value, float) else str(value)
    if block is None:
        cut = el.find("<blockComposition>")
        head, tail = (el[:cut], el[cut:]) if cut >= 0 else (el, "")
        head, ok = _sub_first(head, tag, val)
        new_el = head + tail
    else:
        bm = re.search(rf"<{block}\b[^>]*>.*?</{block}>", el, re.S)
        if not bm:
            return False
        nb, ok = _sub_first(bm.group(0), tag, val)
        new_el = el[:bm.start()] + nb + el[bm.end():]
    if not ok:
        return False
    xml = xml[:m.start()] + new_el + xml[m.end():]
    r.set(b"FBIN", xml.encode("utf-8"))
    return True


def add_wave(pack: Pack, template: Wave, samples: np.ndarray, name: str) -> str:
    """Añade una onda nueva al pack (mismo formato que 'template')."""
    import copy
    w = copy.copy(template)
    w.samples = samples
    w.frames = samples.shape[0]
    w.channels = samples.shape[1]
    w.name = name[:31]
    w.markers = {k: (0 if pos == 0 else samples.shape[0], nm) for k, (pos, nm) in template.markers.items()}
    fbin = w.to_fbin()
    uid = hashlib.sha1(fbin).hexdigest()
    w.uid = uid
    if uid not in pack.waves:
        pack.resources.append(Resource(uid, w.name, "APCp", [
            (b"EUID", uid.encode("ascii")), (b"ETIT", w.name.encode("utf-8")),
            (b"EEXT", b"APCp"), (b"FBIN", fbin)]))
        pack.waves[uid] = w
    return uid


def remove_unused_waves(pack: Pack) -> int:
    used = set()
    for r in pack.resources:
        if r.ext == "uvf":
            used |= set(re.findall(r"<waveFilePath>([0-9a-f]{40})</waveFilePath>", r.get(b"FBIN").decode("utf-8")))
    before = len(pack.resources)
    pack.resources = [r for r in pack.resources if r.ext != "APCp" or r.uid in used]
    for uid in list(pack.waves):
        if uid not in used:
            del pack.waves[uid]
    return before - len(pack.resources)


def set_velocity_layers(pack: Pack, voice: Voice, waveform: int, layers: list[tuple[int, int, str]]) -> bool:
    """Sustituye los keybanks de una forma de onda por capas de velocidad.
    layers: [(vel_lo, vel_hi, uid_onda), ...]  (la plantilla es el primer keybank actual)."""
    r = voice_resource(pack, voice)
    xml = r.get(b"FBIN").decode("utf-8")
    m = re.search(rf'<waveform number="{waveform}">.*?</waveform>', xml, re.S)
    if not m:
        return False
    wf = m.group(0)
    kbs = list(re.finditer(r'[ \t]*<keybank number="\d+">.*?</keybank>\n?', wf, re.S))
    if not kbs:
        return False
    tmpl = kbs[0].group(0)
    tm_uid = re.search(r"<waveFilePath>([0-9a-f]{40})</waveFilePath>", tmpl).group(1)
    tm_wave = pack.waves[tm_uid]
    tm_size = int(re.search(r"<sampleSize>(\d+)</sampleSize>", tmpl).group(1))
    pad = tm_size - tm_wave.frames
    new_kbs = []
    nsamples = 0
    for i, (vlo, vhi, uid) in enumerate(layers):
        w = pack.waves[uid]
        k = re.sub(r'<keybank number="\d+">', f'<keybank number="{i}">', tmpl, count=1)
        k, _ = _sub_first(k, "velocityLimitHi", str(vhi))
        k, _ = _sub_first(k, "velocityLimitLo", str(vlo))
        k = k.replace(tm_uid, uid)
        k = re.sub(r"<sampleSize>\d+</sampleSize>", f"<sampleSize>{w.frames + pad}</sampleSize>", k)
        k = re.sub(r"<loopEndPoint>\d+</loopEndPoint>", f"<loopEndPoint>{w.frames}</loopEndPoint>", k)
        k = re.sub(r"<loopStartPoint>\d+</loopStartPoint>", "<loopStartPoint>0</loopStartPoint>", k)
        nsamples += k.count("<sample ")
        new_kbs.append(k)
    new_wf = wf[:kbs[0].start()] + "".join(new_kbs) + wf[kbs[-1].end():]
    new_wf = re.sub(r"<maxSampleCount>\d+</maxSampleCount>", f"<maxSampleCount>{nsamples}</maxSampleCount>", new_wf, count=1)
    xml = xml[:m.start()] + new_wf + xml[m.end():]
    r.set(b"FBIN", xml.encode("utf-8"))
    return True



# ------------------------------------------------- mapeo: mover teclas y capas
def _bloque(xml: str, tag: str, number: int):
    m = re.search(rf'<{tag} number="{number}"[^>]*>.*?</{tag}>', xml, re.S)
    return m


def mover_tecla(pack: Pack, voice: Voice, src: int, dst: int) -> bool:
    """Intercambia todo lo que suena en la tecla src con la tecla dst (drum kits)."""
    if src == dst:
        return False
    r = voice_resource(pack, voice)
    xml = r.get(b"FBIN").decode("utf-8")
    for tag in ("voiceElement", "waveform"):
        a, b = _bloque(xml, tag, src), _bloque(xml, tag, dst)
        if not a or not b:
            return False
        ta, tb = a.group(0), b.group(0)

        def renum(block, old, new):
            block = re.sub(rf'<{tag} number="{old}"', f'<{tag} number="{new}"', block, count=1)
            if tag == "voiceElement":
                nn = note_name(new)
                block = re.sub(r"<noteLimitHi>[^<]*</noteLimitHi>", f"<noteLimitHi>{nn}</noteLimitHi>", block, count=1)
                block = re.sub(r"<noteLimitLo>[^<]*</noteLimitLo>", f"<noteLimitLo>{nn}</noteLimitLo>", block, count=1)
                block = re.sub(r"<waveformNum>\d+</waveformNum>", f"<waveformNum>{new}</waveformNum>", block, count=1)
            return block

        na, nb = renum(tb, dst, src), renum(ta, src, dst)
        if a.start() < b.start():
            xml = xml[:a.start()] + na + xml[a.end():b.start()] + nb + xml[b.end():]
        else:
            xml = xml[:b.start()] + nb + xml[b.end():a.start()] + na + xml[a.end():]
    r.set(b"FBIN", xml.encode("utf-8"))
    return True


def capas_de(voice: Voice, waveform: int) -> list[tuple[int, int, str]]:
    return [(kb.vel_lo, kb.vel_hi, kb.samples[0].wave_uid) for kb in voice.keybanks.get(waveform, [])]


def fijar_rangos(pack: Pack, voice: Voice, waveform: int, rangos: list[tuple[int, int]]) -> bool:
    """Cambia los rangos de velocidad de las capas (keybanks) de una tecla."""
    r = voice_resource(pack, voice)
    xml = r.get(b"FBIN").decode("utf-8")
    m = _bloque(xml, "waveform", waveform)
    if not m:
        return False
    wf = m.group(0)
    kbs = list(re.finditer(r'<keybank number="\d+">.*?</keybank>', wf, re.S))
    if len(kbs) != len(rangos):
        return False
    out, last = [], 0
    for k, (lo, hi) in zip(kbs, rangos):
        b = k.group(0)
        b = re.sub(r"<velocityLimitHi>\d+</velocityLimitHi>", f"<velocityLimitHi>{int(hi)}</velocityLimitHi>", b, count=1)
        b = re.sub(r"<velocityLimitLo>\d+</velocityLimitLo>", f"<velocityLimitLo>{int(lo)}</velocityLimitLo>", b, count=1)
        out.append(wf[last:k.start()] + b)
        last = k.end()
    wf = "".join(out) + wf[last:]
    xml = xml[:m.start()] + wf + xml[m.end():]
    r.set(b"FBIN", xml.encode("utf-8"))
    return True
