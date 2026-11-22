"""Pestaña «Mejorar kit»: aplica todas las mejoras según el modelo de teclado."""
from __future__ import annotations

import copy
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np

import mejora as Mj
import modelos
from ppf_format import load_pack, note_name


class MejorarTab(ttk.Frame):
    def __init__(self, parent, app, T, FONT, text_widget):
        super().__init__(parent, style="Panel.TFrame")
        self.app, self.T, self.FONT = app, T, FONT
        self.result = None          # (pack mejorado, filas, avisos, mb0, mb1)
        self.filas_by_iid = {}

        top = tk.Frame(self, bg=T["panel"])
        top.pack(fill="x", padx=14, pady=(12, 6))
        # modelo
        mf = tk.Frame(top, bg=T["panel2"], padx=12, pady=10)
        mf.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(mf, text="TECLADO DESTINO", bg=T["panel2"], fg=T["mut"], font=(FONT, 8, "bold")).pack(anchor="w")
        self.modelo = tk.StringVar(value=modelos.POR_DEFECTO)
        cb = ttk.Combobox(mf, state="readonly", values=list(modelos.MODELOS), textvariable=self.modelo, width=16)
        cb.pack(anchor="w", pady=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self._model_info())
        self.model_lab = tk.Label(mf, text="", bg=T["panel2"], fg=T["fg"], font=(FONT, 9), justify="left", wraplength=260)
        self.model_lab.pack(anchor="w")
        # opciones
        of = tk.Frame(top, bg=T["panel2"], padx=12, pady=10)
        of.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        tk.Label(of, text="QUÉ MEJORAR", bg=T["panel2"], fg=T["mut"], font=(FONT, 8, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        self.v = {}
        opts = [("correcciones", "Limpieza (DC, clics, silencio final)"), ("procesado", "Procesado por pieza (EQ, ataque, compresión)"),
                ("balance", "Balance del kit"), ("afinar_toms", "Afinar toms y bombos repetidos"),
                ("hihat", "Hi-hat: el cerrado corta al abierto"), ("abrir_filtro", "Abrir el filtro de la voz (más brillo)")]
        for i, (k, t) in enumerate(opts):
            self.v[k] = tk.BooleanVar(value=True)
            ttk.Checkbutton(of, text=t, variable=self.v[k], style="P2.TCheckbutton").grid(row=1 + i % 3, column=i // 3, sticky="w", padx=(0, 16))
        # intensidad + capas
        pf = tk.Frame(top, bg=T["panel2"], padx=12, pady=10)
        pf.grid(row=0, column=2, sticky="nsew")
        tk.Label(pf, text="INTENSIDAD Y CAPAS", bg=T["panel2"], fg=T["mut"], font=(FONT, 8, "bold")).pack(anchor="w")
        row = tk.Frame(pf, bg=T["panel2"])
        row.pack(fill="x")
        tk.Label(row, text="Intensidad del procesado", bg=T["panel2"], fg=T["fg"], font=(FONT, 10)).pack(side="left")
        self.int_lab = tk.Label(row, text="100 %", bg=T["panel2"], fg=T["accent"], font=(FONT, 10, "bold"), width=5)
        self.int_lab.pack(side="right")
        self.intensidad = tk.IntVar(value=100)
        tk.Scale(pf, from_=0, to=150, orient="horizontal", variable=self.intensidad, showvalue=False, length=220,
                 bg=T["panel2"], troughcolor=T["panel"], highlightthickness=0, sliderrelief="flat", activebackground=T["accent"],
                 command=lambda v: self.int_lab.configure(text=f"{int(float(v))} %")).pack(anchor="w")
        row = tk.Frame(pf, bg=T["panel2"])
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="Capas de velocidad", bg=T["panel2"], fg=T["fg"], font=(FONT, 10)).pack(side="left")
        self.capas = ttk.Combobox(row, state="readonly", width=16,
                                  values=["Auto (según modelo)", "Sin capas", "2 capas", "3 capas"])
        self.capas.current(0)
        self.capas.pack(side="right")
        for c in range(3):
            top.columnconfigure(c, weight=1)

        bar = tk.Frame(self, bg=T["panel"])
        bar.pack(fill="x", padx=14, pady=6)
        self.b_prev = ttk.Button(bar, text="✨  Mejorar (vista previa)", style="Accent.TButton", command=self.preview, state="disabled")
        self.b_prev.pack(side="left")
        self.b_save = ttk.Button(bar, text="💾  Guardar .ppf mejorado", command=self.save, state="disabled")
        self.b_save.pack(side="left", padx=6)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)
        self.b_a = ttk.Button(bar, text="▶  Antes", command=lambda: self._play("antes"), state="disabled")
        self.b_a.pack(side="left")
        self.b_d = ttk.Button(bar, text="▶  Después", command=lambda: self._play("despues"), state="disabled")
        self.b_d.pack(side="left", padx=6)
        self.mem_lab = tk.Label(bar, text="", bg=T["panel"], fg=T["fg"], font=(FONT, 10, "bold"))
        self.mem_lab.pack(side="right")

        body = tk.Frame(self, bg=T["panel"])
        body.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        cols = ("pieza", "tipo", "teclas", "cambios")
        tv = ttk.Treeview(body, columns=cols, show="headings", selectmode="browse")
        for c, w, lab in (("pieza", 150, "Muestra"), ("tipo", 90, "Tipo"), ("teclas", 120, "Teclas"), ("cambios", 420, "Cambios")):
            tv.heading(c, text=lab)
            tv.column(c, width=w, anchor="w")
        tv.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tv.bind("<<TreeviewSelect>>", lambda e: self._sel())
        tv.bind("<Double-1>", lambda e: self._play("despues"))
        self.tv = tv
        self.info = text_widget(body, 10)
        self.info.grid(row=0, column=1, sticky="nsew")
        self._model_info()

    # ------------------------------------------------------------------
    def _model_info(self):
        m = modelos.MODELOS[self.modelo.get()]
        self.model_lab.configure(text=f"Memoria de expansión: {m.memoria_mb:.0f} MB\n"
                                      f"Recomendado por kit: ≤ {m.kit_max_mb:.0f} MB\n{m.nota}")

    def on_load(self, pack):
        self.result = None
        self.tv.delete(*self.tv.get_children())
        self.b_prev.configure(state="normal" if pack and pack.voices else "disabled")
        for b in (self.b_save, self.b_a, self.b_d):
            b.configure(state="disabled")
        self.mem_lab.configure(text="")
        self._write([("mut", "Elige el teclado destino y pulsa «Mejorar». Nada se guarda hasta que pulses «Guardar».")])

    def _opts(self):
        c = self.capas.current()
        return Mj.OpcionesMejora(modelo=self.modelo.get(), intensidad=self.intensidad.get() / 100,
                                 capas=["auto", "0", "2", "3"][c], **{k: v.get() for k, v in self.v.items()})

    def preview(self):
        src = self.app.pack_
        if src is None:
            return
        op = self._opts()
        self.b_prev.configure(state="disabled")
        self.app.set_status("Mejorando el kit…")

        def job():
            pack = copy.deepcopy(src)
            filas, avisos, mb0, mb1 = Mj.mejorar(pack, op)
            return pack, filas, avisos, mb0, mb1

        def done(res):
            self.b_prev.configure(state="normal")
            self.result = res
            pack, filas, avisos, mb0, mb1 = res
            self.tv.delete(*self.tv.get_children())
            self.filas_by_iid = {}
            for f in filas:
                iid = self.tv.insert("", "end", values=(f.nombre, Mj.NOMBRE_TIPO[f.tipo],
                                                        ", ".join(note_name(n) for n in f.notas), " · ".join(f.cambios)))
                self.filas_by_iid[iid] = f
            m = modelos.MODELOS[op.modelo]
            pct = mb1 / m.memoria_mb * 100
            col = self.T["OK"] if mb1 <= m.kit_max_mb else self.T["AVISO"] if mb1 <= m.memoria_mb else self.T["ERROR"]
            self.mem_lab.configure(text=f"Audio: {mb0:.2f} → {mb1:.2f} MB  ({pct:.1f} % del {m.nombre})", fg=col)
            lines = [("mut", "Compatibilidad con la serie S\n")]
            for nombre, est, txt in modelos.compatibilidad(mb1):
                lines.append((est, f"{est:<6}"))
                lines.append((None, f" {nombre}: {txt}\n"))
            if avisos:
                lines.append(("mut", "\nNotas\n"))
                for a in avisos:
                    lines.append(("INFO", "INFO   "))
                    lines.append((None, a + "\n"))
            lines.append(("mut", "\nSelecciona una muestra y compara ▶ Antes / ▶ Después. "
                                 "Luego guarda y escúchalo en «Escuchar como en el teclado» (simulación o PSR real)."))
            self._write(lines)
            self.b_save.configure(state="normal")
            kids = self.tv.get_children()
            if kids:
                self.tv.selection_set(kids[0])
            self.app.set_status("Vista previa lista. Nada se ha guardado todavía.")

        self.app._bg(job, done, on_error=lambda: self.b_prev.configure(state="normal"))

    def _write(self, parts):
        t = self.info
        t.configure(state="normal")
        t.delete("1.0", "end")
        for tag, txt in parts:
            t.insert("end", txt, tag or ())
        t.configure(state="disabled")

    def _sel(self):
        ok = bool(self.tv.selection())
        self.b_a.configure(state="normal" if ok else "disabled")
        self.b_d.configure(state="normal" if ok else "disabled")

    def _play(self, which):
        sel = self.tv.selection()
        if not sel:
            return
        f = self.filas_by_iid[sel[0]]
        x = f.antes if which == "antes" else f.despues
        if x is None:
            return
        x = x if x.shape[1] == 2 else np.repeat(x, 2, axis=1)
        try:
            self.app.listen._ensure_mixer().play(x.astype(np.float32), 0, -1)
        except Exception as e:  # noqa: BLE001
            self.app.set_status(f"No se pudo reproducir: {e}")

    def save(self):
        if not self.result:
            return
        pack = self.result[0]
        src = self.app.pack_.path
        mod = self.modelo.get().replace("PSR-", "")
        out = filedialog.asksaveasfilename(title="Guardar pack mejorado", defaultextension=".ppf",
                                           initialdir=os.path.dirname(src),
                                           initialfile=os.path.splitext(os.path.basename(src))[0] + f"_PRO_{mod}.ppf",
                                           filetypes=[("Yamaha Expansion Manager", "*.ppf")])
        if not out:
            return
        if os.path.abspath(out) == os.path.abspath(src):
            messagebox.showerror("PPF Tester", "Por seguridad no se sobreescribe el archivo original.")
            return
        pack.path = out
        pack.save(out)
        chk = load_pack(out)
        if chk.errors:
            messagebox.showerror("PPF Tester", "El archivo guardado no pasó la verificación:\n" + "\n".join(chk.errors))
            return
        if messagebox.askyesno("PPF Tester", f"Guardado: {os.path.basename(out)}\n\n¿Abrirlo ahora para escucharlo y probarlo en el teclado?\n\n"
                                             "Ábrelo también en Yamaha Expansion Manager para verificarlo antes de instalarlo."):
            self.app.open_file(out)
