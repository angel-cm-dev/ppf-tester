"""Prueba en el teclado real: envia notas por USB-MIDI y graba lo que suena.

MIDI: usa la API de Windows (winmm) directamente, sin librerias extra.
Audio: usa 'sounddevice' (pip install sounddevice) para grabar la salida del
teclado a traves de una interfaz de audio o la entrada de linea del PC.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

import numpy as np

import analisis as A
from ppf_format import note_name


# ------------------------------------------------------------ MIDI (winmm)
class MIDIOUTCAPSW(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("vDriverVersion", wintypes.UINT),
                ("szPname", wintypes.WCHAR * 32), ("wTechnology", wintypes.WORD), ("wVoices", wintypes.WORD),
                ("wNotes", wintypes.WORD), ("wChannelMask", wintypes.WORD), ("dwSupport", wintypes.DWORD)]


def _winmm():
    if sys.platform != "win32":
        raise RuntimeError("La prueba MIDI solo está implementada para Windows.")
    return ctypes.windll.winmm


def midi_outputs() -> list[str]:
    mm = _winmm()
    out = []
    for i in range(mm.midiOutGetNumDevs()):
        caps = MIDIOUTCAPSW()
        mm.midiOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
        out.append(caps.szPname)
    return out


def find_keyboard_port() -> int | None:
    for i, n in enumerate(midi_outputs()):
        low = n.lower()
        if any(k in low for k in ("digital keyboard", "yamaha", "psr", "usb-midi", "usb midi")):
            return i
    return None


class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("vDriverVersion", wintypes.UINT),
                ("szPname", wintypes.WCHAR * 32), ("dwSupport", wintypes.DWORD)]


def midi_inputs() -> list[str]:
    mm = _winmm()
    out = []
    for i in range(mm.midiInGetNumDevs()):
        caps = MIDIINCAPSW()
        mm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
        out.append(caps.szPname)
    return out


_MidiInProc = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t)


class MidiIn:
    """Entrada MIDI (teclado controlador o el propio PSR). on_note(nota, velocidad) se llama desde otro hilo."""

    def __init__(self, port: int, on_note):
        self.mm = _winmm()
        self.on_note = on_note
        self.h = wintypes.HANDLE()

        def proc(h, msg, inst, p1, p2):
            if msg == 0x3C3:                      # MIM_DATA
                st, d1, d2 = p1 & 0xFF, (p1 >> 8) & 0x7F, (p1 >> 16) & 0x7F
                if st & 0xF0 == 0x90 and d2 > 0:
                    try:
                        self.on_note(d1, d2)
                    except Exception:  # noqa: BLE001
                        pass

        self._cb = _MidiInProc(proc)              # mantener la referencia viva
        r = self.mm.midiInOpen(ctypes.byref(self.h), port, ctypes.cast(self._cb, ctypes.c_void_p), 0, 0x30000)
        if r != 0:
            raise RuntimeError(f"No se pudo abrir la entrada MIDI {port} (código {r}).")
        self.mm.midiInStart(self.h)

    def close(self):
        try:
            self.mm.midiInStop(self.h)
            self.mm.midiInReset(self.h)
            self.mm.midiInClose(self.h)
        except Exception:  # noqa: BLE001
            pass


class MidiOut:
    def __init__(self, port: int):
        self.mm = _winmm()
        self.h = wintypes.HANDLE()
        r = self.mm.midiOutOpen(ctypes.byref(self.h), port, 0, 0, 0)
        if r != 0:
            raise RuntimeError(f"No se pudo abrir el puerto MIDI {port} (código {r}). ¿Lo está usando otro programa?")

    def send(self, status: int, d1: int = 0, d2: int = 0):
        self.mm.midiOutShortMsg(self.h, status | (d1 << 8) | (d2 << 16))

    def note(self, ch: int, note: int, vel: int):
        self.send(0x90 | (ch - 1), note, vel)

    def off(self, ch: int, note: int):
        self.send(0x80 | (ch - 1), note, 0)

    def all_off(self, ch: int):
        self.send(0xB0 | (ch - 1), 123, 0)

    def close(self):
        self.mm.midiOutReset(self.h)
        self.mm.midiOutClose(self.h)


# -------------------------------------------------------------- grabacion
class Recorder:
    def __init__(self, device: int | None, rate: int = 44100, channels: int = 2):
        import sounddevice as sd
        self.sd = sd
        info = sd.query_devices(device, "input") if device is not None else sd.query_devices(kind="input")
        self.channels = min(channels, int(info["max_input_channels"])) or 1
        self.rate = rate
        self.device = device
        self.buf: list[np.ndarray] = []
        self.lock = threading.Lock()
        self.t0 = None

    def _cb(self, indata, frames, t, status):
        with self.lock:
            if self.t0 is None:
                self.t0 = time.perf_counter()
            self.buf.append(indata.copy())

    def __enter__(self):
        self.stream = self.sd.InputStream(device=self.device, channels=self.channels, samplerate=self.rate,
                                          dtype="float32", callback=self._cb, latency="low")
        self.stream.start()
        while self.t0 is None:
            time.sleep(0.005)
        return self

    def __exit__(self, *a):
        self.stream.stop()
        self.stream.close()

    def data(self) -> np.ndarray:
        with self.lock:
            return np.concatenate(self.buf) if self.buf else np.zeros((0, self.channels), np.float32)


# ------------------------------------------------------------ prueba
@dataclass
class Hit:
    note: int
    vel: int
    name: str
    t_on: float
    dur: float
    peak_db: float = -120.0
    latency_ms: float | None = None
    audio: np.ndarray | None = None


def plan_notes(kit: A.KitReport, waves_by_name: dict, notas: list[int] | None) -> list[tuple[int, str, float]]:
    seen = {}
    for z in kit.zones:
        for n in range(z["note_lo"], z["note_hi"] + 1):
            if notas and n not in notas:
                continue
            nm = " / ".join(sorted(set(z["samples"]))) or "?"
            w = waves_by_name.get(z["samples"][0]) if z["samples"] else None
            dur = min(3.0, (w.duration if w else 1.0) + 0.3)
            seen[n] = (n, nm, dur)
            if z["note_hi"] - z["note_lo"] > 24:   # voces melodicas: no tocar las 128 teclas
                break
    return [seen[k] for k in sorted(seen)]


def run_test(kit: A.KitReport, waves_by_name: dict, port: int, channel: int, velocities: list[int],
             record_device: int | None, record: bool, notas: list[int] | None = None,
             gap: float = 0.25, log=print) -> tuple[list[Hit], np.ndarray | None, int]:
    plan = plan_notes(kit, waves_by_name, notas)
    if not plan:
        raise RuntimeError("No hay notas que tocar.")
    total = sum(d + gap for _, _, d in plan) * len(velocities)
    log(f"Se tocarán {len(plan)} notas × {len(velocities)} velocidades (~{total:.0f} s).")
    out = MidiOut(port)
    hits: list[Hit] = []
    rec = None
    try:
        ctx = Recorder(record_device) if record else None
        if ctx:
            rec = ctx.__enter__()
            time.sleep(0.5)  # medir ruido de fondo
        t_start = rec.t0 if rec else time.perf_counter()
        for vel in velocities:
            for n, nm, dur in plan:
                t_on = time.perf_counter() - t_start
                out.note(channel, n, vel)
                log(f"  {note_name(n):>4} ({n:3})  vel {vel:3}  {nm}")
                time.sleep(dur)
                out.off(channel, n)
                time.sleep(gap)
                hits.append(Hit(n, vel, nm, t_on, dur))
        out.all_off(channel)
        if rec:
            time.sleep(0.5)
            ctx.__exit__(None, None, None)
    finally:
        out.close()

    audio = None
    sr = 44100
    if rec:
        audio = rec.data()
        sr = rec.rate
        mono = np.abs(audio).max(axis=1) if audio.ndim > 1 else np.abs(audio)
        # ruido de fondo medido en el pre-roll, saltando el clic de arranque del stream
        pre = mono[int(sr * 0.05):int(sr * 0.45)]
        noise = float(np.percentile(pre, 95)) if len(pre) else 0.0
        thr = max(noise * 4, 10 ** (-60 / 20))
        for h in hits:
            a = int(h.t_on * sr)
            b = min(len(mono), int((h.t_on + h.dur + gap * 0.9) * sr))
            seg = mono[a:b]
            if not len(seg):
                continue
            h.audio = audio[a:b]
            h.peak_db = A.db(float(seg.max()))
            idx = np.where(seg > thr)[0]
            h.latency_ms = idx[0] / sr * 1000 if len(idx) else None
    return hits, audio, sr


def evaluate(hits: list[Hit]) -> list[A.Problem]:
    probs: list[A.Problem] = []
    by_note: dict[int, list[Hit]] = {}
    for h in hits:
        by_note.setdefault(h.note, []).append(h)
    if not any(h.audio is not None for h in hits):
        return probs
    lats = [h.latency_ms for h in hits if h.latency_ms is not None]
    base = float(np.median(lats)) if lats else None
    if base is not None:
        probs.append(A.Problem("INFO", "latencia", f"Retardo típico MIDI→audio: {base:.0f} ms (incluye USB y la interfaz de audio; "
                               "se usa como referencia para comparar las notas)."))
    clipped = [h for h in hits if h.peak_db > -0.3]
    if clipped:
        probs.append(A.Problem("AVISO", "rec_clip", "La grabación llegó a 0 dBFS en " +
                               ", ".join(f"{note_name(h.note)}/v{h.vel}" for h in clipped[:8]) +
                               ". Baja la ganancia de la interfaz o el volumen del teclado y repite."))
    for n, hs in sorted(by_note.items()):
        hs = sorted(hs, key=lambda h: h.vel)
        mute = [h for h in hs if h.latency_ms is None]
        if mute:
            probs.append(A.Problem("ERROR", "mudo", f"{note_name(n)} '{hs[0].name}' no sonó con velocidad " +
                                   ", ".join(str(h.vel) for h in mute) +
                                   ". Revisa que el pack esté instalado y la voz seleccionada en el canal correcto."))
            continue
        lat = [h.latency_ms for h in hs]
        if base is not None and max(lat) > base + 15:
            probs.append(A.Problem("AVISO", "lento", f"{note_name(n)} '{hs[0].name}' tarda {max(lat) - base:.0f} ms más que el resto en sonar: "
                                   "hay silencio al inicio de la muestra o un ataque lento."))
        if len(hs) > 1:
            span = hs[-1].peak_db - hs[0].peak_db
            if span < 3:
                probs.append(A.Problem("INFO", "sin_dinamica", f"{note_name(n)} '{hs[0].name}': casi no cambia de volumen entre "
                                       f"velocidad {hs[0].vel} y {hs[-1].vel} ({span:.1f} dB). Revisa la sensibilidad de velocidad."))
            for a, b in zip(hs, hs[1:]):
                if b.peak_db < a.peak_db - 2:
                    probs.append(A.Problem("AVISO", "dinamica_inv", f"{note_name(n)}: suena más suave con velocidad {b.vel} que con {a.vel}."))
    # balance real del kit a velocidad maxima
    top = [max(hs, key=lambda h: h.vel) for hs in by_note.values()]
    loud = max(h.peak_db for h in top)
    for h in sorted(top, key=lambda h: h.note):
        if h.peak_db < loud - 18:
            probs.append(A.Problem("INFO", "rec_balance", f"En el teclado, {note_name(h.note)} '{h.name}' suena {loud - h.peak_db:.0f} dB "
                                   "más bajo que la nota más fuerte del kit."))
    return probs
