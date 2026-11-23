"""Demos del kit para compartir (WhatsApp, redes): render sin conexión y MP3.

El MP3 usa el codificador LAME (paquete «lameenc», LGPL). Si no está instalado,
se guarda en WAV.
"""
from __future__ import annotations

import numpy as np

import grooves
from motor import SR


def _mezclar(eventos, total: int) -> np.ndarray:
    """eventos: [(inicio, buf estéreo, grupo)]. Respeta los grupos de corte (hi-hat)."""
    out = np.zeros((total, 2), np.float64)
    sonando: dict[int, tuple[int, np.ndarray]] = {}
    eventos = sorted(eventos, key=lambda e: e[0])
    cortes = []
    for i, (t0, buf, g) in enumerate(eventos):
        if g:
            prev = sonando.get(g)
            if prev is not None:
                cortes.append((prev[0], t0))
            sonando[g] = (i, buf)
    fin = {i: t for i, t in cortes}
    for i, (t0, buf, g) in enumerate(eventos):
        if t0 >= total:
            continue
        b = buf.astype(np.float64)
        if i in fin:
            n = max(0, fin[i] - t0)
            b = b[: n + int(SR * 0.006)].copy()
            k = min(len(b), int(SR * 0.006))
            if k > 1:
                b[-k:] *= np.linspace(1, 0, k)[:, None]
        n = min(len(b), total - t0)
        out[t0:t0 + n] += b[:n]
    return out


def _limitar(x: np.ndarray, techo_db: float = -1.0) -> np.ndarray:
    pk = np.abs(x).max()
    techo = 10 ** (techo_db / 20)
    if pk <= techo or pk == 0:
        return x
    # compresión suave de picos y normalización
    y = np.tanh(x / pk * 1.5) / np.tanh(1.5)
    return y * techo


def render_ritmo(engine, nombre: str, bpm: float = 76, compases: int = 4, swing: float = 0.0,
                 humanizar: bool = True) -> np.ndarray:
    pasos, sub, notas = grooves.PATRONES[nombre]
    disp = {n for el, kb, lo, hi, vlo, vhi in engine.voice.zones() for n in range(lo, hi + 1)}
    dt = 60.0 / bpm / sub
    evs = []
    rng = np.random.default_rng(3)
    antes = engine.settings.humanizar
    engine.settings.humanizar = humanizar
    try:
        for c in range(compases):
            for st, n, v in notas:
                m = grooves.adaptar(n, disp)
                if m is None:
                    continue
                t = (c * pasos + st) * dt
                if swing and st % 2 == 1 and sub % 2 == 0:
                    t += swing * dt
                if humanizar:
                    t += rng.normal(0, 0.004)
                    v = int(np.clip(v + rng.normal(0, 4), 1, 127))
                buf, g = engine.render_play(m, v)
                evs.append((max(0, int(t * SR)), buf, g))
    finally:
        engine.settings.humanizar = antes
    total = int((compases * pasos * dt + 2.5) * SR)
    return _mezclar(evs, total)


def render_estilo(engine, estilo, secuencia=None, bpm: float | None = None, humanizar: bool = False) -> np.ndarray:
    """La batería de un estilo Yamaha (.sty) tocada con el kit. secuencia: lista de secciones
    (por defecto Intro, los Main con sus Fill y un Ending)."""
    import estilos
    sec = secuencia or estilos.secuencia_demo(estilo)
    evs_est, dur = estilos.eventos_secuencia(estilo, sec, bpm)
    disp = {n for el, kb, lo, hi, vlo, vhi in engine.voice.zones() for n in range(lo, hi + 1)}
    mapa = {n: grooves.adaptar(n, disp) for n in estilo.notas()}
    evs = []
    rng = np.random.default_rng(5)
    antes = engine.settings.humanizar
    engine.settings.humanizar = humanizar
    try:
        for t, n, v, ch in evs_est:
            m = mapa.get(n)
            if m is None:
                continue
            buf, g = engine.render_play(m, v)
            gan = estilo.ganancia.get(ch, 1.0)
            if gan < 0.999:
                buf = buf * gan
            if humanizar:
                t += rng.normal(0, 0.003)
            evs.append((max(0, int(t * SR)), buf, g))
    finally:
        engine.settings.humanizar = antes
    return _mezclar(evs, int((dur + 2.5) * SR))


def render_recorrido(engine, velocidades=(60, 115), pausa_s: float = 0.45) -> np.ndarray:
    """Cada tecla del kit, suave y fuerte."""
    notas = sorted({lo for el, kb, lo, hi, vlo, vhi in engine.voice.zones()})
    evs, t = [], 0.0
    for n in notas:
        for v in velocidades:
            buf, g = engine.render(n, v)
            evs.append((int(t * SR), buf, 0))
            t += pausa_s
        t += 0.15
    return _mezclar(evs, int((t + 2.0) * SR))


def demo_kit(engine, ritmos=("Worship 4/4 (toms)", "Balada 4/4"), bpm: float = 76, compases: int = 4,
             recorrido: bool = True, estilo=None, bpm_estilo: float | None = None) -> np.ndarray:
    partes = []
    if recorrido:
        partes.append(render_recorrido(engine))
    if estilo is not None:
        partes.append(render_estilo(engine, estilo, bpm=bpm_estilo))
    for r in ritmos:
        partes.append(render_ritmo(engine, r, bpm, compases))
    silencio = np.zeros((int(SR * 0.4), 2))
    x = np.vstack([p for parte in partes for p in (parte, silencio)])
    # recortar silencio final
    a = np.abs(x).max(axis=1)
    idx = np.where(a > 10 ** (-70 / 20))[0]
    if len(idx):
        x = x[: idx[-1] + int(SR * 0.3)]
    return _limitar(x)


def mp3_disponible() -> bool:
    try:
        import lameenc  # noqa: F401
        return True
    except ImportError:
        return False


def guardar_mp3(path: str, x: np.ndarray, kbps: int = 192, sr: int = SR):
    import lameenc
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    pcm = np.clip(np.round(x[:, :2] * 32767), -32768, 32767).astype("<i2")
    enc = lameenc.Encoder()
    enc.set_bit_rate(int(kbps))
    enc.set_in_sample_rate(int(sr))
    enc.set_channels(2)
    enc.set_quality(2)
    data = enc.encode(pcm.tobytes()) + enc.flush()
    with open(path, "wb") as f:
        f.write(data)


def guardar(path: str, x: np.ndarray, sr: int = SR) -> str:
    """Guarda en MP3 si la ruta termina en .mp3 (y hay codificador); si no, en WAV. Devuelve la ruta final."""
    if path.lower().endswith(".mp3"):
        if mp3_disponible():
            guardar_mp3(path, x, sr=sr)
            return path
        path = path[:-4] + ".wav"
    from ppf_tester import _write_wav
    _write_wav(path, x, sr)
    return path
