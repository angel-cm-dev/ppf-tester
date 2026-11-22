"""Construye PPF-Tester.exe (Windows) con PyInstaller y lo empaqueta en un .zip.

Uso:  python build.py
Resultado:  dist/PPF-Tester.exe  y  dist/PPF-Tester-vX.Y.Z-windows.zip
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "ppf_tester")
VERSION = re.search(r'__version__ = "([^"]+)"', open(os.path.join(SRC, "version.py"), encoding="utf-8").read()).group(1)
NUM = tuple(int(x) for x in (VERSION.split(".") + ["0"] * 4)[:4])

VERSION_INFO = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={NUM}, prodvers={NUM}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040a04b0', [
      StringStruct('CompanyName', 'Angel Cm'),
      StringStruct('FileDescription', 'PPF Tester - Sample Lab para Yamaha PSR-S'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'PPF-Tester'),
      StringStruct('LegalCopyright', 'MIT - Angel Cm - angelcm.com'),
      StringStruct('OriginalFilename', 'PPF-Tester.exe'),
      StringStruct('ProductName', 'PPF Tester'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [0x040a, 1200])])
  ]
)
"""


def main():
    build = os.path.join(ROOT, "build")
    os.makedirs(build, exist_ok=True)
    vfile = os.path.join(build, "version_info.txt")
    with open(vfile, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO)
    ico = os.path.join(SRC, "ppf_tester.ico")
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "PPF-Tester", "--icon", ico, "--version-file", vfile,
        "--add-data", f"{ico}{os.pathsep}.",
        "--paths", SRC,
        "--distpath", os.path.join(ROOT, "dist"), "--workpath", build, "--specpath", build,
        # módulos que no se usan (reduce tamaño)
        *[a for m in ("scipy", "matplotlib", "PIL", "pandas", "IPython", "pytest", "setuptools",
                      "xmlrpc", "lib2to3", "sqlite3", "curses", "tkinter",
                      "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore",
                      "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtTest",
                      "PySide6.QtOpenGL", "PySide6.QtSvg", "PySide6.QtDBus")
          for a in ("--exclude-module", m)],
        os.path.join(SRC, "qt_main.py"),
    ]
    print(" ".join(args))
    subprocess.check_call(args)
    exe = os.path.join(ROOT, "dist", "PPF-Tester.exe")
    zpath = os.path.join(ROOT, "dist", f"PPF-Tester-v{VERSION}-windows.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe, "PPF-Tester.exe")
        z.write(os.path.join(ROOT, "README.md"), "LEEME.md")
        z.write(os.path.join(ROOT, "LICENSE"), "LICENSE.txt")
    print(f"\nListo:\n  {exe} ({os.path.getsize(exe) / 1e6:.1f} MB)\n  {zpath} ({os.path.getsize(zpath) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
