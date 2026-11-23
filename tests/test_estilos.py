"""Pruebas de los estilos Yamaha (.sty): lectura, reproducción tipo PSR-S y demo con el kit."""
import os
import struct
import sys
import time
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ppf_tester"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import demo  # noqa: E402
import estilos as E  # noqa: E402
import motor  # noqa: E402
from test_v5 import SR, Base  # noqa: E402

PPQ = 480
COMPAS = PPQ * 4


def _vlq(n):
    b = [n & 0x7F]
    n >>= 7
    while n:
        b.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(b)


def sty_sintetico(path, tempo=100):
    """Estilo mínimo como los de la serie S: SInt + Intro A, Main A/B, Fills, Break y Ending A."""
    ev = []   # (tick, bytes)
    ev.append((0, b"\xff\x51\x03" + int(60e6 / tempo).to_bytes(3, "big")))
    ev.append((0, b"\xff\x58\x04\x04\x02\x18\x08"))
    ev.append((0, b"\xff\x06\x04SFF2"))
    ev.append((0, b"\xff\x06\x04SInt"))
    ev.append((0, bytes([0xB8, 7, 64])))     # Rhythm 1 más bajo
    ev.append((0, bytes([0xB9, 7, 127])))    # Rhythm 2
    ev.append((0, bytes([0xBA, 7, 100])))    # bajo (no es batería)
    t = COMPAS
    secciones = [("Intro A", 2), ("Main A", 2), ("Main B", 2), ("Fill In AA", 1), ("Fill In BB", 1),
                 ("Fill In BA", 1), ("Ending A", 1)]
    for nombre, comp in secciones:
        ev.append((t, b"\xff\x06" + _vlq(len(nombre)) + nombre.encode()))
        for c in range(comp):
            for pulso in range(4):
                tp = t + c * COMPAS + pulso * PPQ
                ev.append((tp, bytes([0x99, 42, 80])))                      # hi-hat (canal 10)
                ev.append((tp + 60, bytes([0x99, 42, 0])))                  # note-off como vel 0
                ev.append((tp, bytes([0x99, 36 if pulso % 2 == 0 else 38, 110])))
                if nombre.startswith("Main B"):
                    ev.append((tp + PPQ // 2, bytes([0x98, 54, 90])))      # pandereta (canal 9)
                ev.append((tp, bytes([0x9A, 40, 100])))                     # bajo: se ignora
        t += comp * COMPAS
    ev.append((t, b"\xff\x2f\x00"))
    ev.sort(key=lambda e: e[0])
    trk, prev = b"", 0
    for tk, data in ev:
        trk += _vlq(tk - prev) + data
        prev = tk
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQ))
        f.write(b"MTrk" + struct.pack(">I", len(trk)) + trk)
        f.write(b"CASM" + struct.pack(">I", 4) + b"\0\0\0\0")   # bloque Yamaha que no se usa
    return path


class Estilos(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sty = sty_sintetico(os.path.join(cls.dir, "Prueba.S910.sty"))

    def test_leer(self):
        est = E.leer(self.sty)
        self.assertEqual(est.nombre, "Prueba")
        self.assertAlmostEqual(est.tempo, 100, delta=0.5)
        self.assertEqual(est.compas, (4, 4))
        self.assertEqual(est.ordenadas(), ["Intro A", "Main A", "Main B", "Fill In AA", "Fill In BB",
                                           "Fill In BA", "Ending A"])
        self.assertEqual(est.compases("Main A"), 2)
        self.assertEqual(est.compases("Fill In BB"), 1)
        notas = est.notas()
        self.assertNotIn(40, notas)            # el bajo no cuenta
        self.assertEqual(set(notas), {36, 38, 42, 54})
        self.assertEqual(notas[54], 8)
        self.assertLess(est.ganancia[8], est.ganancia[9])
        self.assertEqual(est.ganancia[9], 1.0)
        self.assertEqual(E.etiqueta("Fill In BA"), "Break")
        self.assertEqual(E.etiqueta("Fill In CC"), "Fill C")
        self.assertEqual(E.fill_de("Main D"), "Fill In DD")

    def test_no_es_estilo(self):
        p = os.path.join(self.dir, "malo.sty")
        with open(p, "wb") as f:
            f.write(b"RIFF....WAVE")
        with self.assertRaises(E.ErrorEstilo):
            E.leer(p)

    def test_faltantes(self):
        est = E.leer(self.sty)
        f = dict(E.faltantes(est, {36, 38, 42}))
        self.assertEqual(f, {54: 8})
        self.assertIn("Pandereta", E.resumen_faltantes(est, {36, 38, 42}))
        self.assertEqual(E.resumen_faltantes(est, {36, 38, 42, 54}), "")

    def test_reproductor_como_psr(self):
        est = E.leer(self.sty)
        golpes, secs = [], []
        r = E.Reproductor(est, lambda n, v, g: golpes.append((n, g)), {36, 38, 42}, lambda s: secs.append(s))
        r.bpm = 900   # rápido para la prueba
        r.start("Intro A")
        time.sleep(0.2)
        r.pedir("Main B")          # durante la Intro: solo elige qué Main sigue
        t = time.time()
        while "Main B" not in secs and time.time() - t < 5:
            time.sleep(0.01)
        r.pedir("Main B")          # pulsar el Main que suena = su Fill
        t = time.time()
        while "Fill In BB" not in secs and time.time() - t < 5:
            time.sleep(0.01)
        t = time.time()
        while secs[-1] != "Main B" and time.time() - t < 5:   # el Fill vuelve al Main
            time.sleep(0.01)
        r.pedir("Ending A")
        t = time.time()
        while r.actual is not None or r.sonando:
            if time.time() - t > 8:
                break
            time.sleep(0.02)
        r.stop()
        self.assertEqual(secs[0], "Intro A")
        self.assertIn("Main B", secs)
        self.assertNotIn("Main A", secs)
        i = secs.index("Fill In BB")
        self.assertEqual(secs[i + 1], "Main B")      # el Fill vuelve al Main
        self.assertEqual(secs[-2:], ["Ending A", None])
        self.assertNotIn(54, [n for n, _ in golpes])  # la pandereta no está en el kit
        self.assertTrue(golpes)

    def test_render_y_demo(self):
        est = E.leer(self.sty)
        self.assertEqual(E.secuencia_demo(est), ["Intro A", "Main A", "Main A", "Fill In BB", "Main B", "Main B", "Ending A"])
        e = motor.Engine(self.pack, self.pack.voices[0])
        x = demo.render_estilo(e, est, ["Main A"])
        self.assertEqual(x.shape[1], 2)
        self.assertGreater(np.abs(x).max(), 0.01)
        self.assertAlmostEqual(len(x) / SR, 2 * 4 * 60 / 100 + 2.5, delta=0.1)
        y = demo.demo_kit(e, [], recorrido=False, estilo=est)
        self.assertLessEqual(np.abs(y).max(), 10 ** (-1 / 20) + 1e-6)


if __name__ == "__main__":
    unittest.main()
