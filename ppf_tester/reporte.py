"""Informe HTML (se abre con cualquier navegador)."""
from __future__ import annotations

import html
import os
import time

import numpy as np

import analisis as A
from ppf_format import Pack, note_name

CSS = """
:root{--bg:#fafaf9;--fg:#1c1917;--mut:#78716c;--line:#e7e5e4;--card:#fff;--err:#b91c1c;--warn:#b45309;--info:#1d4ed8;--ok:#15803d;--wave:#44403c}
@media(prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#f5f5f4;--mut:#a8a29e;--line:#3a3532;--card:#262220;--err:#f87171;--warn:#fbbf24;--info:#93c5fd;--ok:#4ade80;--wave:#d6d3d1}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px 20px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:32px 0 12px}
.mut{color:var(--mut)}.stats{display:flex;gap:24px;flex-wrap:wrap;margin:16px 0}.stats div b{display:block;font-size:20px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}th{font-weight:600;color:var(--mut);font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin-bottom:12px}
.card h3{margin:0 0 6px;font-size:15px;display:flex;gap:8px;align-items:center}
.tag{font-size:11px;font-weight:600;padding:1px 6px;border-radius:4px;border:1px solid currentColor}
.ERROR{color:var(--err)}.AVISO{color:var(--warn)}.INFO{color:var(--info)}.OK{color:var(--ok)}
ul{margin:6px 0 0;padding-left:18px}li{margin:2px 0}svg{width:100%;height:64px;display:block;margin:6px 0}
.m{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--mut)}
"""


def _svg(x: np.ndarray, width: int = 1000, h: int = 64) -> str:
    mono = np.abs(x).max(axis=1) if x.ndim > 1 else np.abs(x)
    if not len(mono):
        return ""
    n = min(width, len(mono))
    edges = np.linspace(0, len(mono), n + 1).astype(int)
    peaks = np.array([mono[a:b].max() if b > a else 0 for a, b in zip(edges, edges[1:])])
    mid = h / 2
    pts_top = " ".join(f"{i},{mid - p * mid:.1f}" for i, p in enumerate(peaks))
    pts_bot = " ".join(f"{i},{mid + p * mid:.1f}" for i, p in reversed(list(enumerate(peaks))))
    return (f'<svg viewBox="0 0 {n} {h}" preserveAspectRatio="none"><polygon points="{pts_top} {pts_bot}" '
            f'fill="var(--wave)" opacity=".8"/><line x1="0" x2="{n}" y1="{mid}" y2="{mid}" stroke="var(--line)"/></svg>')


def _problems(ps: list[A.Problem]) -> str:
    if not ps:
        return '<p class="OK">Sin problemas detectados.</p>'
    return "<ul>" + "".join(f'<li><span class="{p.level}">{p.level}</span> {html.escape(p.text)}'
                            f'{" <span class=mut>(corregible)</span>" if p.fixable else ""}</li>' for p in ps) + "</ul>"


def write_report(path: str, pack: Pack, kits: list[A.KitReport], waves: list[A.WaveReport],
                 midi_problems: list[A.Problem] | None = None, midi_hits=None, extra_title: str = ""):
    by_uid = {w.uid: w for w in waves}
    nerr = sum(1 for w in waves for p in w.problems if p.level == "ERROR") + sum(1 for k in kits for p in k.problems if p.level == "ERROR")
    nwarn = sum(1 for w in waves for p in w.problems if p.level == "AVISO") + sum(1 for k in kits for p in k.problems if p.level == "AVISO")
    mem = A.memory_bytes(pack)
    o = [f"<!doctype html><html lang=es><meta charset=utf-8><title>Informe {html.escape(pack.title)}</title>"
         f"<meta name=viewport content='width=device-width,initial-scale=1'><style>{CSS}</style><main>",
         f"<h1>{html.escape(pack.title)} {html.escape(extra_title)}</h1>",
         f"<div class=mut>{html.escape(os.path.basename(pack.path))} · {time.strftime('%Y-%m-%d %H:%M')}</div>",
         "<div class=stats>",
         f"<div><b>{len(pack.voices)}</b><span class=mut>voces</span></div>",
         f"<div><b>{len(pack.waves)}</b><span class=mut>muestras</span></div>",
         f"<div><b>{mem / 1e6:.2f} MB</b><span class=mut>audio (16 bit)</span></div>",
         f"<div><b class=ERROR>{nerr}</b><span class=mut>errores</span></div>",
         f"<div><b class=AVISO>{nwarn}</b><span class=mut>avisos</span></div></div>"]
    if pack.errors:
        o.append("<h2>Errores de lectura</h2>" + _problems([A.Problem("ERROR", "lectura", e) for e in pack.errors]))
    for k in kits:
        o.append(f"<h2>Voz: {html.escape(k.voice)} <span class=mut>({html.escape(k.voice_type)})</span></h2>")
        o.append("<table><tr><th>Tecla</th><th>MIDI</th><th>Velocidad</th><th>Muestra</th><th>Duración</th><th>Pico</th><th>Estado</th></tr>")
        for z in k.zones:
            w = by_uid.get(z["uid"])
            key = note_name(z["note_lo"]) if z["note_lo"] == z["note_hi"] else f"{note_name(z['note_lo'])}–{note_name(z['note_hi'])}"
            st = w.worst if w else "ERROR"
            o.append(f"<tr><td>{key}</td><td>{z['note_lo']}</td><td>{z['vel_lo']}–{z['vel_hi']}</td>"
                     f"<td>{html.escape(', '.join(sorted(set(z['samples']))))}{' <span class=mut>(estéreo falso)</span>' if z['fake_stereo'] else ''}</td>"
                     f"<td>{w.duration:.2f} s</td><td>{w.peak_db:.1f} dB</td><td class={st}>{st}</td></tr>" if w else
                     f"<tr><td>{key}</td><td>{z['note_lo']}</td><td></td><td>falta</td><td></td><td></td><td class=ERROR>ERROR</td></tr>")
        o.append("</table><h2>Revisión del kit</h2>" + _problems(k.problems))
    if midi_problems is not None:
        o.append("<h2>Prueba en el teclado</h2>" + _problems(midi_problems))
        if midi_hits:
            o.append("<table><tr><th>Tecla</th><th>Vel</th><th>Muestra</th><th>Pico grabado</th><th>Retardo</th></tr>")
            for h in midi_hits:
                lat = f"{h.latency_ms:.0f} ms" if h.latency_ms is not None else "<span class=ERROR>sin sonido</span>"
                o.append(f"<tr><td>{note_name(h.note)}</td><td>{h.vel}</td><td>{html.escape(h.name)}</td><td>{h.peak_db:.1f} dB</td><td>{lat}</td></tr>")
            o.append("</table>")
    o.append("<h2>Muestras</h2>")
    for r in sorted(waves, key=lambda r: ("ERROR", "AVISO", "OK").index(r.worst)):
        w = pack.waves.get(r.uid)
        o.append(f"<div class=card><h3>{html.escape(r.name)} <span class='tag {r.worst}'>{r.worst}</span></h3>")
        if w is not None:
            o.append(_svg(w.samples))
        o.append(f"<div class=m><span>{r.duration:.2f} s</span><span>{'estéreo' if r.channels > 1 else 'mono'}</span>"
                 f"<span>{r.rate:.0f} Hz</span><span>pico {r.peak_db:.1f} dBFS</span><span>RMS {r.rms_db:.1f} dBFS</span>"
                 f"<span>DC {r.dc_pct:+.2f} %</span><span>silencio inicial {r.lead_silence_ms:.0f} ms</span>"
                 f"<span>silencio final {r.tail_silence_ms:.0f} ms</span></div>")
        o.append(_problems(r.problems) + "</div>")
    o.append('<p class=mut style="margin-top:40px;text-align:center">PPF Tester · Desarrollado por '
             '<a href="https://angelcm.com" style="color:#f4b860">Angel Cm</a> · angelcm.com</p>')
    o.append("</main></html>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(o))
