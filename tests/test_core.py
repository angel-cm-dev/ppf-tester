"""Pruebas automáticas de PPF Tester (formato .ppf, audio, importación y mejora).

Ejecutar:  python -m unittest discover -s tests -v
No necesitan muestras reales: crean un kit sintético con WAV generados.
"""
import os
import shutil
import struct
import sys
import tempfile
import unittest
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ppf_tester"))

import importar_wav as I  # noqa: E402
import mejora as Mj  # noqa: E402
import modelos  # noqa: E402
import ppf_format as P  # noqa: E402
import sig  # noqa: E402

SR = 44100


def _wav(path, x, sr=SR, bits=16):
    x = np.atleast_2d(x.T).T if x.ndim == 1 else x
    if x.ndim == 1:
        x = x[:, None]
    with wave.open(path, "wb") as f:
        f.setnchannels(x.shape[1])
        f.setsampwidth(bits // 8)
        f.setframerate(sr)
        if bits == 16:
            f.writeframes(np.clip(np.round(x * 32767), -32768, 32767).astype("<i2").tobytes())
        else:
            v = np.clip(np.round(x * 8388607), -8388608, 8388607).astype(np.int32)
            f.writeframes(np.stack([v & 255, (v >> 8) & 255, (v >> 16) & 255], -1).astype(np.uint8).tobytes())


def _golpe(f0, dur, ruido=0.0, decae=8.0, sr=SR, seed=0):
    t = np.arange(int(sr * dur)) / sr
    rng = np.random.default_rng(seed)
    y = np.sin(2 * np.pi * f0 * t) * (1 - ruido) + rng.standard_normal(len(t)) * ruido
    return (y * np.exp(-t * decae) * 0.8)[:, None]


class KitSintetico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="ppf_test_")
        d = cls.dir
        for sub in ("Kick", "Snare", "Toms/High Tom", "Toms/Floor Tom", "Cymbals/Hi Hat", "Cymbals/Crash", "Loops"):
            os.makedirs(os.path.join(d, sub), exist_ok=True)
        _wav(os.path.join(d, "Kick", "Kick_soft.wav"), _golpe(55, 0.5) * 0.4)
        _wav(os.path.join(d, "Kick", "Kick_hard.wav"), _golpe(55, 0.5), bits=24)
        _wav(os.path.join(d, "Snare", "SN_1.wav"), _golpe(200, 0.4, ruido=0.6, seed=1))
        _wav(os.path.join(d, "Snare", "SN_2.wav"), _golpe(205, 0.4, ruido=0.6, seed=2) * 0.7)
        _wav(os.path.join(d, "Toms", "High Tom", "HT_1.wav"), _golpe(180, 0.8, decae=5))
        _wav(os.path.join(d, "Toms", "Floor Tom", "FT_1.wav"), _golpe(90, 1.0, decae=4))
        _wav(os.path.join(d, "Cymbals", "Hi Hat", "HH_1.wav"), _golpe(8000, 0.15, ruido=0.95, decae=30, seed=3))
        st = np.hstack([_golpe(5000, 2.5, ruido=0.95, decae=1.5, seed=4), _golpe(5100, 2.5, ruido=0.95, decae=1.5, seed=5)])
        _wav(os.path.join(d, "Cymbals", "Crash", "Crash_1.wav"), st, sr=48000)
        _wav(os.path.join(d, "Loops", "Groove 100BPM.wav"), _golpe(60, 1.0))
        cls.archivos = I.escanear(d)
        cls.grupos = I.agrupar(cls.archivos)
        cls.piezas = I.auto_kit(cls.grupos)
        cls.op = I.OpcionesImport(nombre="Test Kit", modelo="PSR-S670")
        cls.plan = I.planificar(cls.piezas, cls.op)
        cls.ppf = os.path.join(d, "test.ppf")
        cls.pack = I.construir(cls.plan, cls.op, cls.ppf)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    # ------------------------------------------------------------ importación
    def test_detecta_piezas_y_excluye_loops(self):
        tipos = {g.tipo for g in self.grupos}
        self.assertTrue({"kick", "snare", "tom", "hh_closed", "crash"} <= tipos, tipos)
        self.assertTrue(any(a.excluido for a in self.archivos if "BPM" in a.nombre))

    def test_capas_por_nombre(self):
        kick = next(g for g in self.grupos if g.tipo == "kick")
        self.assertTrue(kick.capas_en_nombre)
        p = next(p for p in self.piezas if p.nota == 36)
        self.assertEqual(len(p.seleccion()), 2)

    def test_notas_gm(self):
        notas = {p.nota: p.tipo for p in self.piezas}
        self.assertEqual(notas.get(36), "kick")
        self.assertEqual(notas.get(38), "snare")
        self.assertEqual(notas.get(42), "hh_closed")
        self.assertEqual(notas.get(49), "crash")
        toms = sorted(n for n, t in notas.items() if t == "tom")
        self.assertIn(41, toms)
        self.assertIn(50, toms)

    def test_pack_valido_y_memoria(self):
        self.assertEqual(self.pack.errors, [])
        self.assertEqual(len(self.pack.voices), 1)
        self.assertLessEqual(self.plan.mb, modelos.MODELOS["PSR-S670"].kit_max_mb)
        zonas = list(self.pack.voices[0].zones())
        self.assertGreaterEqual(len(zonas), 8)
        for el, kb, lo, hi, vl, vh in zonas:
            for s in kb.samples:
                w = self.pack.waves[s.wave_uid]
                self.assertEqual(s.sample_size, w.frames + 4)
                self.assertEqual(s.loop_end, w.frames)

    # ------------------------------------------------------------ formato
    def test_ida_y_vuelta_identica(self):
        with open(self.ppf, "rb") as f:
            data = f.read()
        self.assertEqual(P.load_pack_bytes(data).to_bytes(), data)

    def test_mover_tecla_y_rangos(self):
        pack = P.load_pack(self.ppf)
        v = pack.voices[0]
        antes = {lo: kb.samples[0].wave_uid for el, kb, lo, hi, vl, vh in v.zones() if vh == 127}
        self.assertTrue(P.mover_tecla(pack, v, 36, 38))
        P.reparse_voices(pack)
        despues = {lo: kb.samples[0].wave_uid for el, kb, lo, hi, vl, vh in pack.voices[0].zones() if vh == 127}
        self.assertEqual(despues[38], antes[36])
        self.assertEqual(despues[36], antes[38])
        capas = P.capas_de(pack.voices[0], 38)
        self.assertEqual(len(capas), 2)
        self.assertTrue(P.fijar_rangos(pack, pack.voices[0], 38, [(1, 60), (61, 127)]))
        P.reparse_voices(pack)
        self.assertEqual([(lo, hi) for lo, hi, _ in P.capas_de(pack.voices[0], 38)], [(1, 60), (61, 127)])
        self.assertEqual(P.load_pack_bytes(pack.to_bytes()).errors, [])

    def test_variacion_humana(self):
        import dataclasses
        piezas = [dataclasses.replace(p) for p in self.piezas]
        sn = next(p for p in piezas if p.nota == 38)
        sn.variacion = 2
        plan = I.planificar(piezas, I.OpcionesImport(modelo="PSR-S975"))
        self.assertGreater(len(plan.capas[38]), 2)
        self.assertEqual(plan.capas[38][0][0], 1)
        self.assertEqual(plan.capas[38][-1][1], 127)

    # ------------------------------------------------------------ mejora
    def test_mejora_completa(self):
        pack = P.load_pack(self.ppf)
        filas, avisos, mb0, mb1 = Mj.mejorar(pack, Mj.OpcionesMejora(modelo="PSR-S775"))
        self.assertTrue(filas)
        out = P.load_pack_bytes(pack.to_bytes())
        self.assertEqual(out.errors, [])
        for w in out.waves.values():
            self.assertLessEqual(float(np.abs(w.samples).max()), 1.0)

    def test_referencia(self):
        import referencia
        filas = referencia.comparar(self.pack, self.pack)
        self.assertTrue(filas)
        for f in filas:
            self.assertEqual(f["consejos"], [])


class Audio(unittest.TestCase):
    def test_lfilter_un_polo(self):
        a = 0.9
        x = np.zeros(200)
        x[0] = 1
        y = sig.lfilter([1 - a], [1, -a], x)
        np.testing.assert_allclose(y, (1 - a) * a ** np.arange(200), atol=1e-9)

    def test_resample_longitud(self):
        x = np.random.default_rng(0).standard_normal((48000, 2))
        self.assertEqual(len(sig.resample(x, 48000, 44100)), 44100)

    def test_leer_wav_float(self):
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "f.wav")
            x = (np.sin(np.arange(1000) / 10) * 0.5).astype("<f4")
            fmt = struct.pack("<HHIIHH", 3, 1, SR, SR * 4, 4, 32)
            data = x.tobytes()
            with open(path, "wb") as f:
                f.write(b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(data)) + b"WAVE")
                f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data)
            y, sr = I.leer_wav(path)
            self.assertEqual(sr, SR)
            np.testing.assert_allclose(y[:, 0], x, atol=1e-6)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class Varios(unittest.TestCase):
    def test_idiomas(self):
        import idioma
        idioma.set_idioma("en")
        self.assertEqual(idioma.tr("  Escuchar"), "  Listen")
        self.assertEqual(idioma.tr("MUESTRAS"), "SAMPLES")
        idioma.set_idioma("pt")
        self.assertEqual(idioma.tr("Muestras"), "Amostras")
        idioma.set_idioma("es")
        self.assertEqual(idioma.tr("Muestras"), "Muestras")

    def test_ritmos(self):
        import grooves
        for nombre, (pasos, sub, notas) in grooves.PATRONES.items():
            self.assertTrue(all(0 <= st < pasos and 1 <= v <= 127 for st, n, v in notas), nombre)

    def test_modelos(self):
        self.assertEqual(modelos.MODELOS["PSR-S670"].memoria_mb, 32)
        estados = dict((n, e) for n, e, _ in modelos.compatibilidad(40))
        self.assertEqual(estados["PSR-S670"], "ERROR")
        self.assertEqual(estados["PSR-S975"], "OK")


if __name__ == "__main__":
    unittest.main()
