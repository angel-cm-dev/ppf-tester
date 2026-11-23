"""Registro de errores y reporte de problemas."""
from __future__ import annotations

import logging
import os
import platform
import sys
import threading
import urllib.parse
from logging.handlers import RotatingFileHandler

if sys.platform == "darwin":
    CARPETA = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "PPFTester")
else:
    CARPETA = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "PPFTester")
ARCHIVO = os.path.join(CARPETA, "ppf_tester.log")
log = logging.getLogger("ppf_tester")


def iniciar(version: str):
    os.makedirs(CARPETA, exist_ok=True)
    if not log.handlers:
        h = RotatingFileHandler(ARCHIVO, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    log.info("PPF Tester %s · %s · Python %s", version, platform.platform(), platform.python_version())

    def hook(tipo, valor, tb):
        log.error("Error no controlado", exc_info=(tipo, valor, tb))
        sys.__excepthook__(tipo, valor, tb)

    sys.excepthook = hook

    def thook(args):
        log.error("Error en hilo %s", args.thread.name if args.thread else "?",
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = thook


def _anonimizar(texto: str) -> str:
    home = os.path.expanduser("~")
    t = texto.replace(home, "~").replace(home.replace("\\", "/"), "~")
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    return t.replace(user, "<usuario>") if len(user) > 2 else t


def ultimas_lineas(n: int = 40) -> str:
    try:
        with open(ARCHIVO, encoding="utf-8", errors="replace") as f:
            return _anonimizar("".join(f.readlines()[-n:]))
    except OSError:
        return "(sin registros)"


def url_reporte(repo: str, version: str) -> str:
    """Página de GitHub para abrir un reporte, con la información técnica ya escrita.
    El usuario la revisa en el navegador antes de enviarla."""
    cuerpo = (f"**Qué pasó:**\n\n(describe el problema)\n\n**Pasos para reproducirlo:**\n1. \n\n"
              f"---\nVersión: {version}\nSistema: {platform.platform()}\nPython: {platform.python_version()}\n\n"
              f"<details><summary>Últimas líneas del registro</summary>\n\n```\n{ultimas_lineas()[-5000:]}\n```\n</details>")
    q = urllib.parse.urlencode({"title": f"[v{version}] ", "body": cuerpo})
    return f"{repo}/issues/new?{q}"
