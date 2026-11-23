"""Pruebas de la versión 5: sonido, compatibilidad, biblioteca, set, voces melódicas, demos y MIDI."""
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ppf_tester"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import biblioteca  # noqa: E402
import compat  # noqa: E402
import conjunto  # noqa: E402
import demo  # noqa: E402
import importar_wav as I  # noqa: E402
import melodico as Mel  # noqa: E402
import midi_test  # noqa: E402
import motor  # noqa: E402
import ppf_format as P  # noqa: E402
import sonido  # noqa: E402
from test_core import SR, _golpe, _wav  # noqa: E402


def _tono(midi, dur=2.5, sr=SR, decae=1.0):
    f = 440 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(sr * dur)) / sr
    x = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.5 for k in range(1, 7)) * np.exp(-t * decae) * np.minimum(1, t / 0.01)
    return (x / np.abs(x).max() * 0.8)[:, None]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="ppf_v5_")
        d = cls.dir
        # kit multi-micrófono: el mismo golpe grabado con close / overheads / room
        for mic, g in (("Close", 1.0), ("OH", 0.5), ("Room", 0.3)):
            for pieza, f0 in (("Kick", 55), ("Snare", 200)):
                os.makedirs(os.path.join(d, "multi", pieza, mic), exist_ok=True)
                for k in (1, 2):
                    _wav(os.path.join(d, "multi", pieza, mic, f"{pieza}_{k}.wav"),
                         _golpe(f0, 0.5, ruido=0.3 if pieza == "Snare" else 0, seed=k) * g)
        # kit simple
        os.makedirs(os.path.join(d, "kit", "Kick"))
        os.makedirs(os.path.join(d, "kit", "Snare"))
        os.makedirs(os.path.join(d, "kit", "Crash"))
        _wav(os.path.join(d, "kit", "Kick", "Kick_1.wav"), _golpe(55, 0.5))
        _wav(os.path.join(d, "kit", "Snare", "Snare_1.wav"), _golpe(200, 0.4, ruido=0.6, seed=1))
        st = np.hstack([_golpe(5000, 1.5, ruido=0.95, decae=2, seed=4), -_golpe(5000, 1.5, ruido=0.95, decae=2, seed=4)])
        _wav(os.path.join(d, "kit", "Crash", "Crash_1.wav"), st)          # canal derecho invertido
        arch = I.escanear(os.path.join(d, "kit"))
        cls.op = I.OpcionesImport(nombre="V5 Kit", modelo="PSR-S970")
        cls.kit_path = os.path.join(d, "v5.ppf")
        cls.pack = I.construir(I.planificar(I.auto_kit(I.agrupar(arch)), cls.op), cls.op, cls.kit_path)
        # muestras de piano
        os.makedirs(os.path.join(d, "piano"))
        for nm, m in (("C2", 48), ("G2", 55), ("C3", 60), ("G3", 67), ("C4", 72)):
            _wav(os.path.join(d, "piano", f"Piano_{nm}.wav"), _tono(m))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)


class Sonido(Base):
    def test_mics_se_mezclan(self):
        arch = I.escanear(os.path.join(self.dir, "multi"))
        self.assertEqual({a.mic for a in arch}, {"close", "oh", "room"})
        self.assertTrue(sonido.hay_multimic(arch))
        mez = I.preparar_archivos(arch, 0.5)
        self.assertEqual(len(mez), 4)                   # 2 piezas × 2 golpes, cada uno con 3 micrófonos
        self.assertTrue(all(getattr(a, "componentes", None) for a in mez))
        seco = sonido.audio_archivo(mez[0], 0.0)
        amb = sonido.audio_archivo(mez[0], 1.0)
        self.assertGreater(np.abs(amb).sum(), np.abs(seco).sum())
        grupos = I.agrupar(mez)
        self.assertEqual(sorted(g.tipo for g in grupos), ["kick", "snare"])

    def test_sala_y_capa_suave(self):
        x = _golpe(200, 0.4, ruido=0.5)
        y = sonido.sala(x, SR, 0.6, 0.5)
        self.assertGreater(len(y), len(x))
        self.assertLessEqual(np.abs(y).max(), np.abs(x).max() + 1e-9)
        z = sonido.capa_suave(x, SR, "caja", 1.0)
        X, Z = np.abs(np.fft.rfft(x[:, 0])), np.abs(np.fft.rfft(z[:len(x), 0], len(x)))
        f = np.fft.rfftfreq(len(x), 1 / SR)
        brillo = lambda S: (f * S ** 2).sum() / (S ** 2).sum()  # noqa: E731
        self.assertLess(brillo(Z), brillo(X))

    def test_fase(self):
        x = _golpe(80, 0.4)
        self.assertTrue(sonido.fase(x, -x).invertido)
        l, r, msg = sonido.corregir_fase(x, -x)
        self.assertIsNone(sonido.fase(l, r).problema)
        self.assertTrue(msg)
        d = np.vstack([np.zeros((40, 1)), x[:-40]])
        self.assertIn("alineados", sonido.corregir_fase(x, d)[2])

    def test_nivel_referencia(self):
        x = _golpe(8000, 0.2, ruido=0.9, decae=30) * 0.99
        self.assertLess(sonido.ganancia_referencia(x, SR, "hihat"), 0)

    def test_import_corrige_fase(self):
        # el crash con un canal invertido entra en el kit (estéreo en S970) sin problema de fase
        import analisis as A
        r = A.analyze_voice(self.pack, self.pack.voices[0])
        self.assertFalse([p for p in r.problems if p.code == "fase"])
        # y la detección sí reconoce un par L/R invertido
        pk = P.load_pack(self.kit_path)
        pares = [kb for _, kb, *_ in pk.voices[0].zones() if len(kb.samples) == 2 and kb.samples[0].wave_uid != kb.samples[1].wave_uid]
        self.assertTrue(pares, "el crash debería estar en estéreo en el S970")
        l = pk.waves[pares[0].samples[0].wave_uid].samples
        self.assertEqual(sonido.fase(l, -l).problema is not None, True)


class Compat(Base):
    def test_revisar(self):
        res = compat.revisar(self.pack)
        self.assertEqual([r.modelo for r in res], ["PSR-S670", "PSR-S770", "PSR-S775", "PSR-S970", "PSR-S975"])
        self.assertTrue(all(r.estado in ("OK", "AVISO", "ERROR") for r in res))
        self.assertTrue(compat.PASOS_EM)


class Biblio(Base):
    def test_biblioteca(self):
        d = tempfile.mkdtemp()
        try:
            b = biblioteca.Biblioteca(d)
            n = b.agregar_carpeta(os.path.join(self.dir, "kit"))
            self.assertEqual(n, 3)
            self.assertEqual(b.agregar_carpeta(os.path.join(self.dir, "kit")), 0)     # sin duplicados
            self.assertEqual(len(b.buscar(tipo="kick")), 1)
            m = b.buscar("snare")[0]
            b.editar(m.id, fav=True, etiquetas=["Worship", " seco "])
            b2 = biblioteca.Biblioteca(d)                                          # persiste
            self.assertEqual(b2.buscar(solo_fav=True)[0].etiquetas, ["seco", "worship"])
            self.assertEqual(len(b2.buscar(etiqueta="seco")), 1)
            self.assertEqual(b2.audio(m).shape[1], 1)
            self.assertEqual(b2.borrar([m.id]), 1)
            self.assertEqual(len(biblioteca.Biblioteca(d).muestras), 2)
            self.assertGreaterEqual(b2.agregar_pack(self.pack), 0)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class SetYComparar(Base):
    def test_set(self):
        info = conjunto.info(self.kit_path)
        st = conjunto.estado_set([info] * 3, "PSR-S670")
        self.assertAlmostEqual(st.total_mb, info.mb * 3)
        self.assertEqual(st.estado, "OK")
        grande = conjunto.PackInfo("x", "Grande", 31.9, [], [], 0)
        self.assertEqual(conjunto.estado_set([info, grande], "PSR-S670").estado, "ERROR")
        self.assertEqual(conjunto.que_quitar([info, grande], "PSR-S670")[0].titulo, "Grande")

    def test_comparar(self):
        a = P.load_pack(self.kit_path)
        difs, tot = conjunto.comparar(a, a)
        self.assertEqual(tot["cambiadas"] + tot["nuevas"] + tot["quitadas"], 0)
        b = P.load_pack(self.kit_path)
        P.mover_tecla(b, b.voices[0], 36, 60)
        P.reparse_voices(b)
        difs, tot = conjunto.comparar(a, b)
        self.assertEqual(tot["nuevas"], 1)
        self.assertEqual(tot["quitadas"], 1)
        self.assertIn("cambiada", conjunto.informe_html(difs, tot, "a", "b", {"OK": "g", "ERROR": "r", "AVISO": "y", "mut": "m"})
                      or "nueva")


class Melodico(Base):
    def test_altura_y_nombres(self):
        for m in (40, 52, 60, 69, 81):
            self.assertAlmostEqual(Mel.hz_a_midi(Mel.altura(_tono(m))), m, delta=0.1)
        self.assertEqual(Mel.nota_en_nombre("Piano_C3.wav"), [60, 48])
        self.assertEqual(Mel.nota_en_nombre("pad A#2"), [58, 46])
        self.assertEqual(Mel.nota_en_nombre("str_060.wav"), [60])
        self.assertEqual(Mel.detectar_nota("Piano_C4.wav", _tono(60))[0], 60)    # el audio decide la octava

    def test_loop(self):
        x = _tono(57, 4.0, decae=0.05)
        lp = Mel.buscar_loop(x)
        self.assertIsNotNone(lp)
        self.assertGreater(lp.calidad, 0.95)
        y = Mel.aplicar_loop(x, lp)
        self.assertEqual(len(y), lp.fin)
        # la unión del loop no salta
        self.assertLess(abs(y[lp.fin - 1, 0] - y[lp.inicio - 1, 0]), 0.2)
        pad, lp2 = Mel.crear_pad(x, ataque_s=0.5)
        self.assertIsNotNone(lp2)
        self.assertLess(np.abs(pad[:100]).max(), 0.05)

    def _plantilla(self):
        """Voz «normal» de prueba: un kit con una muestra en la nota 0 y voiceType NORMAL."""
        a = I.escanear(os.path.join(self.dir, "kit", "Kick"))
        g = I.agrupar(a)
        op = I.OpcionesImport(nombre="Tpl")
        path = os.path.join(self.dir, "tpl.ppf")
        pk = I.construir(I.planificar([I.Pieza(0, "kick", g[0])], op), op, path)
        r = P.voice_resource(pk, pk.voices[0])
        r.set(b"FBIN", r.get(b"FBIN").replace(b"<voiceType>DRUM_KIT</voiceType>", b"<voiceType>NORMAL</voiceType>"))
        pk.save(path)
        return P.load_pack(path)

    def test_construir_voz(self):
        tpl = self._plantilla()
        self.assertIsNone(Mel.es_plantilla_valida(tpl))
        self.assertIsNotNone(Mel.es_plantilla_valida(self.pack))     # un drum kit no sirve
        ms = Mel.escanear(os.path.join(self.dir, "piano"), sostenido=True)
        self.assertEqual(sorted(m.nota for m in ms), [48, 55, 60, 67, 72])
        out = os.path.join(self.dir, "piano.ppf")
        pk = Mel.construir(tpl, ms, Mel.OpcionesVoz(nombre="Piano V5", sostenido=True), out)
        self.assertFalse(pk.errors)
        self.assertEqual(pk.title, "Piano V5")
        kbs = pk.voices[0].keybanks[pk.voices[0].elements[0].waveform]
        self.assertEqual(len(kbs), 5)
        self.assertEqual(sorted(k.center_note for k in kbs), [48, 55, 60, 67, 72])
        self.assertTrue(all(not k.fixed_pitch for k in kbs))
        self.assertEqual(min(k.note_lo for k in kbs), 0)
        self.assertEqual(max(k.note_hi for k in kbs), 127)
        # rangos contiguos
        r = sorted((k.note_lo, k.note_hi) for k in kbs)
        self.assertTrue(all(r[i][1] + 1 == r[i + 1][0] for i in range(len(r) - 1)))
        # el motor lo toca transportado
        e = motor.Engine(pk, pk.voices[0])
        buf, _ = e.render(62, 100)
        self.assertGreater(len(buf), 1000)
        f = Mel.hz_a_midi(Mel.altura(buf.astype(np.float64)))
        self.assertAlmostEqual(f, 62, delta=0.3)
        # vuelve a guardarse igual
        self.assertEqual(P.load_pack_bytes(pk.to_bytes()).to_bytes(), pk.to_bytes())


class Demos(Base):
    def test_demo(self):
        e = motor.Engine(self.pack, self.pack.voices[0])
        x = demo.demo_kit(e, ["Balada 4/4"], 90, 1)
        self.assertEqual(x.shape[1], 2)
        self.assertGreater(len(x), SR * 2)
        self.assertLessEqual(np.abs(x).max(), 10 ** (-1 / 20) + 1e-6)
        out = demo.guardar(os.path.join(self.dir, "demo.mp3"), x)
        self.assertTrue(os.path.getsize(out) > 1000)
        if demo.mp3_disponible():
            with open(out, "rb") as f:
                cab = f.read(3)
            self.assertTrue(cab == b"ID3" or cab[0] == 0xFF)


class Midi(unittest.TestCase):
    def test_despachar(self):
        on, off = [], []
        midi_test._despachar(0x99, 36, 100, lambda n, v: on.append((n, v)), lambda n: off.append(n))
        midi_test._despachar(0x89, 36, 0, lambda n, v: on.append((n, v)), lambda n: off.append(n))
        midi_test._despachar(0x99, 38, 0, lambda n, v: on.append((n, v)), lambda n: off.append(n))
        self.assertEqual(on, [(36, 100)])
        self.assertEqual(off, [36, 38])


if __name__ == "__main__":
    unittest.main()
