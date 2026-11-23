"""Biblioteca de muestras: tus golpes favoritos guardados para reutilizarlos en otros kits.

Cada muestra se guarda como WAV (float 32 bits, 44.1 kHz) en la carpeta de datos de la
app, con un índice JSON: nombre, pieza, etiquetas, favorito y de dónde salió.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import time
from dataclasses import asdict, dataclass, field

import numpy as np

SR = 44100


def carpeta_datos() -> str:
    import registro
    return registro.CARPETA


@dataclass
class Muestra:
    id: str
    nombre: str
    tipo: str                       # tipos de importar_wav.PIEZAS (kick, snare, tom…)
    archivo: str                    # ruta relativa dentro de la biblioteca
    dur: float
    canales: int
    origen: str = ""
    etiquetas: list[str] = field(default_factory=list)
    fav: bool = False
    creado: float = 0.0


def escribir_wav_float(path: str, x: np.ndarray, sr: int = SR):
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    ch = x.shape[1]
    data = x.astype("<f4").tobytes()
    fmt = struct.pack("<HHIIHH", 3, ch, sr, sr * ch * 4, ch * 4, 32)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(data)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        f.write(b"data" + struct.pack("<I", len(data)) + data)


def _seguro(s: str) -> str:
    return re.sub(r"[^\w\- ]+", "", s).strip()[:40] or "muestra"


class Biblioteca:
    def __init__(self, carpeta: str | None = None):
        self.carpeta = carpeta or os.path.join(carpeta_datos(), "biblioteca")
        self.indice = os.path.join(self.carpeta, "biblioteca.json")
        self.muestras: dict[str, Muestra] = {}
        self._cargar()

    # ---------------------------------------------------------- persistencia
    def _cargar(self):
        if not os.path.exists(self.indice):
            return
        try:
            with open(self.indice, encoding="utf-8") as f:
                for d in json.load(f).get("muestras", []):
                    m = Muestra(**d)
                    if os.path.exists(self.ruta(m)):
                        self.muestras[m.id] = m
        except (OSError, ValueError, TypeError):
            # índice dañado: se conserva una copia y se empieza de nuevo
            try:
                os.replace(self.indice, self.indice + ".danado")
            except OSError:
                pass

    def guardar(self):
        os.makedirs(self.carpeta, exist_ok=True)
        tmp = self.indice + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "muestras": [asdict(m) for m in self.muestras.values()]}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.indice)

    def ruta(self, m: Muestra) -> str:
        return os.path.join(self.carpeta, m.archivo)

    # ---------------------------------------------------------- añadir
    def agregar_audio(self, x: np.ndarray, nombre: str, tipo: str, origen: str = "",
                      etiquetas: list[str] | None = None, sr: int = SR, guardar: bool = True) -> tuple[Muestra, bool]:
        """Añade audio (frames × canales). Devuelve (muestra, es_nueva). No duplica audio idéntico."""
        import dsp
        x = np.asarray(x, dtype=np.float64)
        if x.ndim == 1:
            x = x[:, None]
        if sr != SR:
            x = dsp.to_rate(x, sr, SR)
        x = x[:, :2]
        h = hashlib.sha1(np.round(x, 5).astype(np.float32).tobytes()).hexdigest()[:16]
        if h in self.muestras:
            return self.muestras[h], False
        sub = os.path.join(self.carpeta, tipo)
        os.makedirs(sub, exist_ok=True)
        rel = f"{tipo}/{_seguro(nombre)}_{h[:6]}.wav"
        escribir_wav_float(os.path.join(self.carpeta, rel), x)
        m = Muestra(h, nombre[:40], tipo, rel, len(x) / SR, x.shape[1], origen, list(etiquetas or []), False, time.time())
        self.muestras[h] = m
        if guardar:
            self.guardar()
        return m, True

    def agregar_archivos(self, archivos: list, origen: str = "") -> int:
        """Añade objetos Archivo de importar_wav (ya leídos y clasificados)."""
        n = 0
        for a in archivos:
            if a.excluido or not len(a.x):
                continue
            nombre = os.path.splitext(a.nombre)[0]
            _, nueva = self.agregar_audio(a.x, nombre, a.tipo, origen or os.path.dirname(a.rel), guardar=False)
            n += nueva
        self.guardar()
        return n

    def agregar_carpeta(self, carpeta: str, log=lambda s: None) -> int:
        import importar_wav as I
        return self.agregar_archivos(I.escanear(carpeta, log), os.path.basename(carpeta.rstrip("\\/")))

    def agregar_pack(self, pack) -> int:
        """Guarda las muestras que usa un .ppf (con la pieza según su tecla)."""
        import importar_wav as I
        import mejora
        tipos = {"bombo": "kick", "caja": "snare", "tom": "tom", "hihat": "hh_closed", "ride": "ride", "crash": "crash", "perc": "perc"}
        por_nota = {}
        for t, (_n, notas_gm, _f) in I.PIEZAS.items():
            for n in notas_gm:
                por_nota.setdefault(n, t)
        uso: dict[str, list[int]] = {}
        for v in pack.voices:
            for el, kb, lo, hi, vlo, vhi in v.zones():
                for s in kb.samples:
                    uso.setdefault(s.wave_uid, []).append(lo)
        n = 0
        for uid, notas in uso.items():
            w = pack.waves.get(uid)
            if w is None:
                continue
            # primero por la tecla General MIDI; si no es estándar, por el nombre y el sonido
            t = next((por_nota[n] for n in sorted(notas) if n in por_nota and n < 60), None)
            if t is None:
                t, seguro = I.detectar_tipo(w.name, None, 0)
                if not seguro:
                    t = tipos[mejora.clasificar(w.name, notas, w)]
            _, nueva = self.agregar_audio(w.samples, w.name, t, pack.title, sr=int(w.rate), guardar=False)
            n += nueva
        self.guardar()
        return n

    # ---------------------------------------------------------- consultar / editar
    def buscar(self, texto: str = "", tipo: str | None = None, solo_fav: bool = False, etiqueta: str | None = None) -> list[Muestra]:
        t = texto.lower().strip()
        out = []
        for m in self.muestras.values():
            if tipo and m.tipo != tipo:
                continue
            if solo_fav and not m.fav:
                continue
            if etiqueta and etiqueta not in m.etiquetas:
                continue
            if t and not all(p in f"{m.nombre} {m.origen} {' '.join(m.etiquetas)} {m.tipo}".lower() for p in t.split()):
                continue
            out.append(m)
        return sorted(out, key=lambda m: (not m.fav, m.tipo, m.nombre.lower()))

    def etiquetas(self) -> list[str]:
        return sorted({e for m in self.muestras.values() for e in m.etiquetas})

    def editar(self, mid: str, **campos):
        m = self.muestras[mid]
        for k, v in campos.items():
            if k == "etiquetas":
                v = sorted({e.strip().lower() for e in v if e.strip()})
            setattr(m, k, v)
        self.guardar()

    def borrar(self, ids: list[str]) -> int:
        n = 0
        for mid in ids:
            m = self.muestras.pop(mid, None)
            if m is not None:
                try:
                    os.remove(self.ruta(m))
                except OSError:
                    pass
                n += 1
        self.guardar()
        return n

    def audio(self, m: Muestra) -> np.ndarray:
        import importar_wav as I
        x, sr = I.leer_wav(self.ruta(m))
        return x
