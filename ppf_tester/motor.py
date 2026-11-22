"""Motor de sonido: reproduce una voz del pack aplicando los parámetros que usa
el teclado (curva de velocidad, volumen, paneo, afinación, filtro, sends) y un
mezclador polifónico en tiempo real.

Es una APROXIMACIÓN del motor AWM del teclado. Lo único 100 % exacto es grabar
el propio teclado (ver Teclado real / A-B en la app).
"""
from __future__ import annotations

import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import numpy as np

from sig import fftconvolve, lfilter

from ppf_format import Pack, Voice

SR = 44100


# ------------------------------------------------------------------ parametros
@dataclass
class ElementSound:
    number: int
    vol_db: float = 0.0
    pan: float = 0.0               # -1 .. 1
    tune: float = 0.0              # semitonos
    touch_db: np.ndarray | None = None
    touch_sens: float = 1.0
    lpf_hz: float | None = None
    lpf_q: float = 0.707
    hpf_hz: float | None = None
    level: int = 127               # drum setup
    rev_send: int = 0
    cho_send: int = 0
    alt_group: int = 0
    aeg_flat: bool = True
    notes: list[str] = field(default_factory=list)


def _f(node, path, default=0.0):
    x = node.find(path) if node is not None else None
    try:
        return float(x.text) if x is not None and x.text else default
    except ValueError:
        return default


def _s(node, path, default=""):
    x = node.find(path) if node is not None else None
    return x.text.strip() if x is not None and x.text else default


def parse_sound(voice: Voice) -> tuple[dict[int, ElementSound], dict]:
    root = ET.fromstring(voice.xml_bytes.rstrip(b"\0"))
    common = root.find("voiceCommon")
    out = {}
    for el in (common.findall("voiceElement") if common is not None else []):
        n = int(el.get("number"))
        bc = el.find("blockComposition")
        amp = bc.find("amplitudeBlock") if bc is not None else None
        flt = bc.find("filterBlock") if bc is not None else None
        pit = bc.find("pitchBlock") if bc is not None else None
        pan = bc.find("panBlock") if bc is not None else None
        ds = el.find("drumSetup")
        es = ElementSound(n)
        es.vol_db = _f(el, "volume") + _f(amp, "volume")
        p = _f(pan, "pan") + _f(el, "pan")
        p = p / 64.0 if abs(p) > 1 else p
        if ds is not None:
            dp = int(_f(ds, "pan", 64))
            if dp > 0:
                p += (dp - 64) / 63.0
        es.pan = float(np.clip(p, -1, 1))
        es.tune = _f(pit, "tuneCoarse") + _f(pit, "tuneFine") / 100.0
        if ds is not None:
            es.tune += (_f(ds, "pitchCoarse", 64) - 64) + (_f(ds, "pitchFine", 64) - 64) / 100.0
            es.level = int(_f(ds, "level", 127))
            es.rev_send = int(_f(ds, "reverbSend", 0))
            es.cho_send = int(_f(ds, "chorusSend", 0))
            es.alt_group = int(_f(ds, "alternateGroup", 0))
        tct = amp.find("touchCurveTable") if amp is not None else None
        if tct is not None and _s(tct, "table"):
            vals = np.array([float(v) for v in _s(tct, "table").split()])
            if len(vals) == 128:
                es.touch_db = vals
            es.touch_sens = _f(tct, "sens", 100) / 100.0
        if flt is not None:
            ft = _s(flt, "dcfFilterType", "THRU").upper()
            fc = _f(flt, "dcfCutoff", 0)
            if ft.startswith("LPF") and 20 < fc < 20000:
                es.lpf_hz = fc
                res = _f(flt, "dcfResonance", 0)
                es.lpf_q = 0.707 + max(0.0, res) / 6.0   # aprox.
            ft2 = _s(flt, "dcf2FilterType", "THRU").upper()
            fc2 = _f(flt, "dcf2Cutoff", 0)
            if ft2.startswith("HPF") and 10 < fc2 < 2000:
                es.hpf_hz = fc2
        # envolvente: solo detectamos si modifica la muestra
        if amp is not None:
            lv = [_f(amp, t) for t in ("decay1Level", "decay2Level")]
            rates = [_f(amp, t) for t in ("decay1Rate", "decay2Rate", "decay3Rate")]
            es.aeg_flat = all(abs(v) < 0.01 for v in lv) or all(r == 0 for r in rates)
        out[n] = es
    vs = root.find("voiceSet")
    fx = root.find("effectSet")
    common_p = dict(
        part_volume=int(_f(vs, "volume", 100)),
        reverb=int(_f(fx, "reverbSend", 0)),
        chorus=int(_f(fx, "chorusSend", 0)),
        touch_depth=int(_f(vs, "touchSensDepth", 64)),
        touch_offset=int(_f(vs, "touchSensOffset", 64)),
    )
    return out, common_p


# ------------------------------------------------------------------ DSP
def _biquad(kind: str, fc: float, q: float, sr: float):
    w = 2 * np.pi * min(fc, sr * 0.45) / sr
    alpha = np.sin(w) / (2 * q)
    cw = np.cos(w)
    if kind == "lp":
        b = np.array([(1 - cw) / 2, 1 - cw, (1 - cw) / 2])
    else:
        b = np.array([(1 + cw) / 2, -(1 + cw), (1 + cw) / 2])
    a = np.array([1 + alpha, -2 * cw, 1 - alpha])
    return b / a[0], a / a[0]


def _filt(b, a, x):
    if lfilter is not None:
        return lfilter(b, a, x, axis=0)
    y = np.zeros_like(x)
    for i in range(len(x)):
        y[i] = b[0] * x[i] + (b[1] * x[i - 1] if i > 0 else 0) + (b[2] * x[i - 2] if i > 1 else 0) \
               - (a[1] * y[i - 1] if i > 0 else 0) - (a[2] * y[i - 2] if i > 1 else 0)
    return y


def _resample(x: np.ndarray, ratio: float) -> np.ndarray:
    if abs(ratio - 1) < 1e-6:
        return x
    n = int(len(x) / ratio)
    t = np.arange(n) * ratio
    return np.stack([np.interp(t, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], axis=1)


_IR_CACHE: dict = {}


def _reverb_ir(sr: float, size: float) -> np.ndarray:
    """Respuesta al impulso estéreo de una reverb tipo Hall (Schroeder), calculada una vez."""
    key = (sr, round(size, 2))
    if key in _IR_CACHE:
        return _IR_CACHE[key]
    n = int(sr * 2.2 * size) + 1
    imp = np.zeros(n)
    imp[0] = 1.0
    outs = []
    for combs in ((1116, 1188, 1277, 1356), (1139, 1211, 1300, 1379)):
        acc = np.zeros(n)
        for d in combs:
            d = int(d * sr / 44100 * (0.7 + 0.3 * size))
            g = 0.78 + 0.1 * size
            a = np.zeros(d + 1)
            a[0], a[d] = 1, -g
            acc += lfilter([0.8], [1, -0.2], lfilter(np.r_[np.zeros(d), 1.0], a, imp))
        for d in (556, 441):
            d = int(d * sr / 44100)
            bb = np.zeros(d + 1); bb[0], bb[d] = -0.5, 1
            aa = np.zeros(d + 1); aa[0], aa[d] = 1, -0.5
            acc = lfilter(bb, aa, acc)
        outs.append(acc / 4)
    ir = np.stack(outs, axis=1)
    _IR_CACHE[key] = ir
    return ir


def reverb(x: np.ndarray, sr: float, amount: float, size: float = 0.8) -> np.ndarray:
    """Añade reverb tipo Hall (aproximada; la del PSR depende del tipo elegido en el panel)."""
    if amount <= 0:
        return x
    ir = _reverb_ir(sr, size)
    m = x.mean(axis=1)
    wet = np.stack([fftconvolve(m, ir[:, 0]), fftconvolve(m, ir[:, 1])], axis=1)
    dry = np.pad(x, ((0, len(wet) - len(x)), (0, 0)))
    return dry + wet * amount * 0.35


@dataclass
class Settings:
    use_filter: bool = True
    use_velocity: bool = True
    reverb: float | None = None     # 0..1, None = el de la voz
    master_db: float = 0.0


class Engine:
    """Renderiza notas de una voz como las tocaría el teclado."""

    def __init__(self, pack: Pack, voice: Voice):
        self.pack = pack
        self.voice = voice
        self.sound, self.common = parse_sound(voice)
        self.settings = Settings()
        self._cache: dict = {}

    def invalidate(self):
        self._cache.clear()

    def zones_for(self, note: int, vel: int):
        for el, kb, lo, hi, vlo, vhi in self.voice.zones():
            if lo <= note <= hi and vlo <= vel <= vhi:
                yield el, kb

    def describe(self, note: int) -> list[str]:
        """Parámetros que se aplican a la nota (para mostrarlos al usuario)."""
        lines = []
        for el, kb in self.zones_for(note, 100):
            es = self.sound.get(el.number)
            if es is None:
                continue
            lines.append(f"Elemento {el.number}: volumen {es.vol_db:+.1f} dB · nivel {es.level}/127 · "
                         f"paneo {es.pan:+.2f} · afinación {es.tune:+.2f} st")
            lines.append(f"Filtro: {'paso-bajo ' + format(es.lpf_hz, '.0f') + ' Hz' if es.lpf_hz else 'sin filtro'}"
                         f"{' · paso-alto ' + format(es.hpf_hz, '.0f') + ' Hz' if es.hpf_hz else ''} · "
                         f"reverb send {es.rev_send} · chorus send {es.cho_send} · grupo {es.alt_group or '—'}")
            if not es.aeg_flat:
                lines.append("Esta nota tiene envolvente de volumen (AEG) que la simulación no reproduce.")
        return lines

    def velocity_db(self, es: ElementSound, vel: int) -> float:
        if not self.settings.use_velocity:
            return 0.0
        vel = int(np.clip(vel, 1, 127))
        if es.touch_db is not None:
            db = es.touch_db[vel] * es.touch_sens
        else:
            db = 40 * np.log10(vel / 127)
        depth = self.common.get("touch_depth", 64) / 64.0
        return db * depth

    def render(self, note: int, vel: int) -> tuple[np.ndarray, int]:
        """Devuelve (audio estéreo float32, grupo alterno)."""
        key = (note, vel // 4)
        if key in self._cache:
            return self._cache[key]
        out = None
        group = 0
        for el, kb in self.zones_for(note, vel):
            es = self.sound.get(el.number, ElementSound(el.number))
            group = group or es.alt_group
            chans = []
            for s in kb.samples:
                w = self.pack.waves.get(s.wave_uid)
                if w is None:
                    continue
                chans.append(w.samples[:, 0] if w.channels == 1 else
                             w.samples[:, 0 if s.position != "RIGHT" else 1])
            if not chans:
                continue
            n = min(len(c) for c in chans)
            x = np.stack([chans[0][:n], chans[-1][:n]], axis=1) if len(chans) > 1 else np.stack([chans[0][:n]] * 2, axis=1)
            rate = self.pack.waves[kb.samples[0].wave_uid].rate or SR
            semis = es.tune + (0 if kb.fixed_pitch else note - kb.center_note)
            x = _resample(x, 2 ** (semis / 12) * rate / SR)
            if self.settings.use_filter:
                if es.lpf_hz:
                    b, a = _biquad("lp", es.lpf_hz, es.lpf_q, SR)
                    x = _filt(b, a, x)
                if es.hpf_hz:
                    b, a = _biquad("hp", es.hpf_hz, 0.707, SR)
                    x = _filt(b, a, x)
            g_db = es.vol_db + 40 * np.log10(max(es.level, 1) / 127) + self.velocity_db(es, vel) + self.settings.master_db
            g = 10 ** (g_db / 20)
            th = (es.pan + 1) * np.pi / 4            # paneo de potencia constante
            x = x * g * np.array([np.cos(th), np.sin(th)]) * np.sqrt(2)
            rv = self.settings.reverb if self.settings.reverb is not None else self.common["reverb"] / 127
            x = reverb(x, SR, rv * es.rev_send / 127)
            if out is None:
                out = x
            else:
                m = max(len(out), len(x))
                out = np.pad(out, ((0, m - len(out)), (0, 0))) + np.pad(x, ((0, m - len(x)), (0, 0)))
        if out is None:
            out = np.zeros((1, 2))
        res = (out.astype(np.float32), group)
        if len(self._cache) > 400:
            self._cache.clear()
        self._cache[key] = res
        return res


# ------------------------------------------------------------- mezclador
class Mixer:
    """Salida polifónica en tiempo real (sounddevice)."""

    def __init__(self, device=None, max_voices: int = 24):
        import sounddevice as sd
        self.sd = sd
        self.voices: list[list] = []        # [buffer, pos, group, note]
        self.lock = threading.Lock()
        self.max_voices = max_voices
        self.peak = 0.0
        self.stream = sd.OutputStream(samplerate=SR, channels=2, dtype="float32", device=device,
                                      latency="low", callback=self._cb)
        self.stream.start()

    def _cb(self, out, frames, t, status):
        out.fill(0)
        with self.lock:
            keep = []
            for v in self.voices:
                buf, pos = v[0], v[1]
                n = min(frames, len(buf) - pos)
                if n > 0:
                    out[:n] += buf[pos:pos + n]
                    v[1] += n
                if v[1] < len(buf):
                    keep.append(v)
            self.voices = keep
        pk = float(np.abs(out).max()) if frames else 0.0
        self.peak = max(pk, self.peak * 0.9)
        np.clip(out, -1, 1, out=out)

    def play(self, buf: np.ndarray, group: int = 0, note: int = -1, exclusive_note: bool = True):
        with self.lock:
            if group:
                self.voices = [v for v in self.voices if v[2] != group]   # el hi-hat cerrado corta al abierto
            if len(self.voices) >= self.max_voices:
                self.voices.pop(0)
            self.voices.append([buf, 0, group, note])

    def stop(self):
        with self.lock:
            self.voices = []

    def close(self):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:  # noqa: BLE001
            pass


class LiveInput:
    """Entrada de audio en vivo (el teclado): la graba continuamente en un búfer
    circular y, si se pide, la deja oír por los altavoces del PC (monitor).
    Usa streams separados de entrada y salida, así funciona con cualquier driver."""

    def __init__(self, in_dev, out_dev=None, monitor: bool = False, seconds: float = 12.0):
        import sounddevice as sd
        import time
        self.time = time
        info = sd.query_devices(in_dev, "input")
        self.ch = min(2, int(info["max_input_channels"])) or 1
        rate = SR
        try:
            sd.check_input_settings(device=in_dev, channels=self.ch, samplerate=SR, dtype="float32")
        except Exception:  # noqa: BLE001
            rate = int(info["default_samplerate"])
        self.rate = rate
        self.buf = np.zeros((int(rate * seconds), 2), np.float32)
        self.pos = 0
        self.t_ref = None
        self.monitor = monitor
        self.gain = 1.0
        self.level = 0.0
        self.lock = threading.Lock()
        self.read_pos = None

        def cb_in(indata, frames, t, status):
            x = indata[:, :2] if self.ch >= 2 else np.repeat(indata[:, :1], 2, axis=1)
            with self.lock:
                n = len(self.buf)
                i = self.pos % n
                k = min(frames, n - i)
                self.buf[i:i + k] = x[:k]
                if k < frames:
                    self.buf[:frames - k] = x[k:]
                self.pos += frames
                self.t_ref = (self.time.perf_counter(), self.pos)
            self.level = max(float(np.abs(x).max()) if frames else 0.0, self.level * 0.85)

        def cb_out(outdata, frames, t, status):
            outdata.fill(0)
            if not self.monitor:
                self.read_pos = None
                return
            with self.lock:
                lag = int(self.rate * 0.03)
                if self.read_pos is None or self.pos - self.read_pos > self.rate * 0.2 or self.read_pos > self.pos:
                    self.read_pos = max(0, self.pos - lag)
                avail = min(frames, self.pos - self.read_pos)
                if avail > 0:
                    idx = np.arange(self.read_pos, self.read_pos + avail) % len(self.buf)
                    outdata[:avail] = self.buf[idx] * self.gain
                    self.read_pos += avail

        self.stream_in = sd.InputStream(device=in_dev, channels=self.ch, samplerate=rate, dtype="float32",
                                        latency="low", callback=cb_in)
        self.stream_in.start()
        self.stream_out = sd.OutputStream(device=out_dev, channels=2, samplerate=rate, dtype="float32",
                                          latency="low", callback=cb_out)
        self.stream_out.start()

    def now(self) -> int:
        with self.lock:
            if self.t_ref is None:
                return self.pos
            t, p = self.t_ref
            return p + int((self.time.perf_counter() - t) * self.rate)

    def get(self, start: int, end: int) -> np.ndarray:
        with self.lock:
            n = len(self.buf)
            end = min(end, self.pos)
            start = max(start, self.pos - n + 1, 0)
            if end <= start:
                return np.zeros((0, 2), np.float32)
            x = self.buf[np.arange(start, end) % n].copy()
        if self.rate != SR:   # llevar a 44.1 kHz para comparar
            t = np.arange(int(len(x) * SR / self.rate)) * self.rate / SR
            x = np.stack([np.interp(t, np.arange(len(x)), x[:, c]) for c in range(2)], axis=1).astype(np.float32)
        return x

    def close(self):
        for st in (self.stream_in, self.stream_out):
            try:
                st.stop()
                st.close()
            except Exception:  # noqa: BLE001
                pass


# ------------------------------------------------------------- comparacion
def spectral_centroid(x: np.ndarray, sr: int = SR) -> float:
    m = x.mean(axis=1) if x.ndim > 1 else x
    m = m[: sr * 2]
    if not len(m) or np.abs(m).max() == 0:
        return 0.0
    spec = np.abs(np.fft.rfft(m * np.hanning(len(m))))
    f = np.fft.rfftfreq(len(m), 1 / sr)
    return float((spec * f).sum() / max(spec.sum(), 1e-12))


def align_onset(x: np.ndarray, thr_db: float = -30) -> np.ndarray:
    m = np.abs(x).max(axis=1) if x.ndim > 1 else np.abs(x)
    if not len(m):
        return x
    idx = np.where(m > m.max() * 10 ** (thr_db / 20))[0]
    return x[max(0, idx[0] - 32):] if len(idx) else x


def compare(sim: np.ndarray, rec: np.ndarray, sr: int = SR) -> dict:
    """Compara simulación y grabación real (alineadas por el ataque)."""
    a, b = align_onset(sim), align_onset(rec)
    rms = lambda x: float(np.sqrt(np.mean(x[: int(sr * 0.3)] ** 2))) if len(x) else 0.0
    ca, cb = spectral_centroid(a, sr), spectral_centroid(b, sr)
    m = np.abs(b).max(axis=1) if b.ndim > 1 else np.abs(b)
    above = np.where(m > m.max() * 10 ** (-40 / 20))[0] if len(m) else []
    ma = np.abs(a).max(axis=1)
    above_a = np.where(ma > ma.max() * 10 ** (-40 / 20))[0] if len(ma) else []
    return dict(
        centroid_sim=ca, centroid_rec=cb,
        brillo_pct=(cb / ca - 1) * 100 if ca else 0.0,
        dur_sim=(above_a[-1] / sr) if len(above_a) else 0.0,
        dur_rec=(above[-1] / sr) if len(above) else 0.0,
        rms_sim_db=20 * np.log10(max(rms(a), 1e-9)), rms_rec_db=20 * np.log10(max(rms(b), 1e-9)),
    )
