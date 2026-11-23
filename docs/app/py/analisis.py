"""Analisis de calidad de las muestras y del mapa del kit/voz."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ppf_format import Pack, Wave, note_name

SILENCE_DB = -60.0     # por debajo se considera silencio (inicio)
TAIL_DB = -72.0        # umbral para la cola (los platos decaen muy suave)
EPS = 1e-12


def db(x: float) -> float:
    return 20 * np.log10(max(abs(x), EPS))


@dataclass
class Problem:
    level: str      # "ERROR" | "AVISO" | "INFO"
    code: str
    text: str
    fixable: bool = False


@dataclass
class WaveReport:
    name: str
    uid: str
    channels: int
    rate: float
    frames: int
    duration: float
    peak_db: float
    rms_db: float
    dc_pct: float
    clipped: int
    lead_silence_ms: float
    tail_silence_ms: float
    end_level_db: float
    start_level_db: float
    noise_floor_db: float
    loop_jump_db: float | None
    problems: list[Problem] = field(default_factory=list)

    @property
    def worst(self) -> str:
        lv = [p.level for p in self.problems]
        return "ERROR" if "ERROR" in lv else "AVISO" if "AVISO" in lv else "OK"


def _window_rms(x: np.ndarray, win: int) -> np.ndarray:
    n = len(x) // win
    if n == 0:
        return np.array([np.sqrt(np.mean(x ** 2))]) if len(x) else np.array([0.0])
    return np.sqrt(np.mean(x[:n * win].reshape(n, win) ** 2, axis=1))


def analyze_wave(w: Wave, one_shot: bool = True) -> WaveReport:
    x = w.samples
    mono = x.mean(axis=1) if x.shape[1] > 1 else x[:, 0]
    absx = np.abs(x).max(axis=1)
    sr = w.rate or 44100.0
    peak = float(absx.max()) if len(absx) else 0.0
    rms = float(np.sqrt(np.mean(mono ** 2))) if len(mono) else 0.0
    dc = float(np.mean(mono)) if len(mono) else 0.0

    # clipping: 3+ muestras consecutivas en el limite
    lim = absx >= (32766 / 32768)
    clipped = 0
    if lim.any():
        runs = np.diff(np.concatenate([[0], lim.astype(int), [0]]))
        starts, ends = np.where(runs == 1)[0], np.where(runs == -1)[0]
        clipped = int(np.sum((ends - starts) >= 3))

    thr = 10 ** (SILENCE_DB / 20)
    above = np.where(absx > thr)[0]
    above_t = np.where(absx > 10 ** (TAIL_DB / 20))[0]
    if len(above):
        lead = above[0] / sr * 1000
        tail = (len(absx) - 1 - above_t[-1]) / sr * 1000
    else:
        lead, tail = len(absx) / sr * 1000, 0.0

    n_edge = max(1, int(sr * 0.002))           # ultimos/primeros 2 ms
    end_level = db(absx[-n_edge:].max()) if len(absx) else -120
    start_level = db(absx[0]) if len(absx) else -120

    # ruido de fondo: cola que NO decae (siseo estacionario), medida en los
    # ultimos 300 ms de la parte con sonido
    noise_floor = -120.0
    if len(above) and above[-1] > sr * 0.6:
        seg = mono[int(above[-1] - sr * 0.3):above[-1]]
        h = len(seg) // 2
        r1, r2 = np.sqrt(np.mean(seg[:h] ** 2)), np.sqrt(np.mean(seg[h:] ** 2))
        if r1 > EPS and r2 > EPS and db(r1) - db(r2) < 2.0:
            noise_floor = db(r2)

    loop_jump = None
    lp = w.loop_points
    if lp and not one_shot:
        s, e = lp
        e = min(e, len(mono) - 1)
        if 0 <= s < e:
            loop_jump = db(float(np.max(np.abs(x[e] - x[s]))))

    r = WaveReport(w.name, w.uid, w.channels, sr, w.frames, w.duration, db(peak), db(rms),
                   dc * 100, clipped, lead, tail, end_level, start_level, noise_floor, loop_jump)
    P = r.problems.append

    if peak == 0:
        P(Problem("ERROR", "silencio", "La muestra está completamente en silencio."))
        return r
    if clipped:
        P(Problem("ERROR", "clip", f"Saturación digital: {clipped} tramo(s) recortados en 0 dBFS. "
                  "No se puede reparar bien; conviene volver a exportar la muestra con menos nivel."))
    elif r.peak_db > -0.1:
        P(Problem("AVISO", "pico", f"Pico en {r.peak_db:.2f} dBFS, sin margen. Puede saturar al sumarse con otras notas.", True))
    if r.peak_db < -12:
        P(Problem("INFO", "bajo", f"Nivel bajo (pico {r.peak_db:.1f} dBFS). Si en el teclado suena demasiado suave frente al resto, "
                  "súbelo con --normalizar o con el volumen de la nota.", True))
    if abs(r.dc_pct) > 0.5:
        P(Problem("AVISO", "dc", f"DC offset de {r.dc_pct:.2f} %: reduce margen y produce clics al empezar/cortar.", True))
    if start_level > -30:
        P(Problem("AVISO", "clic_ini", f"Empieza con un salto brusco ({start_level:.1f} dBFS en la primera muestra): clic al inicio.", True))
    if lead > 15:
        P(Problem("AVISO", "sil_ini", f"{lead:.0f} ms de silencio al inicio: el golpe suena con retraso.", True))
    elif lead > 5:
        P(Problem("INFO", "sil_ini", f"{lead:.0f} ms de silencio al inicio (pequeño retraso del golpe).", True))
    if one_shot and end_level > -40:
        P(Problem("AVISO", "corte", f"Termina cortada ({end_level:.1f} dBFS en los últimos 2 ms): se oye un corte o clic al final.", True))
    if tail > 80:
        P(Problem("INFO", "sil_fin", f"{tail:.0f} ms de silencio al final: ocupa memoria sin aportar sonido.", True))
    if noise_floor > -66:
        P(Problem("AVISO" if noise_floor > -50 else "INFO", "ruido",
                  f"La cola termina en un ruido constante de ~{noise_floor:.0f} dBFS (no se apaga): siseo o zumbido de fondo."))
    if sr != 44100:
        P(Problem("AVISO", "sr", f"Frecuencia de muestreo {sr:.0f} Hz (lo normal es 44100 Hz)."))
    if loop_jump is not None and loop_jump > -30:
        P(Problem("AVISO", "loop", f"Salto de {loop_jump:.1f} dBFS en el punto de loop: clic en cada repetición."))
    return r


@dataclass
class KitReport:
    voice: str
    voice_type: str
    zones: list[dict]
    problems: list[Problem]


def analyze_voice(pack: Pack, voice) -> KitReport:
    zones, problems = [], []
    used = set()
    by_note: dict[int, list[tuple[int, int]]] = {}
    for el, kb, lo, hi, vlo, vhi in voice.zones():
        names = []
        for s in kb.samples:
            used.add(s.wave_uid)
            w = pack.waves.get(s.wave_uid)
            if w is None:
                problems.append(Problem("ERROR", "falta", f"La nota {note_name(lo)} usa una onda que no está en el archivo ({s.wave_uid[:8]}…)."))
            else:
                names.append(w.name)
        fake_stereo = (len(kb.samples) == 2 and kb.samples[0].wave_uid == kb.samples[1].wave_uid)
        zones.append(dict(note_lo=lo, note_hi=hi, vel_lo=vlo, vel_hi=vhi, element=el.number,
                          samples=names, one_shot=kb.one_shot, fake_stereo=fake_stereo,
                          uid=kb.samples[0].wave_uid))
        for n in range(lo, hi + 1):
            by_note.setdefault(n, []).append((vlo, vhi))

    # huecos de velocidad
    for n, ranges in sorted(by_note.items()):
        cover = np.zeros(128, bool)
        for a, b in ranges:
            cover[a:b + 1] = True
        missing = [v for v in range(1, 128) if not cover[v]]
        if missing:
            problems.append(Problem("AVISO", "vel", f"Nota {note_name(n)}: no suena con velocidades {missing[0]}–{missing[-1]}."))
    # fase de las muestras estéreo reales (L y R distintas)
    import sonido
    vistos = set()
    for el, kb, lo, hi, vlo, vhi in voice.zones():
        if len(kb.samples) == 2 and kb.samples[0].wave_uid != kb.samples[1].wave_uid:
            par = (kb.samples[0].wave_uid, kb.samples[1].wave_uid)
            wl, wr = pack.waves.get(par[0]), pack.waves.get(par[1])
            if par in vistos or wl is None or wr is None:
                continue
            vistos.add(par)
            pr = sonido.fase(wl.samples, wr.samples, wl.rate).problema
            if pr:
                problems.append(Problem("AVISO", "fase", f"{note_name(lo)} '{wl.name}': {pr}.", True))
    fake = sum(1 for z in zones if z["fake_stereo"])
    if fake:
        problems.append(Problem("INFO", "falso_estereo",
                                f"{fake} zona(s) usan la misma muestra mono en L y R (estéreo falso). Suena igual que mono."))
    for uid, w in pack.waves.items():
        if uid not in used:
            problems.append(Problem("INFO", "sin_uso", f"La muestra '{w.name}' no la usa ninguna nota: ocupa memoria sin sonar."))
    # notas repetidas con la misma muestra
    rep: dict[str, list[int]] = {}
    for z in zones:
        rep.setdefault(z["uid"], []).append(z["note_lo"])
    els = {e.number: e for e in voice.elements}
    tune_of = {z["note_lo"]: (els[z["element"]].tune_coarse, els[z["element"]].tune_fine, els[z["element"]].pitch_coarse) for z in zones}
    for uid, notes in rep.items():
        if len(notes) > 1 and uid in pack.waves and len({tune_of[n] for n in notes}) == 1:
            problems.append(Problem("AVISO" if len(notes) > 2 else "INFO", "repetida",
                                    f"'{pack.waves[uid].name}' suena idéntica en {len(notes)} notas ({', '.join(note_name(n) for n in notes)}): "
                                    "si quieres que cada tecla suene distinta, ajusta su afinación (Tune) en Expansion Manager."))
    # hi-hat: cerrado (42), pedal (44) y abierto (46) deberían cortarse entre sí
    hh = [n for n in (42, 44, 46) if n in by_note]
    if 46 in hh and len(hh) > 1:
        groups = {els[n].alternate_group for n in hh if n in els}
        if 0 in groups or len(groups) > 1:
            problems.append(Problem("AVISO", "hihat",
                                    "El hi-hat abierto (A#1) no se corta al tocar el cerrado/pedal (F#1/G#1): "
                                    "ponlos en el mismo 'Alternate Group'.", True))
    # balance del kit
    levels = []
    for z in zones:
        w = pack.waves.get(z["uid"])
        if w is not None:
            levels.append((z["note_lo"], w.name, db(float(np.abs(w.samples).max()))))
    if levels:
        top = max(l[2] for l in levels)
        for n, nm, lv in levels:
            if lv < top - 15:
                problems.append(Problem("INFO", "balance",
                                        f"{note_name(n)} '{nm}' está {top - lv:.0f} dB por debajo de la muestra más fuerte del kit."))
    return KitReport(voice.name, voice.voice_type, zones, problems)


def memory_bytes(pack: Pack) -> int:
    return sum(w.frames * w.channels * 2 for w in pack.waves.values())
