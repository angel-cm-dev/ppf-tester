"""Construye PPF Tester con PyInstaller.

Uso:  python build.py          (ejecutable)
      python build.py web      (copia el núcleo a la web app: docs/app/py)
Windows:  dist/PPF-Tester.exe  y  dist/PPF-Tester-vX.Y.Z-windows.zip
macOS:    dist/PPF Tester.app  y  dist/PPF-Tester-vX.Y.Z-macos.zip
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


# módulos del núcleo que usa la web app (Python en el navegador con Pyodide)
WEB_MODULOS = ["ppf_format", "sig", "dsp", "modelos", "sonido", "motor", "grooves", "estilos",
               "analisis", "compat", "importar_wav", "demo"]
WEB_PY = os.path.join(ROOT, "docs", "app", "py")


def web():
    os.makedirs(WEB_PY, exist_ok=True)
    for m in WEB_MODULOS:
        shutil.copyfile(os.path.join(SRC, m + ".py"), os.path.join(WEB_PY, m + ".py"))
    print(f"Web app: {len(WEB_MODULOS)} módulos copiados a {WEB_PY}")


def main():
    if "web" in sys.argv[1:]:
        web()
        return
    build = os.path.join(ROOT, "build")
    os.makedirs(build, exist_ok=True)
    vfile = os.path.join(build, "version_info.txt")
    with open(vfile, "w", encoding="utf-8") as f:
        f.write(VERSION_INFO)
    ico = os.path.join(SRC, "ppf_tester.ico")
    mac = sys.platform == "darwin"
    if mac:
        # .app (carpeta) con icono convertido por Pillow; la versión va en el Info.plist
        modo = ["--onedir", "--windowed", "--name", "PPF Tester", "--icon", ico,
                "--osx-bundle-identifier", "com.angelcm.ppftester"]
    else:
        modo = ["--onefile", "--windowed", "--name", "PPF-Tester", "--icon", ico, "--version-file", vfile]
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", *modo,
        "--add-data", f"{ico}{os.pathsep}.",
        "--hidden-import", "lameenc",
        *(["--hidden-import", "rtmidi"] if mac else []),
        "--add-data", f"{os.path.join(SRC, 'plantillas')}{os.pathsep}plantillas",
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
    if mac:
        app = os.path.join(ROOT, "dist", "PPF Tester.app")
        plist = os.path.join(app, "Contents", "Info.plist")
        if os.path.exists(plist):
            import plistlib
            with open(plist, "rb") as f:
                d = plistlib.load(f)
            d.update(CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION, NSHighResolutionCapable=True,
                     NSMicrophoneUsageDescription="PPF Tester graba la salida de tu teclado para compararla y calibrar la simulación.",
                     NSHumanReadableCopyright="MIT · Angel Cm · angelcm.com")
            with open(plist, "wb") as f:
                plistlib.dump(d, f)
            subprocess.call(["codesign", "--force", "--deep", "--sign", "-", app])
        zpath = os.path.join(ROOT, "dist", f"PPF-Tester-v{VERSION}-macos.zip")
        subprocess.check_call(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, zpath])
        print(f"\nListo:\n  {app}\n  {zpath} ({os.path.getsize(zpath) / 1e6:.1f} MB)")
        return
    exe = os.path.join(ROOT, "dist", "PPF-Tester.exe")
    zpath = os.path.join(ROOT, "dist", f"PPF-Tester-v{VERSION}-windows.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe, "PPF-Tester.exe")
        z.write(os.path.join(ROOT, "README.md"), "LEEME.md")
        z.write(os.path.join(ROOT, "LICENSE"), "LICENSE.txt")
        z.write(os.path.join(ROOT, "THIRD_PARTY.md"), "TERCEROS.md")
    print(f"\nListo:\n  {exe} ({os.path.getsize(exe) / 1e6:.1f} MB)\n  {zpath} ({os.path.getsize(zpath) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
