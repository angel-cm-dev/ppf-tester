"""PPF Tester - aplicación de escritorio.

Ejecutar:  pythonw app.py   (o doble clic en "PPF Tester.bat")
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import traceback
import webbrowser
from tkinter import filedialog, messagebox, ttk

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analisis as A          # noqa: E402
import correccion as C        # noqa: E402
import reporte as R           # noqa: E402
from ppf_format import load_pack, note_name  # noqa: E402
from ppf_tester import full_analysis, _write_wav, _safe  # noqa: E402

try:
    import sounddevice as sd
except Exception:  # noqa: BLE001
    sd = None

APP = "PPF Tester"
from version import __version__ as VERSION, AUTOR, WEB, REPO  # noqa: E402

# ---------------------------------------------------------------- tema
# Estilo "worship": negro profundo, blanco cálido y luz dorada/coral de escenario
T = dict(
    bg="#09090b", panel="#111114", panel2="#18181d", line="#24242b", fg="#f5f1ea", mut="#8d8996",
    accent="#f4b860", accent2="#ec6f7f", accent3="#8b6cff", accent_dim="#5c4422", accent_fg="#160f06",
    ERROR="#ff6b7d", AVISO="#f6cb6b", INFO="#8fb4ff", OK="#63d4a3",
    wave="#f4b860", wave2="#3a3a44", white_key="#f3efe8", black_key="#1c1c22",
)
FONT = "Segoe UI"
HFONT = "Segoe UI Light"
MONO = "Cascadia Mono" if sys.platform == "win32" else "Menlo"


def set_theme(root: tk.Tk):
    global FONT, HFONT
    import tkinter.font as tkfont
    fams = set(tkfont.families(root))
    if "Segoe UI Variable Text" in fams:
        FONT, HFONT = "Segoe UI Variable Text", "Segoe UI Variable Display Light"
    elif "Segoe UI Light" not in fams:
        HFONT = FONT
    root.configure(bg=T["bg"])
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=T["bg"], foreground=T["fg"], fieldbackground=T["panel2"],
                bordercolor=T["line"], lightcolor=T["line"], darkcolor=T["line"], troughcolor=T["panel"],
                font=(FONT, 10), focuscolor=T["accent"], selectbackground=T["accent_dim"], selectforeground=T["fg"])
    s.configure("TFrame", background=T["bg"])
    s.configure("Panel.TFrame", background=T["panel"])
    s.configure("TLabel", background=T["bg"], foreground=T["fg"])
    s.configure("Panel.TLabel", background=T["panel"])
    s.configure("Mut.TLabel", background=T["panel"], foreground=T["mut"], font=(FONT, 9))
    s.configure("H.TLabel", background=T["panel"], foreground=T["fg"], font=(FONT, 11, "bold"))
    s.configure("Big.TLabel", background=T["panel"], foreground=T["fg"], font=(FONT, 18, "bold"))
    s.configure("TButton", background=T["panel2"], foreground=T["fg"], padding=(14, 7), borderwidth=0, relief="flat")
    s.map("TButton", background=[("active", T["line"]), ("disabled", T["panel"])],
          foreground=[("disabled", T["mut"])])
    s.configure("Accent.TButton", background=T["accent"], foreground=T["accent_fg"], font=(FONT, 10, "bold"))
    s.map("Accent.TButton", background=[("active", "#ffcf85"), ("disabled", T["accent_dim"])])
    s.configure("Ghost.TButton", background=T["bg"], foreground=T["fg"], padding=(12, 7), borderwidth=0)
    s.map("Ghost.TButton", background=[("active", T["panel2"]), ("disabled", T["bg"])], foreground=[("disabled", "#55525c")])
    s.configure("TCheckbutton", background=T["panel"], foreground=T["fg"])
    s.configure("P2.TCheckbutton", background=T["panel2"], foreground=T["fg"])
    s.map("P2.TCheckbutton", background=[("active", T["panel2"])], indicatorcolor=[("selected", T["accent"]), ("!selected", T["panel"])])
    s.map("TCheckbutton", background=[("active", T["panel"])], indicatorcolor=[("selected", T["accent"]), ("!selected", T["panel2"])])
    s.configure("TCombobox", arrowcolor=T["fg"], background=T["panel2"], foreground=T["fg"], padding=4)
    s.map("TCombobox", fieldbackground=[("readonly", T["panel2"]), ("disabled", T["panel"])],
          foreground=[("readonly", T["fg"]), ("disabled", T["mut"])],
          selectbackground=[("readonly", T["panel2"])], selectforeground=[("readonly", T["fg"])],
          background=[("active", T["line"]), ("readonly", T["panel2"])])
    root.option_add("*TCombobox*Listbox.background", T["panel2"])
    root.option_add("*TCombobox*Listbox.foreground", T["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", T["accent_dim"])
    s.configure("TEntry", foreground=T["fg"], padding=4, insertcolor=T["fg"])
    s.configure("TSpinbox", foreground=T["fg"], arrowcolor=T["fg"], padding=4)
    s.configure("Treeview", background=T["panel"], fieldbackground=T["panel"], foreground=T["fg"],
                rowheight=28, borderwidth=0, font=(FONT, 10))
    s.map("Treeview", background=[("selected", T["accent_dim"])], foreground=[("selected", "#fff")])
    s.configure("Treeview.Heading", background=T["panel2"], foreground=T["mut"], relief="flat", font=(FONT, 9, "bold"), padding=4)
    s.map("Treeview.Heading", background=[("active", T["line"])])
    s.configure("TNotebook", background=T["bg"], borderwidth=0, tabmargins=0)
    s.configure("TNotebook.Tab", background=T["bg"], foreground=T["mut"], padding=(20, 10), borderwidth=0, font=(FONT, 9, "bold"))
    s.map("TNotebook.Tab", background=[("selected", T["panel"]), ("active", T["bg"])],
          foreground=[("selected", T["accent"]), ("active", T["fg"])])
    s.layout("TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [("Notebook.label", {"side": "top", "sticky": ""})]})]})])
    s.configure("Vertical.TScrollbar", background=T["panel2"], troughcolor=T["panel"], arrowcolor=T["mut"], borderwidth=0)


def text_widget(parent, h=8):
    t = tk.Text(parent, height=h, bg=T["panel"], fg=T["fg"], insertbackground=T["fg"], relief="flat",
                wrap="word", font=(FONT, 10), padx=10, pady=8, highlightthickness=0, borderwidth=0)
    for lv in ("ERROR", "AVISO", "INFO", "OK"):
        t.tag_configure(lv, foreground=T[lv], font=(FONT, 10, "bold"))
    t.tag_configure("mut", foreground=T["mut"])
    t.tag_configure("mono", font=(MONO, 9))
    t.configure(state="disabled")
    return t


def write_problems(t: tk.Text, probs, empty="Sin problemas detectados."):
    t.configure(state="normal")
    t.delete("1.0", "end")
    if not probs:
        t.insert("end", "✔  ", "OK")
        t.insert("end", empty)
    for p in probs:
        t.insert("end", f"{p.level:<6}", p.level)
        t.insert("end", "  " + p.text)
        if p.fixable:
            t.insert("end", "  · corregible", "mut")
        t.insert("end", "\n")
    t.configure(state="disabled")


# ------------------------------------------------------------ widgets
def _hex(c):
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], float)


def gradient_image(w: int, h: int) -> tk.PhotoImage:
    """Fondo con luces de escenario (dorado, coral y violeta) sobre negro."""
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    img = np.zeros((h, w, 3)) + _hex(T["bg"])
    for cx, cy, r, col, a in ((0.80, 0.0, 0.42, T["accent"], 0.55), (0.97, 1.1, 0.30, T["accent2"], 0.45),
                              (0.55, -0.4, 0.35, T["accent3"], 0.22)):
        d = np.sqrt(((xx - cx * w) / (r * w)) ** 2 + ((yy - cy * h) / (r * w * 0.55)) ** 2)
        k = np.clip(1 - d, 0, 1) ** 2 * a
        img = img * (1 - k[..., None]) + _hex(col) * k[..., None]
    img = np.clip(img, 0, 255).astype(np.uint8)
    ppm = f"P6 {w} {h} 255\n".encode() + img.tobytes()
    return tk.PhotoImage(data=ppm, format="PPM")


def draw_logo(c: tk.Canvas, x: float, y: float, r: float):
    """Logo: anillo de luz con ondas de sonido."""
    steps = 48
    a0, a1 = _hex(T["accent"]), _hex(T["accent2"])
    for i in range(steps):
        t = i / (steps - 1)
        col = "#%02x%02x%02x" % tuple((a0 * (1 - t) + a1 * t).astype(int))
        c.create_arc(x - r, y - r, x + r, y + r, start=90 - i * 360 / steps, extent=-360 / steps - 1,
                     style="arc", outline=col, width=max(2, r * 0.12))
    for i, hh in enumerate((0.35, 0.7, 1.0, 0.6, 0.3)):
        bx = x - r * 0.48 + i * r * 0.24
        c.create_line(bx, y - hh * r * 0.45, bx, y + hh * r * 0.45, fill=T["fg"], width=max(2, r * 0.1), capstyle="round")



class Waveform(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=T["panel"], highlightthickness=0, height=170, **kw)
        self.wave = None
        self.rep = None
        self.mode = "onda"
        self.bind("<Configure>", lambda e: self.redraw())

    def toggle(self):
        self.mode = "espectro" if self.mode == "onda" else "onda"
        self.redraw()
        return self.mode

    def _spectrum(self, w, h):
        import dsp
        db, f = dsp.spectrum_db(self.wave.samples, self.wave.rate, 120)
        lo, hi = np.log10(20), np.log10(20000)
        xs = (np.log10(f) - lo) / (hi - lo) * w
        ys = 14 + (np.clip(-db, 0, 72) / 72) * (h - 30)
        pts = [c for xy in zip(xs, ys) for c in xy]
        self.create_polygon(0, h - 16, *pts, w, h - 16, fill="#3a2b12", outline="")
        self.create_line(*pts, fill=T["wave"], width=2)
        for fr, lab in ((50, "50"), (100, "100"), (300, "300"), (1000, "1k"), (3000, "3k"), (7000, "7k"), (10000, "10k")):
            x = (np.log10(fr) - lo) / (hi - lo) * w
            self.create_line(x, 14, x, h - 16, fill=T["line"], dash=(2, 4))
            self.create_text(x, h - 7, text=lab, fill=T["mut"], font=(FONT, 8))
        self.create_text(8, 12, text=f"{self.wave.name} · espectro", fill=T["fg"], anchor="w", font=(FONT, 10, "bold"))

    def show(self, wave, rep):
        self.wave, self.rep = wave, rep
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        mid = h / 2
        self.create_line(0, mid, w, mid, fill=T["line"])
        if self.wave is None:
            self.create_text(w / 2, mid, text="Abre un archivo .ppf para empezar", fill=T["mut"], font=(FONT, 11))
            return
        if self.mode == "espectro":
            self._spectrum(w, h)
            return
        x = self.wave.samples
        mono = np.abs(x).max(axis=1)
        n = len(mono)
        if not n:
            return
        sr = self.wave.rate
        # zonas de silencio
        r = self.rep
        if r:
            lead = r.lead_silence_ms / 1000 * sr / n * w
            tail = r.tail_silence_ms / 1000 * sr / n * w
            if lead > 1:
                self.create_rectangle(0, 0, lead, h, fill="#2a2116", outline="")
            if tail > 1:
                self.create_rectangle(w - tail, 0, w, h, fill="#1d2331", outline="")
        edges = np.linspace(0, n, w + 1).astype(int)
        pk = np.maximum.reduceat(mono, edges[:-1]) if n >= w else np.interp(np.arange(w), np.linspace(0, w, n), mono)
        scale = (h / 2 - 8)
        top = [(i, mid - v * scale) for i, v in enumerate(pk)]
        bot = [(i, mid + v * scale) for i, v in reversed(list(enumerate(pk)))]
        self.create_polygon(*[c for p in top + bot for c in p], fill=T["wave"], outline="")
        # lineas de 0 dBFS y -6
        for lv, lab in ((1.0, "0 dB"), (0.5, "-6")):
            for yy in (mid - lv * scale, mid + lv * scale):
                self.create_line(0, yy, w, yy, fill=T["line"], dash=(2, 4))
            self.create_text(w - 6, mid - lv * scale - 7, text=lab, fill=T["mut"], anchor="e", font=(FONT, 8))
        self.create_text(8, 12, text=f"{self.wave.name}", fill=T["fg"], anchor="w", font=(FONT, 10, "bold"))
        self.create_text(8, h - 10, text=f"{self.wave.duration:.2f} s", fill=T["mut"], anchor="w", font=(FONT, 8))


class Piano(tk.Canvas):
    WHITE = [0, 2, 4, 5, 7, 9, 11]

    def __init__(self, parent, on_key, **kw):
        super().__init__(parent, bg=T["panel"], highlightthickness=0, height=96, **kw)
        self.on_key = on_key
        self.status: dict[int, str] = {}
        self.selected = None
        self.lo, self.hi = 36, 72
        self.rects = []
        self.labels: dict[int, str] = {}
        self.flashing: set[int] = set()
        self.last_frac = 0.7
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Button-1>", self._click)

    def set_keys(self, status: dict[int, str]):
        self.status = status
        if status:
            lo, hi = min(status), max(status)
            self.lo = max(0, (lo // 12) * 12)
            self.hi = min(127, ((hi // 12) + 1) * 12 - 1)
            if self.hi - self.lo < 35:
                self.hi = min(127, self.lo + 35)
        self.redraw()

    def redraw(self):
        self.delete("all")
        self.rects = []
        w, h = self.winfo_width(), self.winfo_height()
        whites = [n for n in range(self.lo, self.hi + 1) if n % 12 in self.WHITE]
        if not whites or w < 20:
            return
        kw = w / len(whites)
        pos = {}
        for i, n in enumerate(whites):
            x0 = i * kw
            pos[n] = x0
            col = self._col(n, T["white_key"])
            self.create_rectangle(x0 + 1, 0, x0 + kw - 1, h - 2, fill=col, outline=T["bg"])
            if n in self.labels:
                self.create_text(x0 + kw / 2, h - 28, text=self.labels[n], fill="#1a1205", font=(FONT, 9, "bold"))
            if n % 12 == 0:
                self.create_text(x0 + kw / 2, h - 12, text=note_name(n), fill="#55524c", font=(FONT, 7))
            self.rects.append((x0, x0 + kw, 0, h, n, False))
        for n in range(self.lo, self.hi + 1):
            if n % 12 in self.WHITE or n - 1 not in pos:
                continue
            x0 = pos[n - 1] + kw * 0.65
            col = self._col(n, T["black_key"])
            self.create_rectangle(x0, 0, x0 + kw * 0.7, h * 0.6, fill=col, outline=T["bg"])
            if n in self.labels:
                self.create_text(x0 + kw * 0.35, h * 0.6 - 12, text=self.labels[n], fill="#f5f5f4", font=(FONT, 8, "bold"))
            self.rects.insert(0, (x0, x0 + kw * 0.7, 0, h * 0.6, n, True))

    def flash(self, n):
        self.flashing.add(n)
        self.redraw()
        self.after(140, lambda: (self.flashing.discard(n), self.redraw()))

    def _col(self, n, base):
        if n in self.flashing:
            return "#fff4dc"
        if n == self.selected:
            return T["accent2"]
        st = self.status.get(n)
        if st is None:
            return base
        black = n % 12 not in self.WHITE
        if black:
            return {"OK": "#8a6530", "AVISO": "#8f3b47", "ERROR": "#9e2236"}.get(st, "#4b3a8f")
        return {"OK": "#e9b86e", "AVISO": "#ec6f7f", "ERROR": "#ff3d5e"}.get(st, "#8b6cff")

    def _click(self, e):
        for x0, x1, y0, y1, n, _ in self.rects:
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.last_frac = (e.y - y0) / max(1, y1 - y0)
                if n in self.status:
                    self.on_key(n)
                return


# ------------------------------------------------------------------ app
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP} — Laboratorio de samples Yamaha")
        self.geometry("1280x820")
        if sys.platform == "win32":
            try:
                self.state("zoomed")
            except tk.TclError:
                pass
        self.minsize(1020, 680)
        set_theme(self)
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ico = os.path.join(base, "ppf_tester.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except tk.TclError:
                pass
        self.pack_ = None
        self.kits = []
        self.waves = []
        self.rep_by_uid = {}
        self.zone_by_iid = {}
        self.q = queue.Queue()
        self._build()
        self.after(100, self._poll)
        self.bind_all("<KeyPress>", self._key_press, add="+")
        self.bind_all("<KeyRelease>", lambda e: self.listen.key_release(e), add="+")
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _key_press(self, e):
        if self.nb.select() != str(self.listen):
            return
        if isinstance(e.widget, (tk.Entry, ttk.Entry, ttk.Spinbox, ttk.Combobox, tk.Text)) and not isinstance(e.widget, tk.Text):
            return
        if self.listen.key_press(e):
            return "break"

    def _close(self):
        try:
            self.listen.close()
            if sd is not None:
                sd.stop()
        finally:
            self.destroy()

    # ---------- layout
    def _build(self):
        H = 86
        head = tk.Canvas(self, height=H, bg=T["bg"], highlightthickness=0)
        head.pack(fill="x")
        self._banner = gradient_image(2400, H)
        head.create_image(0, 0, image=self._banner, anchor="nw")
        draw_logo(head, 50, H / 2, 22)
        head.create_text(88, H / 2 - 10, text="PPF TESTER", fill=T["fg"], anchor="w", font=(HFONT, 22))
        head.create_text(90, H / 2 + 17, text="SAMPLE LAB  ·  YAMAHA PSR-S670 · S770 · S775 · S970 · S975",
                         fill="#bdb6c4", anchor="w", font=(FONT, 8, "bold"))
        btns = tk.Frame(head, bg=T["bg"])
        self._btn_win = head.create_window(0, H / 2, window=btns, anchor="e")
        head.bind("<Configure>", lambda e: head.coords(self._btn_win, e.width - 18, H / 2))
        self.b_open = ttk.Button(btns, text="Abrir .ppf", style="Accent.TButton", command=self.open_file)
        self.b_open.pack(side="left", padx=3)
        self.b_save = ttk.Button(btns, text="Guardar como", command=self.save_as, state="disabled")
        self.b_fix = ttk.Button(btns, text="Corregir", command=self.fix_dialog, state="disabled")
        self.b_wav = ttk.Button(btns, text="WAV", command=self.export_wav, state="disabled")
        self.b_rep = ttk.Button(btns, text="Informe", command=self.open_report, state="disabled")
        for b in (self.b_save, self.b_fix, self.b_wav, self.b_rep):
            b.pack(side="left", padx=3)
        ttk.Button(btns, text="ⓘ", width=3, command=self.about).pack(side="left", padx=(8, 0))

        # tarjetas de resumen
        self.summary = tk.Frame(self, bg=T["bg"])
        self.summary.pack(fill="x", padx=18, pady=(10, 8))
        self.stat_labels = {}
        for key, lab in (("title", "Pack"), ("voices", "Voces"), ("waves", "Muestras"), ("mem", "Audio"),
                         ("ERROR", "Errores"), ("AVISO", "Avisos")):
            f = tk.Frame(self.summary, bg=T["panel"], padx=14, pady=6)
            f.pack(side="left", padx=(0, 10), fill="y", expand=key == "title", anchor="w")
            tk.Label(f, text=lab.upper(), bg=T["panel"], fg=T["mut"], font=(FONT, 7, "bold")).pack(anchor="w")
            l = tk.Label(f, text="—", bg=T["panel"], fg=T.get(key, T["fg"]), font=(HFONT if key == "title" else FONT, 14 if key == "title" else 12, "normal" if key == "title" else "bold"))
            l.pack(anchor="w")
            self.stat_labels[key] = l

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=18, pady=(4, 0))
        self.nb = nb
        nb.add(self._tab_samples(nb), text="MUESTRAS")
        from escuchar import ListenTab
        self.listen = ListenTab(nb, self, T, FONT, Piano, text_widget)
        nb.add(self.listen, text="ESCUCHAR")
        from mejorar_tab import MejorarTab
        self.mejorar = MejorarTab(nb, self, T, FONT, text_widget)
        nb.add(self.mejorar, text="MEJORAR KIT")
        nb.add(self._tab_kit(nb), text="REVISIÓN")
        nb.add(self._tab_keyboard(nb), text="PRUEBA EN EL TECLADO")

        foot = tk.Frame(self, bg=T["bg"])
        foot.pack(side="bottom", fill="x", padx=18, pady=(4, 8), before=self.nb)
        self.status = tk.Label(foot, text="Listo. Abre un archivo .ppf.", bg=T["bg"], fg=T["mut"], anchor="w", font=(FONT, 9))
        self.status.pack(side="left", fill="x", expand=True)
        credit = tk.Frame(foot, bg=T["bg"])
        credit.pack(side="right")
        tk.Label(credit, text=f"v{VERSION}  ·  Desarrollado por", bg=T["bg"], fg=T["mut"], font=(FONT, 9)).pack(side="left")
        link = tk.Label(credit, text=f" {AUTOR} ", bg=T["bg"], fg=T["accent"], font=(FONT, 9, "bold"), cursor="hand2")
        link.pack(side="left")
        web = tk.Label(credit, text="angelcm.com", bg=T["bg"], fg=T["fg"], font=(FONT, 9, "underline"), cursor="hand2")
        web.pack(side="left")
        for wdg in (link, web):
            wdg.bind("<Button-1>", lambda e: webbrowser.open(WEB))
        web.bind("<Enter>", lambda e: web.configure(fg=T["accent"]))
        web.bind("<Leave>", lambda e: web.configure(fg=T["fg"]))

    def about(self):
        d = tk.Toplevel(self, bg=T["bg"])
        d.title(f"Acerca de {APP}")
        d.resizable(False, False)
        d.transient(self)
        c = tk.Canvas(d, width=420, height=250, bg=T["bg"], highlightthickness=0)
        c.pack()
        self._about_bg = gradient_image(420, 250)
        c.create_image(0, 0, image=self._about_bg, anchor="nw")
        draw_logo(c, 210, 70, 34)
        c.create_text(210, 132, text="PPF TESTER", fill=T["fg"], font=(HFONT, 22))
        c.create_text(210, 160, text=f"Versión {VERSION} · Sample Lab para Yamaha PSR-S", fill="#bdb6c4", font=(FONT, 9))
        c.create_text(210, 192, text=f"Desarrollado por {AUTOR}", fill=T["fg"], font=(FONT, 10, "bold"))
        lk = c.create_text(160, 222, text="angelcm.com", fill=T["accent"], font=(FONT, 10, "underline"))
        gh = c.create_text(275, 222, text="GitHub", fill=T["fg"], font=(FONT, 10, "underline"))
        c.tag_bind(gh, "<Button-1>", lambda e: webbrowser.open(REPO))
        c.tag_bind(gh, "<Enter>", lambda e: c.configure(cursor="hand2"))
        c.tag_bind(gh, "<Leave>", lambda e: c.configure(cursor=""))
        c.tag_bind(lk, "<Button-1>", lambda e: webbrowser.open(WEB))
        c.tag_bind(lk, "<Enter>", lambda e: c.configure(cursor="hand2"))
        c.tag_bind(lk, "<Leave>", lambda e: c.configure(cursor=""))
        d.update_idletasks()
        d.geometry(f"+{self.winfo_x() + (self.winfo_width() - 420) // 2}+{self.winfo_y() + 160}")

    def _tab_samples(self, nb):
        f = ttk.Frame(nb, style="Panel.TFrame")
        f.columnconfigure(1, weight=1)
        f.rowconfigure(1, weight=1)

        self.piano = Piano(f, self.select_note)
        self.piano.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))

        left = ttk.Frame(f, style="Panel.TFrame")
        left.grid(row=1, column=0, sticky="nsw", padx=(12, 6), pady=(0, 12))
        cols = ("tecla", "muestra", "pico", "estado")
        tv = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse", height=8)
        for c, w, lab in (("tecla", 64, "Tecla"), ("muestra", 170, "Muestra"), ("pico", 70, "Pico"), ("estado", 70, "Estado")):
            tv.heading(c, text=lab)
            tv.column(c, width=w, anchor="w" if c == "muestra" else "center")
        for lv in ("ERROR", "AVISO", "INFO", "OK"):
            tv.tag_configure(lv, foreground=T[lv] if lv != "OK" else T["fg"])
        sb = ttk.Scrollbar(left, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="y", expand=True)
        sb.pack(side="left", fill="y")
        tv.bind("<<TreeviewSelect>>", self._on_select)
        tv.bind("<Double-1>", lambda e: self.play())
        tv.bind("<space>", lambda e: (self.play(), "break")[1])
        self.tv = tv

        right = ttk.Frame(f, style="Panel.TFrame")
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)
        self.wavev = Waveform(right)
        self.wavev.grid(row=0, column=0, sticky="ew")
        bar = ttk.Frame(right, style="Panel.TFrame")
        bar.grid(row=1, column=0, sticky="ew", pady=8)
        self.b_play = ttk.Button(bar, text="▶  Escuchar", style="Accent.TButton", command=self.play,
                                 state="disabled")
        self.b_play.pack(side="left")
        ttk.Button(bar, text="■  Parar", command=self.stop).pack(side="left", padx=6)
        self.b_spec = ttk.Button(bar, text="Espectro", command=lambda: self.b_spec.configure(
            text="Forma de onda" if self.wavev.toggle() == "espectro" else "Espectro"))
        self.b_spec.pack(side="right")
        self.b_imp = ttk.Button(bar, text="Reemplazar con WAV…", command=self.import_wav, state="disabled")
        self.b_imp.pack(side="right", padx=6)
        if sd is None:
            ttk.Label(bar, text="(instala 'sounddevice' para escuchar)", style="Mut.TLabel").pack(side="left", padx=8)
        else:
            ttk.Label(bar, text="Doble clic o barra espaciadora para escuchar", style="Mut.TLabel").pack(side="left", padx=8)
        self.metrics = tk.Frame(right, bg=T["panel"])
        self.metrics.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.metric_labels = {}
        names = [("dur", "Duración"), ("ch", "Canales"), ("sr", "Frecuencia"), ("pk", "Pico"), ("rms", "RMS"),
                 ("dc", "DC offset"), ("lead", "Silencio inicial"), ("tail", "Silencio final")]
        for i, (k, lab) in enumerate(names):
            cell = tk.Frame(self.metrics, bg=T["panel2"], padx=10, pady=6)
            cell.grid(row=i // 4, column=i % 4, sticky="ew", padx=3, pady=3)
            self.metrics.columnconfigure(i % 4, weight=1)
            tk.Label(cell, text=lab, bg=T["panel2"], fg=T["mut"], font=(FONT, 8)).pack(anchor="w")
            l = tk.Label(cell, text="—", bg=T["panel2"], fg=T["fg"], font=(FONT, 11, "bold"))
            l.pack(anchor="w")
            self.metric_labels[k] = l
        ed = tk.Frame(right, bg=T["panel2"], padx=10, pady=6)
        ed.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        tk.Label(ed, text="PARÁMETROS DE LA TECLA", bg=T["panel2"], fg=T["mut"], font=(FONT, 8, "bold")).grid(row=0, column=0, columnspan=12, sticky="w")
        self.ed = {}
        for i, (k, lab, lo, hi, inc, wdt) in enumerate((("tune", "Afinación (st)", -48, 48, 1, 5), ("vol", "Volumen (dB)", -96, 12, 0.5, 6),
                                                        ("pan", "Paneo (−64…63)", -64, 63, 1, 5), ("cut", "Filtro (Hz)", 20, 20000, 100, 7),
                                                        ("grp", "Grupo corte", 0, 127, 1, 4))):
            tk.Label(ed, text=lab, bg=T["panel2"], fg=T["fg"], font=(FONT, 9)).grid(row=1, column=i * 2, sticky="e", padx=(0, 4))
            sp = ttk.Spinbox(ed, from_=lo, to=hi, increment=inc, width=wdt)
            sp.grid(row=1, column=i * 2 + 1, sticky="w", padx=(0, 10))
            self.ed[k] = sp
        self.b_apply = ttk.Button(ed, text="Aplicar", command=self.apply_params, state="disabled")
        self.b_apply.grid(row=1, column=10, padx=(4, 0))
        self.wprobs = text_widget(right, 5)
        self.wprobs.grid(row=4, column=0, sticky="nsew")
        return f

    def _tab_kit(self, nb):
        f = ttk.Frame(nb, style="Panel.TFrame")
        ttk.Label(f, text="Problemas del mapa de teclas, velocidades y balance del kit", style="H.TLabel").pack(anchor="w", padx=14, pady=(14, 6))
        self.kprobs = text_widget(f, 20)
        self.kprobs.pack(fill="both", expand=True, padx=8, pady=(0, 12))
        return f

    def _tab_keyboard(self, nb):
        f = ttk.Frame(nb, style="Panel.TFrame")
        form = ttk.Frame(f, style="Panel.TFrame")
        form.pack(fill="x", padx=14, pady=14)
        ttk.Label(form, text="1. Conecta el PSR por USB TO HOST, instala el pack y elige la voz en RIGHT 1.   "
                             "2. Conecta la salida del teclado a tu interfaz de audio.   3. Pulsa Iniciar.",
                  style="Mut.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 10))

        def lab(r, c, t):
            ttk.Label(form, text=t, style="Panel.TLabel").grid(row=r, column=c, sticky="w", padx=(0, 6), pady=4)

        lab(1, 0, "Salida MIDI")
        self.cb_midi = ttk.Combobox(form, state="readonly", width=34)
        self.cb_midi.grid(row=1, column=1, sticky="w", padx=(0, 18))
        lab(1, 2, "Canal")
        self.sp_ch = ttk.Spinbox(form, from_=1, to=16, width=5)
        self.sp_ch.set(1)
        self.sp_ch.grid(row=1, column=3, sticky="w", padx=(0, 18))
        lab(1, 4, "Velocidades")
        self.e_vel = ttk.Entry(form, width=14)
        self.e_vel.insert(0, "40,80,127")
        self.e_vel.grid(row=1, column=5, sticky="w")
        self.var_rec = tk.BooleanVar(value=sd is not None)
        ttk.Checkbutton(form, text="Grabar desde", variable=self.var_rec).grid(row=2, column=0, sticky="w", pady=4)
        self.cb_in = ttk.Combobox(form, state="readonly", width=34)
        self.cb_in.grid(row=2, column=1, sticky="w")
        ttk.Button(form, text="↻  Buscar dispositivos", command=self.refresh_devices).grid(row=2, column=2, columnspan=2, sticky="w", padx=(0, 12))
        self.b_test = ttk.Button(form, text="▶  Iniciar prueba", style="Accent.TButton", command=self.run_keyboard, state="disabled")
        self.b_test.grid(row=2, column=4, columnspan=2, sticky="w")
        self.klog = text_widget(f, 16)
        self.klog.pack(fill="both", expand=True, padx=8, pady=(0, 12))
        self.after(300, self.refresh_devices)
        return f

    # ---------- dispositivos
    def refresh_devices(self):
        try:
            import midi_test as M
            outs = M.midi_outputs()
            self.cb_midi["values"] = [f"[{i}] {n}" for i, n in enumerate(outs)]
            kb = M.find_keyboard_port()
            if outs:
                self.cb_midi.current(kb if kb is not None else 0)
        except Exception as e:  # noqa: BLE001
            self.cb_midi["values"] = [f"(MIDI no disponible: {e})"]
        if sd is not None:
            ins = []
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0:
                    api = sd.query_hostapis(d["hostapi"])["name"]
                    ins.append(f"[{i}] {d['name']} · {api}")
            self.cb_in["values"] = ins
            if ins and not self.cb_in.get():
                pref = next((k for k, s in enumerate(ins) if ("M-Track" in s or "Line" in s) and "MME" in s), 0)
                self.cb_in.current(pref)

    # ---------- archivo
    def open_file(self, path=None):
        path = path or filedialog.askopenfilename(title="Abrir pack de Yamaha",
                                                  filetypes=[("Yamaha Expansion Manager", "*.ppf"), ("Todos", "*.*")])
        if not path:
            return
        self.set_status(f"Analizando {os.path.basename(path)}…")
        self._bg(lambda: self._load(path), self._loaded)

    def _load(self, path):
        pack = load_pack(path)
        kits, waves = full_analysis(pack)
        return pack, kits, waves

    def _loaded(self, res):
        self.pack_, self.kits, self.waves = res
        self.rep_by_uid = {w.uid: w for w in self.waves}
        p = self.pack_
        cnt = lambda lv: sum(x.level == lv for w in self.waves for x in w.problems) + sum(x.level == lv for k in self.kits for x in k.problems)
        self.stat_labels["title"].configure(text=p.title)
        self.stat_labels["voices"].configure(text=str(len(p.voices)))
        self.stat_labels["waves"].configure(text=str(len(p.waves)))
        self.stat_labels["mem"].configure(text=f"{A.memory_bytes(p) / 1e6:.2f} MB")
        self.stat_labels["ERROR"].configure(text=str(cnt("ERROR") + len(p.errors)))
        self.stat_labels["AVISO"].configure(text=str(cnt("AVISO")))
        self.tv.delete(*self.tv.get_children())
        self.zone_by_iid = {}
        status = {}
        for k in self.kits:
            for z in k.zones:
                r = self.rep_by_uid.get(z["uid"])
                st = r.worst if r else "ERROR"
                key = note_name(z["note_lo"]) if z["note_lo"] == z["note_hi"] else f"{note_name(z['note_lo'])}–{note_name(z['note_hi'])}"
                if z["vel_lo"] != 1 or z["vel_hi"] != 127:
                    key += f" v{z['vel_lo']}-{z['vel_hi']}"
                iid = self.tv.insert("", "end", values=(key, ", ".join(sorted(set(z["samples"]))) or "(falta)",
                                                        f"{r.peak_db:.1f}" if r else "", st), tags=(st,))
                self.zone_by_iid[iid] = z
                for n in range(z["note_lo"], min(z["note_hi"], z["note_lo"] + 127) + 1):
                    prev = status.get(n)
                    status[n] = st if prev is None or ("OK", "INFO", "AVISO", "ERROR").index(st) > ("OK", "INFO", "AVISO", "ERROR").index(prev) else prev
        self.piano.set_keys(status)
        self.listen.load(p)
        self.mejorar.on_load(p)
        probs = [A.Problem("ERROR", "lectura", e) for e in p.errors] + [x for k in self.kits for x in k.problems]
        write_problems(self.kprobs, probs, "El mapa del kit está correcto.")
        for b in (self.b_fix, self.b_wav, self.b_rep, self.b_play, self.b_test, self.b_imp, self.b_apply, self.b_save):
            b.configure(state="normal")
        kids = self.tv.get_children()
        if kids:
            self.tv.selection_set(kids[0])
            self.tv.focus(kids[0])
        self.title(f"{APP} — {os.path.basename(p.path)}")
        self.set_status(f"{os.path.basename(p.path)} analizado.")

    def _on_select(self, _=None):
        sel = self.tv.selection()
        if not sel or not self.pack_:
            return
        z = self.zone_by_iid[sel[0]]
        w = self.pack_.waves.get(z["uid"])
        r = self.rep_by_uid.get(z["uid"])
        self.piano.selected = z["note_lo"]
        self.piano.redraw()
        self.wavev.show(w, r)
        if r:
            m = self.metric_labels
            m["dur"].configure(text=f"{r.duration:.2f} s")
            m["ch"].configure(text="estéreo" if r.channels > 1 else ("mono" + (" (L+R)" if z["fake_stereo"] else "")))
            m["sr"].configure(text=f"{r.rate:.0f} Hz")
            m["pk"].configure(text=f"{r.peak_db:.1f} dBFS", fg=T["ERROR"] if r.clipped else T["fg"])
            m["rms"].configure(text=f"{r.rms_db:.1f} dBFS")
            m["dc"].configure(text=f"{r.dc_pct:+.2f} %")
            m["lead"].configure(text=f"{r.lead_silence_ms:.0f} ms")
            m["tail"].configure(text=f"{r.tail_silence_ms:.0f} ms")
            write_problems(self.wprobs, r.problems)
        self._fill_params(z)

    # ---------- edición
    def _fill_params(self, z):
        import motor
        el = next((e for e in self.pack_.voices[0].elements if e.number == z["element"]), None) if self.pack_.voices else None
        if el is None:
            return
        snd, _ = motor.parse_sound(self.pack_.voices[0])
        es = snd.get(el.number)
        vals = dict(tune=el.tune_coarse, vol=f"{es.vol_db:.1f}" if es else "0",
                    pan=round(el.pan if abs(el.pan) > 1 else el.pan * 64),
                    cut=f"{es.lpf_hz:.0f}" if es and es.lpf_hz else "20000", grp=el.alternate_group)
        for k, v in vals.items():
            self.ed[k].delete(0, "end")
            self.ed[k].insert(0, str(v))

    def apply_params(self):
        from ppf_format import edit_element, reparse_voices
        sel = self.tv.selection()
        if not sel or not self.pack_:
            return
        z = self.zone_by_iid[sel[0]]
        v = self.pack_.voices[0]
        try:
            vals = {k: float(self.ed[k].get()) for k in self.ed}
        except ValueError:
            messagebox.showerror(APP, "Revisa los valores: deben ser números.")
            return
        n = z["element"]
        edit_element(self.pack_, v, n, "pitchBlock", "tuneCoarse", int(vals["tune"]))
        edit_element(self.pack_, v, n, None, "volume", float(vals["vol"]))
        edit_element(self.pack_, v, n, "panBlock", "pan", float(vals["pan"]))
        edit_element(self.pack_, v, n, "filterBlock", "dcfCutoff", float(vals["cut"]))
        edit_element(self.pack_, v, n, "drumSetup", "alternateGroup", int(vals["grp"]))
        reparse_voices(self.pack_)
        self._mark_modified(f"Parámetros de {note_name(z['note_lo'])} cambiados (sin guardar).")

    def import_wav(self):
        import copy as _copy
        import wave as wavelib
        import dsp
        from ppf_format import replace_wave, reparse_voices
        sel = self.tv.selection()
        if not sel:
            return
        z = self.zone_by_iid[sel[0]]
        path = filedialog.askopenfilename(title="WAV para reemplazar la muestra", filetypes=[("WAV", "*.wav")])
        if not path:
            return
        try:
            with wavelib.open(path, "rb") as f:
                ch, sw, sr, n = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
                raw = f.readframes(n)
            if sw == 2:
                x = np.frombuffer(raw, "<i2").astype(np.float64) / 32768
            elif sw == 3:
                b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
                v24 = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
                v24 = np.where(v24 >= 1 << 23, v24 - (1 << 24), v24)
                x = v24 / 8388608.0
            elif sw == 4:
                x = np.frombuffer(raw, "<i4").astype(np.float64) / 2147483648
            else:
                raise ValueError(f"{sw * 8} bits no soportado")
            x = x.reshape(-1, ch)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP, "No se pudo leer el WAV (usa PCM 16/24/32 bits):\n" + str(e))
            return
        old = self.pack_.waves[z["uid"]]
        x = dsp.to_rate(x, sr, 44100)
        x = x[:, :1] if old.channels == 1 else (x if x.shape[1] == 2 else np.repeat(x, 2, axis=1))
        nw = _copy.copy(old)
        nw.samples = np.clip(x, -1, 32767 / 32768)
        nw.markers = {k: (len(x) if pos >= old.frames else min(pos, len(x)), nm) for k, (pos, nm) in old.markers.items()}
        replace_wave(self.pack_, z["uid"], nw)
        reparse_voices(self.pack_)
        mb = x.shape[0] * nw.channels * 2 / 1e6
        self._mark_modified(f"'{old.name}' reemplazada por {os.path.basename(path)} ({mb:.2f} MB, sin guardar).")

    def _mark_modified(self, msg):
        keep = self.tv.selection()
        idx = self.tv.index(keep[0]) if keep else 0
        kits, waves = full_analysis(self.pack_)
        self._loaded((self.pack_, kits, waves))
        kids = self.tv.get_children()
        if kids:
            self.tv.selection_set(kids[min(idx, len(kids) - 1)])
        self.title(f"{APP} — {os.path.basename(self.pack_.path)} *")
        self.set_status(msg + "  Usa «Guardar como…» para crear el archivo.")

    def save_as(self):
        from ppf_format import load_pack as _lp
        src = self.pack_.path
        out = filedialog.asksaveasfilename(title="Guardar pack", defaultextension=".ppf", initialdir=os.path.dirname(src),
                                           initialfile=os.path.splitext(os.path.basename(src))[0] + "_editado.ppf",
                                           filetypes=[("Yamaha Expansion Manager", "*.ppf")])
        if not out:
            return
        if os.path.abspath(out) == os.path.abspath(src) and not messagebox.askyesno(APP, "¿Sobrescribir el archivo abierto?"):
            return
        self.pack_.save(out)
        chk = _lp(out)
        if chk.errors:
            messagebox.showerror(APP, "El archivo guardado no pasó la verificación:\n" + "\n".join(chk.errors))
            return
        self.pack_.path = out
        self.title(f"{APP} — {os.path.basename(out)}")
        self.set_status(f"Guardado: {out}")

    def select_note(self, n):
        for iid, z in self.zone_by_iid.items():
            if z["note_lo"] <= n <= z["note_hi"]:
                self.tv.selection_set(iid)
                self.tv.see(iid)
                self.play()
                return

    def play(self):
        if sd is None or not self.pack_:
            return
        sel = self.tv.selection()
        if not sel:
            return
        w = self.pack_.waves.get(self.zone_by_iid[sel[0]]["uid"])
        if w is not None:
            try:
                sd.stop()
                sd.play(w.samples.astype(np.float32), int(w.rate))
            except Exception as e:  # noqa: BLE001
                self.set_status(f"No se pudo reproducir: {e}")

    def stop(self):
        if sd is not None:
            sd.stop()

    def export_wav(self):
        folder = filedialog.askdirectory(title="Carpeta para los WAV")
        if not folder:
            return

        def job():
            for w in self.pack_.waves.values():
                _write_wav(os.path.join(folder, _safe(w.name) + ".wav"), w.samples, w.rate)
            return folder
        self._bg(job, lambda f: (self.set_status(f"{len(self.pack_.waves)} WAV exportados en {f}"), os.startfile(f) if sys.platform == "win32" else None))

    def open_report(self):
        base = os.path.splitext(self.pack_.path)[0] + "_informe.html"
        R.write_report(base, self.pack_, self.kits, self.waves)
        webbrowser.open("file:///" + os.path.abspath(base).replace("\\", "/"))
        self.set_status(f"Informe: {base}")

    # ---------- corregir
    def fix_dialog(self):
        d = tk.Toplevel(self, bg=T["panel"])
        d.title("Corregir pack")
        d.transient(self)
        d.grab_set()
        d.resizable(False, False)
        ttk.Label(d, text="Correcciones automáticas", style="Big.TLabel").pack(anchor="w", padx=20, pady=(18, 2))
        ttk.Label(d, text="Se guarda un archivo nuevo; el original no se modifica.", style="Mut.TLabel").pack(anchor="w", padx=20)
        opts = [("dc", "Quitar DC offset", True), ("fades", "Fades anti-clic al inicio y final", True),
                ("trim", "Recortar silencio final (ahorra memoria)", True),
                ("lead", "Recortar silencio inicial (golpe más inmediato)", False),
                ("hh", "Hi-hat: el cerrado corta al abierto (Alternate Group)", False),
                ("norm", "Normalizar cada muestra a −1 dBFS (cambia el balance)", False)]
        vars_ = {}
        box = ttk.Frame(d, style="Panel.TFrame")
        box.pack(fill="x", padx=20, pady=14)
        for k, t, v in opts:
            vars_[k] = tk.BooleanVar(value=v)
            ttk.Checkbutton(box, text=t, variable=vars_[k]).pack(anchor="w", pady=3)
        bar = ttk.Frame(d, style="Panel.TFrame")
        bar.pack(fill="x", padx=20, pady=(0, 18))

        def go():
            op = C.Opciones(quitar_dc=vars_["dc"].get(), fade_inicio=vars_["fades"].get(), fade_final=vars_["fades"].get(),
                            recortar_final=vars_["trim"].get(), recortar_inicio=vars_["lead"].get(),
                            normalizar_db=-1.0 if vars_["norm"].get() else None, agrupar_hihat=vars_["hh"].get())
            src = self.pack_.path
            out = filedialog.asksaveasfilename(parent=d, title="Guardar pack corregido", defaultextension=".ppf",
                                               initialfile=os.path.splitext(os.path.basename(src))[0] + "_corregido.ppf",
                                               initialdir=os.path.dirname(src), filetypes=[("Yamaha Expansion Manager", "*.ppf")])
            if not out:
                return
            if os.path.abspath(out) == os.path.abspath(src):
                messagebox.showerror(APP, "Por seguridad no se sobreescribe el archivo original.", parent=d)
                return
            d.destroy()
            self._bg(lambda: self._fix(src, out, op), self._fixed)

        ttk.Button(bar, text="Cancelar", command=d.destroy).pack(side="right")
        ttk.Button(bar, text="Corregir y guardar", style="Accent.TButton", command=go).pack(side="right", padx=8)
        d.update_idletasks()
        d.geometry(f"+{self.winfo_x() + (self.winfo_width() - d.winfo_width()) // 2}+{self.winfo_y() + 140}")

    def _fix(self, src, out, op):
        pack = load_pack(src)
        mem0 = A.memory_bytes(pack)
        log = C.corregir(pack, op)
        if not log:
            return None
        pack.save(out)
        check = load_pack(out)
        if check.errors:
            raise RuntimeError("El archivo corregido no pasó la verificación:\n" + "\n".join(check.errors))
        return out, log, mem0, A.memory_bytes(check)

    def _fixed(self, res):
        if res is None:
            messagebox.showinfo(APP, "No hay nada que corregir con las opciones elegidas.")
            return
        out, log, m0, m1 = res
        lines = "\n".join(f"• {n}: " + "; ".join(d) for n, d in log[:14])
        if len(log) > 14:
            lines += f"\n… y {len(log) - 14} más"
        if messagebox.askyesno(APP, f"Guardado: {os.path.basename(out)}\nAudio: {m0 / 1e6:.2f} → {m1 / 1e6:.2f} MB\n\n{lines}\n\n"
                                    "¿Abrir el pack corregido para revisarlo?\n\n"
                                    "Recuerda escucharlo en Expansion Manager antes de instalarlo en el teclado."):
            self.open_file(out)

    # ---------- prueba en teclado
    def _log(self, text, tag=None):
        self.klog.configure(state="normal")
        self.klog.insert("end", text + "\n", tag or ())
        self.klog.see("end")
        self.klog.configure(state="disabled")

    def run_keyboard(self):
        import midi_test as M
        if not self.kits:
            return
        try:
            port = int(self.cb_midi.get().split("]")[0].strip("["))
            ch = int(self.sp_ch.get())
            vels = [int(v) for v in self.e_vel.get().split(",") if v.strip()]
        except ValueError:
            messagebox.showerror(APP, "Revisa el puerto MIDI, el canal y las velocidades.")
            return
        rec = self.var_rec.get() and sd is not None
        dev = int(self.cb_in.get().split("]")[0].strip("[")) if rec and self.cb_in.get() else None
        kit = self.kits[0]
        if not messagebox.askokcancel(APP, f"Selecciona la voz '{kit.voice}' en RIGHT 1 del teclado (canal {ch}).\n\n¿Empezar la prueba?"):
            return
        self.klog.configure(state="normal")
        self.klog.delete("1.0", "end")
        self.klog.configure(state="disabled")
        self.b_test.configure(state="disabled")
        waves_by_name = {w.name: w for w in self.pack_.waves.values()}
        pack = self.pack_

        def job():
            hits, audio, sr = M.run_test(kit, waves_by_name, port, ch, vels, dev, rec,
                                         log=lambda s: self.q.put(("log", s)))
            probs = M.evaluate(hits) if rec else []
            folder = None
            if rec:
                folder = os.path.splitext(pack.path)[0] + "_grabacion"
                os.makedirs(folder, exist_ok=True)
                _write_wav(os.path.join(folder, "sesion_completa.wav"), audio, sr)
                for h in hits:
                    if h.audio is not None:
                        _write_wav(os.path.join(folder, f"{h.note:03d}_{note_name(h.note).replace('#', 's')}_v{h.vel:03d}_{_safe(h.name)}.wav"), h.audio, sr)
            return hits, probs, folder, rec

        def done(res):
            hits, probs, folder, rec = res
            self.b_test.configure(state="normal")
            if not rec:
                self._log("\nPrueba terminada (sin grabación).", "OK")
                return
            self._log("\nResultado:", "mut")
            if not [p for p in probs if p.level != "INFO"]:
                self._log("✔  Todas las notas sonaron y la dinámica es correcta.", "OK")
            for p in probs:
                self.klog.configure(state="normal")
                self.klog.insert("end", f"{p.level:<6}", p.level)
                self.klog.insert("end", "  " + p.text + "\n")
                self.klog.configure(state="disabled")
            self._log("\nTecla   Vel   Pico       Retardo   Muestra", "mut")
            for h in hits:
                lat = f"{h.latency_ms:5.0f} ms" if h.latency_ms is not None else " MUDO  "
                self._log(f"{note_name(h.note):<7} {h.vel:>3}   {h.peak_db:6.1f} dB  {lat}   {h.name}",
                          "mono" if h.latency_ms is not None else "ERROR")
            self._log(f"\nGrabaciones en: {folder}", "mut")
            self.set_status("Prueba en el teclado terminada.")

        self._bg(job, done, on_error=lambda: self.b_test.configure(state="normal"))

    # ---------- hilos
    def _bg(self, fn, cb, on_error=None):
        def run():
            try:
                self.q.put(("ok", cb, fn()))
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.q.put(("err", on_error, e))
        threading.Thread(target=run, daemon=True).start()

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "log":
                    self._log(item[1])
                elif item[0] == "ok":
                    item[1](item[2])
                else:
                    if item[1]:
                        item[1]()
                    self.set_status(f"Error: {item[2]}")
                    messagebox.showerror(APP, str(item[2]))
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def set_status(self, t):
        self.status.configure(text=t)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PPFTester.App")
        except Exception:  # noqa: BLE001
            pass
    app = App()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        app.after(200, lambda: app.open_file(sys.argv[1]))
    app.mainloop()


if __name__ == "__main__":
    main()
