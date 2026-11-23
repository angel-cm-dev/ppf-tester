"""Estilos de acompañamiento Yamaha (.sty) para probar el kit en contexto.

Un .sty es un archivo MIDI estándar (más bloques CASM/OTS/MDB al final que aquí no se usan).
Las secciones van marcadas con «markers»: Intro A-C, Main A-D, Fill In AA-DD, Fill In BA (Break)
y Ending A-C, como en los botones de la serie PSR-S. La batería va en los canales 9 y 10
(Rhythm 1 y Rhythm 2). Solo se toma la batería: se toca con el kit abierto, que es lo que
queremos escuchar.
"""
from __future__ import annotations

import os
import struct
import threading
import time
from dataclasses import dataclass, field

CANALES_RITMO = (8, 9)  # 0-based: canal MIDI 9 = Rhythm 1, 10 = Rhythm 2

# Orden de los botones en el panel de un PSR-S
ORDEN = ["Intro A", "Intro B", "Intro C", "Intro D",
         "Main A", "Main B", "Main C", "Main D",
         "Fill In AA", "Fill In BB", "Fill In CC", "Fill In DD", "Fill In BA",
         "Ending A", "Ending B", "Ending C", "Ending D"]
NO_SECCION = {"SFF1", "SFF2", "SInt"}


def tipo(seccion: str) -> str:
    """'intro' | 'main' | 'fill' | 'break' | 'ending' | 'otro'."""
    s = seccion.lower()
    if s.startswith("intro"):
        return "intro"
    if s.startswith("main"):
        return "main"
    if s == "fill in ba" or s.startswith("break"):
        return "break"
    if s.startswith("fill"):
        return "fill"
    if s.startswith("ending"):
        return "ending"
    return "otro"


def fill_de(main: str) -> str:
    """Fill In que corresponde a un Main: Main B -> Fill In BB."""
    x = main.split()[-1]
    return f"Fill In {x}{x}"


def etiqueta(seccion: str) -> str:
    """Nombre corto para un botón: 'Fill In BB' -> 'Fill B', 'Fill In BA' -> 'Break'."""
    t = tipo(seccion)
    if t == "break":
        return "Break"
    if t == "fill":
        x = seccion.split()[-1]
        return "Fill " + (x[-1] if x[0] == x[-1] else x)
    return seccion


@dataclass
class Seccion:
    nombre: str
    largo: int                                   # en ticks
    eventos: list[tuple[int, int, int, int]]    # (tick relativo, nota, velocidad, canal)

    @property
    def tipo(self) -> str:
        return tipo(self.nombre)


@dataclass
class Estilo:
    path: str
    nombre: str
    ppq: int
    tempo: float
    compas: tuple[int, int]
    secciones: dict[str, Seccion] = field(default_factory=dict)
    ganancia: dict[int, float] = field(default_factory=dict)   # canal -> 0..1 (volumen del SInt)

    @property
    def ticks_compas(self) -> int:
        num, den = self.compas
        return int(self.ppq * 4 * num / den)

    def compases(self, seccion: str) -> int:
        s = self.secciones[seccion]
        return max(1, round(s.largo / self.ticks_compas))

    def ordenadas(self) -> list[str]:
        r = [s for s in ORDEN if s in self.secciones]
        return r + sorted(s for s in self.secciones if s not in r)

    def notas(self) -> dict[int, int]:
        """nota -> número de golpes en todo el estilo."""
        c: dict[int, int] = {}
        for s in self.secciones.values():
            for _, n, _, _ in s.eventos:
                c[n] = c.get(n, 0) + 1
        return c


class ErrorEstilo(ValueError):
    pass


def _vlq(d: bytes, i: int) -> tuple[int, int]:
    v = 0
    while True:
        b = d[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def _pistas(d: bytes):
    if d[:4] != b"MThd":
        raise ErrorEstilo("No es un estilo Yamaha (.sty): falta la cabecera MIDI.")
    hl, fmt, ntr, div = struct.unpack(">IHHH", d[4:14])
    if div & 0x8000:
        raise ErrorEstilo("Formato de tiempo SMPTE no soportado.")
    i = 8 + hl
    pistas = []
    while len(pistas) < ntr and i + 8 <= len(d) and d[i:i + 4] == b"MTrk":
        n = struct.unpack(">I", d[i + 4:i + 8])[0]
        pistas.append(d[i + 8:i + 8 + n])
        i += 8 + n
    if not pistas:
        raise ErrorEstilo("El estilo no tiene pistas MIDI.")
    return div, pistas


def _eventos(trk: bytes):
    """Genera (tick, tipo, datos). tipo: 'nota', 'cc', 'meta'."""
    i, t, st = 0, 0, 0
    n = len(trk)
    while i < n:
        dt, i = _vlq(trk, i)
        t += dt
        if i >= n:
            break
        b = trk[i]
        if b == 0xFF:
            mt = trk[i + 1]
            ln, j = _vlq(trk, i + 2)
            yield t, "meta", (mt, trk[j:j + ln])
            i = j + ln
            if mt == 0x2F:
                break
            continue
        if b in (0xF0, 0xF7):
            ln, j = _vlq(trk, i + 1)
            i = j + ln
            continue
        if b & 0x80:
            st = b
            i += 1
        elif not st:
            raise ErrorEstilo("Datos MIDI dañados en el estilo.")
        hi, ch = st & 0xF0, st & 0x0F
        if hi in (0xC0, 0xD0):
            d1 = trk[i]
            i += 1
            continue
        d1, d2 = trk[i], trk[i + 1]
        i += 2
        if hi == 0x90 and d2 > 0:
            yield t, "nota", (ch, d1, d2)
        elif hi == 0xB0:
            yield t, "cc", (ch, d1, d2)


def leer(path: str) -> Estilo:
    with open(path, "rb") as f:
        d = f.read()
    try:
        ppq, pistas = _pistas(d)
    except (struct.error, IndexError) as e:
        raise ErrorEstilo("El archivo no es un estilo válido.") from e
    tempo, compas = 120.0, (4, 4)
    marcas: list[tuple[int, str]] = []
    notas: list[tuple[int, int, int, int]] = []
    ccs: list[tuple[int, int, int, int]] = []
    tempos: list = []
    compases: list = []
    fin = 0
    for trk in pistas:
        try:
            for t, k, x in _eventos(trk):
                fin = max(fin, t)
                if k == "nota":
                    ch, n, v = x
                    if ch in CANALES_RITMO:
                        notas.append((t, n, v, ch))
                elif k == "cc":
                    if x[0] in CANALES_RITMO and x[1] in (7, 11):
                        ccs.append((t, *x))
                else:
                    mt, data = x
                    if mt == 0x51 and len(data) == 3 and int.from_bytes(data, "big"):
                        tempos.append((t, 60e6 / int.from_bytes(data, "big")))
                    elif mt == 0x58 and len(data) >= 2:
                        compases.append((t, (max(1, data[0]), 2 ** min(data[1], 5))))
                    elif mt == 0x06:
                        marcas.append((t, data.decode("latin-1").strip()))
        except IndexError:
            pass   # pista cortada: nos quedamos con lo leído
    marcas.sort()
    if tempos:
        tempo = min(tempos)[1]
    if compases:
        compas = min(compases)[1]
    secs = [(t, m) for t, m in marcas if m not in NO_SECCION]
    if not secs:
        raise ErrorEstilo("No se encontraron secciones (Intro, Main, Fill, Ending) en el estilo.")
    nombre = os.path.splitext(os.path.basename(path))[0]
    # quitar la extensión de modelo (p. ej. «Balada.S910»)
    if "." in nombre and len(nombre.rsplit(".", 1)[1]) <= 5:
        nombre = nombre.rsplit(".", 1)[0]
    est = Estilo(path, nombre.strip(), ppq, round(tempo, 1), compas)
    notas.sort()
    for k, (t0, m) in enumerate(secs):
        t1 = secs[k + 1][0] if k + 1 < len(secs) else max(fin, t0 + 1)
        if t1 <= t0 or m in est.secciones:
            continue
        ev = [(t - t0, n, v, ch) for t, n, v, ch in notas if t0 <= t < t1]
        est.secciones[m] = Seccion(m, t1 - t0, ev)
    # volumen de cada canal de ritmo en la zona inicial (SInt)
    t_ini = secs[0][0]
    vol = {ch: {7: 100, 11: 127} for ch in CANALES_RITMO}
    for t, ch, cc, v in sorted(ccs):
        if t <= t_ini:
            vol[ch][cc] = v
    amp = {ch: (vol[ch][7] / 127) ** 2 * (vol[ch][11] / 127) ** 2 for ch in CANALES_RITMO}
    top = max(amp.values()) or 1.0
    est.ganancia = {ch: a / top for ch, a in amp.items()}
    return est


# --------------------------------------------------------------- kit vs estilo
# Nombres de la percusión del mapa XG/GM (los de batería están en importar_wav.GM)
PERCUSION = {25: "Redoble", 26: "Chasquido", 27: "High Q", 28: "Slap", 29: "Scratch", 30: "Scratch 2", 31: "Baquetas",
             32: "Click", 33: "Metrónomo", 34: "Campana metrónomo", 58: "Vibraslap", 60: "Bongó agudo",
             61: "Bongó grave", 62: "Conga apagada", 63: "Conga abierta", 64: "Conga grave", 65: "Timbal agudo",
             66: "Timbal grave", 67: "Agogó agudo", 68: "Agogó grave", 69: "Cabasa", 70: "Maracas",
             71: "Silbato corto", 72: "Silbato largo", 73: "Güiro corto", 74: "Güiro largo", 75: "Claves",
             76: "Bloque agudo", 77: "Bloque grave", 78: "Cuíca apagada", 79: "Cuíca abierta",
             80: "Triángulo apagado", 81: "Triángulo abierto", 82: "Shaker", 83: "Cascabeles", 84: "Bell tree"}


def nombre_nota(n: int) -> str:
    import importar_wav as I
    from ppf_format import note_name
    nom = I.GM.get(n) or PERCUSION.get(n)
    return f"{note_name(n)} {nom}" if nom else note_name(n)

def faltantes(est: Estilo, disponibles: set[int]) -> list[tuple[int, int]]:
    """Notas que el estilo toca y el kit no tiene (ni un sustituto): [(nota, golpes)], las más usadas primero."""
    import grooves
    r = [(n, c) for n, c in est.notas().items() if grooves.adaptar(n, disponibles) is None]
    return sorted(r, key=lambda x: -x[1])


def resumen_faltantes(est: Estilo, disponibles: set[int], maximo: int = 6) -> str:
    f = faltantes(est, disponibles)
    if not f:
        return ""
    total = sum(est.notas().values()) or 1
    partes = [f"{nombre_nota(n)} ({c})" for n, c in f[:maximo]]
    pct = 100 * sum(c for _, c in f) / total
    mas = f" y {len(f) - maximo} más" if len(f) > maximo else ""
    return f"Al kit le faltan {len(f)} sonidos que usa el estilo ({pct:.0f} % de los golpes): " + ", ".join(partes) + mas


# --------------------------------------------------------------- reproducción
class Reproductor:
    """Toca un estilo como el PSR: Intro -> Main en bucle, Fill al cambiar de Main, Break y Ending.

    tocar(nota, velocidad, ganancia) debe ser thread-safe. Los cambios se aplican al siguiente
    pulso (fill/break) o al siguiente compás (main sin fill, ending), como en el teclado.
    """

    def __init__(self, estilo: Estilo, tocar, disponibles: set[int], al_cambiar=None):
        import grooves
        self.est = estilo
        self.tocar = tocar
        self.al_cambiar = al_cambiar      # al_cambiar(seccion o None) cuando empieza una sección / termina
        self.autofill = True
        self.bpm = estilo.tempo
        self.metronomo = None
        self._map = {n: grooves.adaptar(n, disponibles) for n in estilo.notas()}
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pedido: tuple[str, str] | None = None   # (tipo de cambio, sección)
        self.main = next((s for s in estilo.ordenadas() if tipo(s) == "main"), None)
        self.actual: str | None = None
        self.th = None

    @property
    def sonando(self) -> bool:
        return self.th is not None and self.th.is_alive()

    def start(self, seccion: str | None = None):
        """Empieza por 'seccion' (una Intro o un Main) o por el Main elegido."""
        self.stop()
        if seccion and tipo(seccion) == "main":
            self.main = seccion
        primera = seccion or self.main
        if primera not in self.est.secciones:
            raise ValueError("El estilo no tiene esa sección.")
        self._stop.clear()
        self._pedido = None
        self.th = threading.Thread(target=self._run, args=(primera,), daemon=True)
        self.th.start()

    def pedir(self, seccion: str):
        """Botón del panel mientras suena."""
        if seccion not in self.est.secciones:
            return
        t = tipo(seccion)
        with self._lock:
            if t == "main" and tipo(self.actual or "") in ("intro", "ending"):
                self.main = seccion          # como en el PSR: elige qué Main sigue a la Intro
            elif t == "main":
                f = fill_de(seccion)
                if f not in self.est.secciones and self.main:   # estilos antiguos: Fill In AB = de A a B
                    f = f"Fill In {self.main.split()[-1]}{seccion.split()[-1]}"
                if self.autofill and f in self.est.secciones:
                    self._pedido = ("fill", f)
                else:
                    self._pedido = ("compas", seccion)
                self.main = seccion
            elif t in ("fill", "break"):
                self._pedido = ("fill", seccion)
            elif t == "ending":
                self._pedido = ("compas", seccion)
            elif t == "intro":
                self._pedido = ("compas", seccion)

    def stop(self):
        self._stop.set()
        if self.th and threading.current_thread() is not self.th:
            self.th.join(timeout=1)
        self.th = None

    def _run(self, sec: str):
        est = self.est
        ppq = est.ppq
        tc = est.ticks_compas
        num, den = est.compas
        tpulso = ppq * 4 // den
        t0 = time.perf_counter()
        pos = 0.0                    # tiempo (s) donde empieza la sección actual
        inicio = 0                   # tick de la sección donde se empieza (fill a mitad de compás)
        while not self._stop.is_set() and sec is not None:
            s = est.secciones[sec]
            self.actual = sec
            if self.al_cambiar:
                self.al_cambiar(sec)
            dt = 60.0 / max(20.0, self.bpm) / ppq
            evs = [e for e in s.eventos if e[0] >= inicio]
            largo = s.largo
            k = 0
            salto = None             # (tick de corte, sección, tick de inicio en la nueva)
            tick = inicio
            while tick < largo and not self._stop.is_set():
                with self._lock:
                    ped = self._pedido
                if ped is not None and salto is None:
                    clase, destino = ped
                    if clase == "fill":
                        corte = (tick // tpulso + 1) * tpulso
                        salto = (corte, destino, corte % tc)
                    else:
                        corte = (tick // tc + 1) * tc
                        salto = (corte, destino, 0)
                    with self._lock:
                        self._pedido = None
                limite = min(largo, salto[0]) if salto else largo
                # próximo evento o pulso
                prox = evs[k][0] if k < len(evs) else limite
                prox_pulso = (tick // tpulso + 1) * tpulso
                objetivo = min(prox, prox_pulso, limite)
                espera = t0 + pos + (objetivo - inicio) * dt - time.perf_counter()
                if espera > 0:
                    self._stop.wait(min(espera, 0.05))
                    if time.perf_counter() < t0 + pos + (objetivo - inicio) * dt:
                        continue
                tick = objetivo
                if tick >= limite:
                    break
                if self.metronomo is not None and tick % tpulso == 0:
                    self.metronomo((tick % tc) == 0)
                while k < len(evs) and evs[k][0] <= tick:
                    _, n, v, ch = evs[k]
                    m = self._map.get(n)
                    if m is not None:
                        self.tocar(m, v, est.ganancia.get(ch, 1.0))
                    k += 1
            if self._stop.is_set():
                break
            fin = min(largo, salto[0]) if salto else largo
            pos += (fin - inicio) * dt
            if salto:
                # un fill empieza en el mismo pulso del compás y al terminar vuelve al Main
                sec, inicio = salto[1], salto[2]
            else:
                inicio = 0
                if tipo(sec) in ("fill", "break", "intro"):
                    sec = self.main
                elif tipo(sec) == "ending":
                    sec = None
                # main: vuelve a empezar (bucle)
        self.actual = None
        if self.al_cambiar:
            self.al_cambiar(None)


# --------------------------------------------------------------- render sin conexión
def secuencia_demo(est: Estilo) -> list[str]:
    """Recorrido típico: Intro A, Main A, Fill, Main B, Fill, Main C… Ending A."""
    s = est.secciones
    r = []
    intro = next((x for x in ("Intro A", "Intro B", "Intro C") if x in s), None)
    if intro:
        r.append(intro)
    mains = [m for m in ("Main A", "Main B", "Main C", "Main D") if m in s]
    for i, m in enumerate(mains):
        r += [m, m] if est.compases(m) <= 2 else [m]
        sig = mains[i + 1] if i + 1 < len(mains) else None
        if sig and fill_de(sig) in s:
            r.append(fill_de(sig))
    fin = next((x for x in ("Ending A", "Ending B", "Ending C") if x in s), None)
    if fin:
        r.append(fin)
    return r


def eventos_secuencia(est: Estilo, secuencia: list[str], bpm: float | None = None):
    """[(segundos, nota, velocidad, canal)] de una lista de secciones tocadas una tras otra."""
    dt = 60.0 / (bpm or est.tempo) / est.ppq
    out, t0 = [], 0
    for sec in secuencia:
        s = est.secciones[sec]
        out += [((t0 + t) * dt, n, v, ch) for t, n, v, ch in s.eventos]
        t0 += s.largo
    return out, t0 * dt
