"""Pruebas de la web app (docs/app): el núcleo copiado está al día y el puente Python funciona."""
import filecmp
import json
import os
import sys
import unittest

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(RAIZ, "docs", "app")
sys.path.insert(0, os.path.join(RAIZ, "ppf_tester"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WEB, "py"))

import build  # noqa: E402
from test_estilos import sty_sintetico  # noqa: E402
from test_v5 import Base  # noqa: E402


class Sincronia(unittest.TestCase):
    def test_nucleo_al_dia(self):
        """Si falla: ejecuta «python build.py web» para copiar los cambios a la web app."""
        for m in build.WEB_MODULOS:
            a = os.path.join(RAIZ, "ppf_tester", m + ".py")
            b = os.path.join(WEB, "py", m + ".py")
            self.assertTrue(os.path.exists(b), b)
            self.assertTrue(filecmp.cmp(a, b, shallow=False), f"{m}.py desactualizado en docs/app/py")

    def test_listas_de_modulos(self):
        """El worker y el service worker cargan los mismos módulos."""
        mods = build.WEB_MODULOS + ["web_api"]
        for f in ("worker.js", "sw.js"):
            with open(os.path.join(WEB, f), encoding="utf-8") as fh:
                txt = fh.read()
            for m in mods:
                self.assertIn(f'"{m}"', txt, f"{m} falta en {f}")


class Puente(Base):
    def test_flujo_completo(self):
        import web_api as W
        with open(self.kit_path, "rb") as f:
            info = json.loads(W.abrir_kit(f.read(), "v5.ppf"))
        self.assertTrue(info["notas"])
        plan = json.loads(W.plan_banco())
        self.assertEqual({p["nota"] for p in plan}, {n["nota"] for n in info["notas"]})
        for p in plan:
            self.assertEqual(len(p["db"]), 128)
            self.assertEqual(p["capas"][0][0], 1)
            self.assertEqual(p["capas"][-1][1], 127)
        pedidos = [[p["nota"], c[2]] for p in plan for c in p["capas"]]
        meta, data = W.render_lote(json.dumps(pedidos))
        meta = json.loads(meta)
        x = np.frombuffer(data, np.float32)
        self.assertEqual(len(meta), len(pedidos))
        n, v, ini, frames, g = meta[-1]
        self.assertEqual(len(x), ini + frames * 2)
        self.assertGreater(np.abs(x).max(), 0.01)

        rev = json.loads(W.revisar())
        self.assertEqual(len(rev["compat"]), 5)
        self.assertIn("Balada 4/4", json.loads(W.ritmos()))

        p = sty_sintetico(os.path.join(self.dir, "web.sty"))
        with open(p, "rb") as f:
            est = json.loads(W.abrir_estilo(f.read(), "web.sty"))
        self.assertIn("Main A", est["secciones"])
        self.assertEqual(est["secciones"]["Fill In BA"]["etiqueta"], "Break")
        self.assertIsNotNone(est["faltan"])

        wav = W.crear_demo(json.dumps({"recorrido": False, "ritmos": ["Balada 4/4"], "compases": 1, "estilo": True}))
        self.assertEqual(wav[:4], b"RIFF")
        self.assertGreater(len(wav), 44 + 44100 * 4)


if __name__ == "__main__":
    unittest.main()
