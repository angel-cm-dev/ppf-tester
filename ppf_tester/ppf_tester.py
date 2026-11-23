"""PPF Tester - prueba y mejora de packs de Yamaha Expansion Manager (.ppf)
pensado para PSR-S670 y teclados compatibles.

Uso rápido:
    python ppf_tester.py analizar  MI_PACK.ppf
    python ppf_tester.py corregir  MI_PACK.ppf
    python ppf_tester.py extraer   MI_PACK.ppf
    python ppf_tester.py puertos
    python ppf_tester.py teclado   MI_PACK.ppf --grabar

Escribe  python ppf_tester.py <comando> -h  para ver todas las opciones.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import wave as wavelib
import webbrowser

import numpy as np

import analisis as A
import correccion as C
import reporte as R
from ppf_format import load_pack, note_name, parse_note

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:  # noqa: BLE001
        pass
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

COLORS = {"ERROR": "\033[91m", "AVISO": "\033[93m", "INFO": "\033[94m", "OK": "\033[92m"}
RST = "\033[0m"


def c(level: str, text: str) -> str:
    return f"{COLORS.get(level, '')}{text}{RST}" if sys.stdout.isatty() else text


def one_shot_map(pack):
    m = {}
    for v in pack.voices:
        for kbs in v.keybanks.values():
            for kb in kbs:
                for s in kb.samples:
                    m[s.wave_uid] = m.get(s.wave_uid, True) and kb.one_shot
    return m


def full_analysis(pack):
    os_map = one_shot_map(pack)
    waves = [A.analyze_wave(w, os_map.get(uid, True)) for uid, w in pack.waves.items()]
    kits = [A.analyze_voice(pack, v) for v in pack.voices]
    return kits, waves


def print_summary(pack, kits, waves, verbose=True):
    print(f"\n=== {pack.title} ===  ({os.path.basename(pack.path)})")
    print(f"{len(pack.voices)} voz/voces · {len(pack.waves)} muestras · {A.memory_bytes(pack) / 1e6:.2f} MB de audio")
    for e in pack.errors:
        print(c("ERROR", f"[ERROR] {e}"))
    by_uid = {w.uid: w for w in waves}
    for k in kits:
        print(f"\n-- Voz '{k.voice}' ({k.voice_type}) --")
        print(f"  {'Tecla':<9}{'Vel':<9}{'Muestra':<22}{'Dur':>6}{'Pico':>8}  Estado")
        for z in k.zones:
            w = by_uid.get(z["uid"])
            key = note_name(z["note_lo"]) if z["note_lo"] == z["note_hi"] else f"{note_name(z['note_lo'])}-{note_name(z['note_hi'])}"
            st = w.worst if w else "ERROR"
            name = ", ".join(sorted(set(z["samples"]))) or "(falta)"
            dur = f"{w.duration:5.2f}s" if w else ""
            pk = f"{w.peak_db:6.1f}dB" if w else ""
            print(f"  {key:<9}{z['vel_lo']:>3}-{z['vel_hi']:<5}{name[:21]:<22}{dur:>6}{pk:>8}  {c(st, st)}")
        for p in k.problems:
            print("  " + c(p.level, f"[{p.level}]") + " " + p.text)
    if verbose:
        print("\n-- Muestras --")
        for r in waves:
            if not r.problems:
                continue
            print(f"  {r.name}:")
            for p in r.problems:
                print("    " + c(p.level, f"[{p.level}]") + " " + p.text + (" (corregible)" if p.fixable else ""))


def default_out(path: str, suffix: str) -> str:
    base, _ = os.path.splitext(path)
    return base + suffix


# ------------------------------------------------------------ comandos
def cmd_analizar(a):
    pack = load_pack(a.archivo)
    kits, waves = full_analysis(pack)
    print_summary(pack, kits, waves, verbose=not a.breve)
    out = a.informe or default_out(a.archivo, "_informe.html")
    R.write_report(out, pack, kits, waves)
    print(f"\nInforme: {out}")
    if a.abrir:
        webbrowser.open("file:///" + os.path.abspath(out).replace("\\", "/"))


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "muestra"


def cmd_extraer(a):
    pack = load_pack(a.archivo)
    folder = a.carpeta or default_out(a.archivo, "_wav")
    os.makedirs(folder, exist_ok=True)
    for w in pack.waves.values():
        path = os.path.join(folder, _safe(w.name) + ".wav")
        pcm = np.clip(np.round(w.samples * 32768), -32768, 32767).astype("<i2")
        with wavelib.open(path, "wb") as f:
            f.setnchannels(w.channels)
            f.setsampwidth(2)
            f.setframerate(int(w.rate))
            f.writeframes(pcm.tobytes())
        print(f"  {path}")
    print(f"{len(pack.waves)} muestras extraídas en {folder}")


def cmd_corregir(a):
    pack = load_pack(a.archivo)
    kits0, waves0 = full_analysis(pack)
    mem0 = A.memory_bytes(pack)
    op = C.Opciones(quitar_dc=not a.sin_dc, fade_inicio=not a.sin_fades, fade_final=not a.sin_fades,
                    recortar_final=not a.sin_recorte, recortar_inicio=a.recortar_inicio,
                    normalizar_db=a.normalizar, agrupar_hihat=a.agrupar_hihat)
    log = C.corregir(pack, op)
    if not log:
        print("No hay nada que corregir con las opciones elegidas.")
        return
    out = a.salida or default_out(a.archivo, "_corregido.ppf")
    if os.path.abspath(out) == os.path.abspath(a.archivo):
        sys.exit("Por seguridad no se sobreescribe el archivo original. Elige otro nombre con --salida.")
    pack.save(out)
    # verificacion: volver a leer lo guardado
    check = load_pack(out)
    if check.errors:
        for e in check.errors:
            print(c("ERROR", e))
        sys.exit("El archivo corregido no pasó la verificación; no lo uses.")
    kits1, waves1 = full_analysis(check)
    print(f"\nCorrecciones en '{pack.title}':")
    for name, done in log:
        print(f"  {name}: " + "; ".join(done))
    cnt = lambda ws, ks, lv: sum(p.level == lv for w in ws for p in w.problems) + sum(p.level == lv for k in ks for p in k.problems)
    print(f"\nAntes:   {cnt(waves0, kits0, 'ERROR')} errores, {cnt(waves0, kits0, 'AVISO')} avisos, {mem0 / 1e6:.2f} MB")
    print(f"Después: {cnt(waves1, kits1, 'ERROR')} errores, {cnt(waves1, kits1, 'AVISO')} avisos, {A.memory_bytes(check) / 1e6:.2f} MB")
    print(f"\nGuardado: {out}  (el original no se modificó)")
    rep = default_out(out, "_informe.html")
    R.write_report(rep, check, kits1, waves1, extra_title="(corregido)")
    print(f"Informe:  {rep}")
    print("Ábrelo en Yamaha Expansion Manager, escúchalo y luego exporta el archivo de instalación para tu teclado.")


def cmd_mejorar(a):
    import mejora as Mj
    import modelos
    pack = load_pack(a.archivo)
    modelo = a.modelo if a.modelo.startswith("PSR-") else "PSR-" + a.modelo.upper()
    if modelo not in modelos.MODELOS:
        sys.exit("Modelo desconocido. Usa: " + ", ".join(modelos.MODELOS))
    op = Mj.OpcionesMejora(modelo=modelo, intensidad=a.intensidad / 100, capas=a.capas,
                           abrir_filtro=not a.sin_filtro)
    filas, avisos, mb0, mb1 = Mj.mejorar(pack, op, log=print)
    out = a.salida or default_out(a.archivo, f"_PRO_{modelo[4:]}.ppf")
    if os.path.abspath(out) == os.path.abspath(a.archivo):
        sys.exit("Por seguridad no se sobreescribe el archivo original.")
    pack.save(out)
    chk = load_pack(out)
    if chk.errors:
        sys.exit("El archivo mejorado no pasó la verificación.")
    print()
    for f in filas:
        print(f"  {f.nombre:<18} {Mj.NOMBRE_TIPO[f.tipo]:<12} " + " · ".join(f.cambios))
    for x in avisos:
        print("  " + c("INFO", "[INFO]") + " " + x)
    print(f"\nAudio: {mb0:.2f} → {mb1:.2f} MB")
    for nombre, est, txt in modelos.compatibilidad(mb1):
        print(f"  {c(est, est):<6} {nombre}: {txt}")
    print(f"\nGuardado: {out}")


def cmd_importar(a):
    import importar_wav as I
    import modelos
    modelo = a.modelo if a.modelo.startswith("PSR-") else "PSR-" + a.modelo.upper()
    if modelo not in modelos.MODELOS:
        sys.exit("Modelo desconocido. Usa: " + ", ".join(modelos.MODELOS))
    carpeta = a.carpeta.rstrip("\\/")
    nombre = a.nombre or os.path.basename(carpeta)[:20]
    out = a.salida or os.path.join(os.path.dirname(carpeta), f"{nombre}_{modelo[4:]}.ppf")
    op = I.OpcionesImport(nombre=nombre, modelo=modelo, procesar=not a.sin_procesar, intensidad=a.intensidad / 100,
                          ambiente=a.ambiente / 100, sala=a.sala / 100, nivel_teclado=not a.sin_nivel)
    archivos, grupos, plan, pack = I.crear_kit(carpeta, out, op, log=lambda s: None)
    print(f"{len(archivos)} WAV · {sum(1 for x in archivos if x.excluido)} ignorados · {len(grupos)} grupos")
    for p in sorted(plan.piezas, key=lambda p: p.nota):
        if p.usar:
            extra = f" afin={p.afinacion:+d}" if p.afinacion else ""
            print(f"  {I.nombre_tecla(p.nota):<26} {p.nombre:<20} capas={len(plan.capas[p.nota])}{extra}")
    if plan.pasos:
        print("Ajustes de memoria: " + ", ".join(plan.pasos))
    if pack.errors:
        sys.exit("El archivo creado no pasó la verificación: " + "; ".join(pack.errors))
    print(f"\nKit: {out}  ({plan.mb:.2f} MB para {modelo})")


def cmd_mejorar_carpeta(a):
    import mejora as Mj
    import modelos
    modelo = a.modelo if a.modelo.startswith("PSR-") else "PSR-" + a.modelo.upper()
    if modelo not in modelos.MODELOS:
        sys.exit("Modelo desconocido. Usa: " + ", ".join(modelos.MODELOS))
    base = dict(Mj.PLANTILLAS.get(a.plantilla, {})) if a.plantilla else {}
    base["modelo"] = modelo
    op = Mj.OpcionesMejora(**base)
    salida = a.salida or os.path.join(a.carpeta, "mejorados")
    for f, r in Mj.mejorar_carpeta(a.carpeta, salida, op, log=print):
        print(f"  {f}: {r}")
    print(f"\nGuardados en: {salida}")


def cmd_compat(a):
    import compat
    pack = load_pack(a.archivo)
    for r in compat.revisar(pack):
        print(f"{r.modelo:<10} {r.resumen}")
        for d in r.detalles:
            print(f"    {d}")


def cmd_demo(a):
    import demo
    import motor
    pack = load_pack(a.archivo)
    if not pack.voices:
        sys.exit("El pack no tiene voces.")
    est = None
    if a.estilo:
        import estilos
        est = estilos.leer(a.estilo)
    defecto = [] if est else ["Worship 4/4 (toms)", "Balada 4/4"]
    ritmos = [r.strip() for r in a.ritmos.split(",") if r.strip()] if a.ritmos else defecto
    import grooves
    for r in ritmos:
        if r not in grooves.PATRONES:
            sys.exit(f"Ritmo desconocido: {r}. Usa: " + ", ".join(grooves.PATRONES))
    e = motor.Engine(pack, pack.voices[0])
    x = demo.demo_kit(e, ritmos, a.bpm, a.compases, not a.sin_recorrido, est)
    out = demo.guardar(a.salida or os.path.splitext(a.archivo)[0] + "_demo.mp3", x)
    print(f"Demo: {out} ({len(x) / motor.SR:.0f} s)")


def cmd_estilo(a):
    import estilos
    est = estilos.leer(a.estilo)
    num, den = est.compas
    print(f"{est.nombre}: {est.tempo:g} BPM, {num}/{den}, {len(est.secciones)} secciones")
    for s in est.ordenadas():
        sec = est.secciones[s]
        print(f"  {s:<12} {est.compases(s):>3} comp.  {len(sec.eventos):>5} golpes")
    if not a.kit:
        return
    import demo
    import motor
    pack = load_pack(a.kit)
    if not pack.voices:
        sys.exit("El pack no tiene voces.")
    disp = {n for _, _, lo, hi, _, _ in pack.voices[0].zones() for n in range(lo, hi + 1)}
    print(estilos.resumen_faltantes(est, disp, 12) or "El kit tiene todos los sonidos que usa el estilo.")
    if a.salida:
        sec = [x.strip() for x in a.secciones.split(",")] if a.secciones else None
        for x in sec or []:
            if x not in est.secciones:
                sys.exit(f"Sección desconocida: {x}. Usa: " + ", ".join(est.ordenadas()))
        e = motor.Engine(pack, pack.voices[0])
        x = demo._limitar(demo.render_estilo(e, est, sec, a.bpm))
        out = demo.guardar(a.salida, x)
        print(f"Audio: {out} ({len(x) / motor.SR:.0f} s)")


def cmd_voz(a):
    import melodico as Mel
    tpl = a.plantilla or Mel.ruta_plantilla()
    if not os.path.exists(tpl):
        sys.exit("Falta la plantilla: usa --plantilla con un .ppf de voz normal creado en Expansion Manager.")
    ms = Mel.escanear(a.entrada, sostenido=a.loop or a.pad)
    if a.pad:
        for m in ms:
            m.x, m.loop = Mel.crear_pad(m.x, ataque_s=a.ataque)
    if not ms:
        sys.exit("No encontré WAV válidos.")
    for m in sorted(ms, key=lambda m: m.nota):
        lp = f" loop {(m.loop.fin - m.loop.inicio) / 44100:.2f}s" if m.loop else ""
        print(f"  {note_name(m.nota):<5} {m.nombre:<28} ({m.como}){lp}")
    nombre = a.nombre or os.path.splitext(os.path.basename(a.entrada.rstrip("\\/")))[0][:20]
    out = a.salida or os.path.join(os.path.dirname(os.path.abspath(a.entrada)), f"{nombre}.ppf")
    pack = Mel.construir(load_pack(tpl), ms, Mel.OpcionesVoz(nombre=nombre, estereo=a.estereo, sostenido=a.loop or a.pad), out)
    if pack.errors:
        sys.exit("El archivo creado no pasó la verificación: " + "; ".join(pack.errors))
    print(f"\nVoz: {out}")


def cmd_puertos(a):
    import midi_test as M
    print("Salidas MIDI:")
    outs = M.midi_outputs()
    kb = M.find_keyboard_port()
    for i, n in enumerate(outs):
        print(f"  [{i}] {n}{'   <- teclado Yamaha' if i == kb else ''}")
    if kb is None:
        print("  (No veo el teclado. Conecta el PSR por USB TO HOST y verifica el driver 'Yamaha USB-MIDI'.)")
    try:
        import sounddevice as sd
        print("\nEntradas de audio (para grabar la salida del teclado):")
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                api = sd.query_hostapis(d["hostapi"])["name"]
                print(f"  [{i}] {d['name']}  ({api}, {d['max_input_channels']} canales)")
    except ImportError:
        print("\n(Para grabar audio instala:  pip install sounddevice)")


def _parse_notes(s: str | None):
    if not s:
        return None
    out = []
    for part in s.split(","):
        part = part.strip()
        if "-" in part[1:] and not re.fullmatch(r"[A-G]#?-\d+", part):
            lo, hi = part.split("-", 1) if not part.startswith("-") else (part, part)
            lo_n = int(lo) if lo.isdigit() else parse_note(lo)
            hi_n = int(hi) if hi.isdigit() else parse_note(hi)
            out += list(range(lo_n, hi_n + 1))
        else:
            out.append(int(part) if part.isdigit() else parse_note(part))
    return out


def cmd_teclado(a):
    import midi_test as M
    pack = load_pack(a.archivo)
    kits, waves = full_analysis(pack)
    if not kits:
        sys.exit("El archivo no contiene voces.")
    kit = kits[a.voz]
    port = a.puerto if a.puerto is not None else M.find_keyboard_port()
    if port is None:
        sys.exit("No encuentro el teclado por MIDI. Usa 'python ppf_tester.py puertos' y pasa --puerto N.")
    print(f"Puerto MIDI: [{port}] {M.midi_outputs()[port]} · canal {a.canal}")
    print(f"Antes de seguir: en el PSR selecciona la voz '{kit.voice}' (Expansion) en RIGHT 1, "
          f"y comprueba que esa parte recibe por el canal {a.canal}.")
    if a.grabar:
        print("Grabando la salida del teclado desde la entrada de audio " +
              (f"[{a.entrada}]" if a.entrada is not None else "predeterminada") + ".")
    if not a.si:
        input("Pulsa ENTER para empezar (Ctrl+C para cancelar)… ")
    vels = [int(v) for v in a.velocidades.split(",")]
    waves_by_name = {w.name: w for w in pack.waves.values()}
    hits, audio, sr = M.run_test(kit, waves_by_name, port, a.canal, vels, a.entrada, a.grabar,
                                 _parse_notes(a.notas), gap=a.pausa)
    probs = M.evaluate(hits) if a.grabar else None
    if a.grabar:
        folder = a.carpeta or default_out(a.archivo, "_grabacion")
        os.makedirs(folder, exist_ok=True)
        full = os.path.join(folder, "sesion_completa.wav")
        _write_wav(full, audio, sr)
        for h in hits:
            if h.audio is not None:
                _write_wav(os.path.join(folder, f"{h.note:03d}_{note_name(h.note).replace('#', 's')}_v{h.vel:03d}_{_safe(h.name)}.wav"),
                           h.audio, sr)
        print(f"\nGrabaciones en: {folder}")
        print("\nResultado de la prueba en el teclado:")
        if not probs:
            print("  " + c("OK", "Todas las notas sonaron y la dinámica es correcta."))
        for p in probs:
            print("  " + c(p.level, f"[{p.level}]") + " " + p.text)
        print(f"\n  {'Tecla':<6}{'Vel':>4}  {'Pico':>8}  {'Retardo':>8}  Muestra")
        for h in hits:
            lat = f"{h.latency_ms:6.0f}ms" if h.latency_ms is not None else c("ERROR", "  MUDO")
            print(f"  {note_name(h.note):<6}{h.vel:>4}  {h.peak_db:7.1f}dB  {lat:>8}  {h.name}")
    rep = a.informe or default_out(a.archivo, "_prueba_teclado.html")
    R.write_report(rep, pack, kits, waves, midi_problems=probs or [], midi_hits=hits if a.grabar else None,
                   extra_title="(prueba en teclado)")
    print(f"\nInforme: {rep}")


def _write_wav(path, x, sr):
    x = np.asarray(x)
    if x.ndim == 1:
        x = x[:, None]
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wavelib.open(path, "wb") as f:
        f.setnchannels(x.shape[1])
        f.setsampwidth(2)
        f.setframerate(int(sr))
        f.writeframes(pcm.tobytes())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ppf_tester", description="Prueba y mejora de packs .ppf de Yamaha (PSR-S670 y similares).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("analizar", help="Revisa el pack y genera un informe HTML.")
    s.add_argument("archivo")
    s.add_argument("--informe", help="Ruta del informe HTML")
    s.add_argument("--breve", action="store_true", help="No listar problemas de cada muestra en consola")
    s.add_argument("--abrir", action="store_true", help="Abrir el informe en el navegador")
    s.set_defaults(f=cmd_analizar)

    s = sub.add_parser("extraer", help="Exporta las muestras a WAV.")
    s.add_argument("archivo")
    s.add_argument("--carpeta")
    s.set_defaults(f=cmd_extraer)

    s = sub.add_parser("corregir", help="Crea un .ppf nuevo con las correcciones automáticas.")
    s.add_argument("archivo")
    s.add_argument("--salida", help="Archivo de salida (por defecto *_corregido.ppf)")
    s.add_argument("--recortar-inicio", action="store_true", help="Quitar el silencio inicial (golpe más inmediato)")
    s.add_argument("--normalizar", type=float, metavar="DB", help="Llevar el pico de cada muestra a DB dBFS (p.ej. -1). Cambia el balance del kit")
    s.add_argument("--agrupar-hihat", action="store_true", help="Hi-hat cerrado/pedal/abierto en el mismo Alternate Group")
    s.add_argument("--sin-dc", action="store_true", help="No quitar DC offset")
    s.add_argument("--sin-fades", action="store_true", help="No aplicar fades anti-clic")
    s.add_argument("--sin-recorte", action="store_true", help="No recortar el silencio final")
    s.set_defaults(f=cmd_corregir)

    s = sub.add_parser("mejorar", help="Mejora todo el kit para un modelo de la serie S.")
    s.add_argument("archivo")
    s.add_argument("--modelo", default="S670", help="S670, S770, S775, S970 o S975")
    s.add_argument("--intensidad", type=float, default=100, help="0-150 (%%)")
    s.add_argument("--capas", default="auto", choices=["auto", "0", "2", "3"])
    s.add_argument("--sin-filtro", action="store_true", help="No abrir el filtro paso-bajo de la voz")
    s.add_argument("--salida")
    s.set_defaults(f=cmd_mejorar)

    s = sub.add_parser("importar", help="Crea un kit .ppf desde una carpeta de WAV.")
    s.add_argument("carpeta")
    s.add_argument("--modelo", default="S670", help="S670, S770, S775, S970 o S975")
    s.add_argument("--nombre", help="Nombre del kit (máx. 20 caracteres)")
    s.add_argument("--intensidad", type=float, default=50, help="Mejora por pieza 0-150 (%%)")
    s.add_argument("--sin-procesar", action="store_true", help="No aplicar la mejora por pieza")
    s.add_argument("--ambiente", type=float, default=40, help="Kits multi-micrófono: overheads/sala 0-100 (%%)")
    s.add_argument("--sala", type=float, default=0, help="Sala integrada en las muestras 0-100 (%%)")
    s.add_argument("--sin-nivel", action="store_true", help="No ajustar el nivel de referencia por pieza")
    s.add_argument("--salida")
    s.set_defaults(f=cmd_importar)

    s = sub.add_parser("compat", help="Compatibilidad del pack con cada modelo de la serie S.")
    s.add_argument("archivo")
    s.set_defaults(f=cmd_compat)

    s = sub.add_parser("demo", help="Crea una demo del kit en MP3 (o WAV) para compartir.")
    s.add_argument("archivo")
    s.add_argument("--ritmos", help="Ritmos separados por comas (por defecto: Worship 4/4 (toms), Balada 4/4)")
    s.add_argument("--bpm", type=float, default=76)
    s.add_argument("--compases", type=int, default=4)
    s.add_argument("--sin-recorrido", action="store_true", help="No incluir el recorrido pieza por pieza")
    s.add_argument("--estilo", help="Incluir la batería de un estilo Yamaha (.sty) tocada con el kit")
    s.add_argument("--salida", help="Archivo .mp3 o .wav")
    s.set_defaults(f=cmd_demo)

    s = sub.add_parser("estilo", help="Secciones de un estilo .sty; con --kit, qué sonidos le faltan y audio del estilo con el kit.")
    s.add_argument("estilo", help="Archivo .sty")
    s.add_argument("--kit", help="Pack .ppf con el kit de batería")
    s.add_argument("--secciones", help="Secciones separadas por comas (por defecto: Intro, cada Main con su Fill y Ending)")
    s.add_argument("--bpm", type=float, help="Tempo (por defecto, el del estilo)")
    s.add_argument("--salida", help="Archivo .mp3 o .wav con el estilo tocado por el kit")
    s.set_defaults(f=cmd_estilo)

    s = sub.add_parser("voz", help="Crea una voz melódica o un pad desde WAV (necesita una plantilla de voz normal).")
    s.add_argument("entrada", help="Carpeta con una muestra por nota, o un WAV para --pad")
    s.add_argument("--plantilla", help="Un .ppf con una voz normal creada en Expansion Manager")
    s.add_argument("--nombre")
    s.add_argument("--loop", action="store_true", help="Sonido sostenido: crear loops")
    s.add_argument("--pad", action="store_true", help="Pad/ambiente desde un solo WAV")
    s.add_argument("--ataque", type=float, default=0.3, help="Entrada suave del pad en segundos")
    s.add_argument("--estereo", action="store_true")
    s.add_argument("--salida")
    s.set_defaults(f=cmd_voz)

    s = sub.add_parser("mejorar-carpeta", help="Mejora todos los .ppf de una carpeta.")
    s.add_argument("carpeta")
    s.add_argument("--modelo", default="S670", help="S670, S770, S775, S970 o S975")
    s.add_argument("--plantilla", help="Worship suave, Worship moderno, Rock potente, Natural (mínimo) o Solo limpieza")
    s.add_argument("--salida", help="Carpeta de salida (por defecto <carpeta>\\mejorados)")
    s.set_defaults(f=cmd_mejorar_carpeta)

    s = sub.add_parser("puertos", help="Lista puertos MIDI y entradas de audio.")
    s.set_defaults(f=cmd_puertos)

    s = sub.add_parser("teclado", help="Toca el pack en el teclado por MIDI (y opcionalmente graba).")
    s.add_argument("archivo")
    s.add_argument("--puerto", type=int, help="Número de salida MIDI (ver 'puertos')")
    s.add_argument("--canal", type=int, default=1, help="Canal MIDI (por defecto 1 = RIGHT 1)")
    s.add_argument("--voz", type=int, default=0, help="Índice de la voz dentro del pack")
    s.add_argument("--velocidades", default="40,80,127")
    s.add_argument("--notas", help="Solo estas notas, p.ej. 'C1,D1,36-40'")
    s.add_argument("--pausa", type=float, default=0.25, help="Segundos entre notas")
    s.add_argument("--grabar", action="store_true", help="Grabar la salida del teclado (requiere sounddevice)")
    s.add_argument("--entrada", type=int, help="Número de entrada de audio (ver 'puertos')")
    s.add_argument("--carpeta", help="Carpeta para las grabaciones")
    s.add_argument("--informe")
    s.add_argument("--si", action="store_true", help="No pedir confirmación")
    s.set_defaults(f=cmd_teclado)

    a = ap.parse_args(argv)
    try:
        a.f(a)
    except FileNotFoundError as e:
        sys.exit(f"No encuentro el archivo: {e.filename}")
    except (ValueError, RuntimeError) as e:
        sys.exit(f"Error: {e}")
    except KeyboardInterrupt:
        sys.exit("\nCancelado.")


if __name__ == "__main__":
    main()
