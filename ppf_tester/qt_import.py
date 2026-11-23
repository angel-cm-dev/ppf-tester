"""Página «Importar WAV»: crea un kit .ppf desde una carpeta de WAV, editable."""
from __future__ import annotations

import os

import numpy as np
from PySide6.QtCore import QMimeData, QTimer, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (QMessageBox, QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QProgressBar, QPushButton, QSlider, QSpinBox, QTableWidget,
                               QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

import importar_wav as I
import modelos
from qt_fx import GlowPiano, MemoryBars, caption, card, icon
from qt_pages import Page, btn, hbox, vbox
from qt_theme import C, q

MIME = "application/x-ppf-pieza"


class DropPiano(GlowPiano):
    """Piano que acepta piezas arrastradas desde la tabla o la lista de archivos."""
    dropped = Signal(int, str)

    def __init__(self, parent=None, height=110):
        super().__init__(parent, height)
        self.setAcceptDrops(True)
        self.hover = None

    def _nota_en(self, pos):
        for r, n in self._rects:
            if r.contains(pos):
                return n
        return None

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MIME):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        n = self._nota_en(e.position())
        if n != self.hover:
            self.hover = n
            if n is not None:
                self.flash(n, 0.6)
        e.acceptProposedAction()

    def dropEvent(self, e):
        n = self._nota_en(e.position())
        if n is not None:
            self.dropped.emit(n, bytes(e.mimeData().data(MIME)).decode())
            e.acceptProposedAction()


class KitTable(QTableWidget):
    """Tabla del kit; arrastra una fila (columna «Tecla») hasta el piano para moverla."""

    def __init__(self, *a):
        super().__init__(*a)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

    def startDrag(self, actions):
        r = self.currentRow()
        if r < 0:
            return
        md = QMimeData()
        md.setData(MIME, f"row:{r}".encode())
        d = QDrag(self)
        d.setMimeData(md)
        d.exec(Qt.DropAction.MoveAction)


class FilesTree(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setStyleSheet(f"QTreeWidget {{ background: transparent; border: none; }}"
                           f" QTreeWidget::branch {{ background: transparent; }} QTreeWidget::item {{ padding: 4px 2px; }} QTreeWidget::item:selected {{ background: rgba(244,184,96,0.14); color: {C['fg']}; }}")

    def startDrag(self, actions):
        it = self.currentItem()
        if it is None or it.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        g, v = it.data(0, Qt.ItemDataRole.UserRole)
        md = QMimeData()
        md.setData(MIME, f"file:{g}:{v}".encode())
        d = QDrag(self)
        d.setMimeData(md)
        d.exec(Qt.DropAction.CopyAction)


NOTAS = list(range(27, 88))


class ImportPage(Page):
    title = "Importar WAV"
    subtitle = "Elige una carpeta con tus golpes de batería y la app arma tu kit .ppf. Todo es editable."

    def __init__(self, ctx):
        super().__init__(ctx)
        self.archivos = []
        self.grupos: list[I.Grupo] = []
        self.piezas: list[I.Pieza] = []
        self.carpeta = ""
        self._loading = False
        self._undo, self._redo = [], []
        root = vbox(self, 0, 12)

        # ---- barra superior
        top = card()
        tl = hbox(top, 16, 12)
        tl.setContentsMargins(16, 12, 16, 12)
        self.b_folder = btn("Elegir carpeta de WAV", "folder", primary=True)
        self.b_folder.clicked.connect(self.choose)
        tl.addWidget(self.b_folder)
        self.lbl_path = QLabel("Arrastra aquí una carpeta con WAV o pulsa el botón.")
        self.lbl_path.setObjectName("Mut")
        tl.addWidget(self.lbl_path, 1)
        tl.addWidget(caption("Nombre"))
        self.e_name = QLineEdit("Mi Kit")
        self.e_name.setMaxLength(20)
        self.e_name.setFixedWidth(170)
        tl.addWidget(self.e_name)
        tl.addWidget(caption("Teclado"))
        self.cb_model = QComboBox()
        self.cb_model.addItems(list(modelos.MODELOS))
        self.cb_model.currentIndexChanged.connect(self._schedule_estimate)
        tl.addWidget(self.cb_model)
        self.b_build = btn("Crear .ppf", "sparkle", primary=True)
        self.b_build.clicked.connect(self.build)
        self.b_build.setEnabled(False)
        tl.addWidget(self.b_build)
        root.addWidget(top)

        opts = hbox(None, 0, 16)
        self.chk_proc = QCheckBox("Mejorar cada pieza")
        self.chk_proc.setChecked(True)
        self.sl_int = QSlider(Qt.Orientation.Horizontal)
        self.sl_int.setRange(0, 150)
        self.sl_int.setValue(50)
        self.sl_int.setFixedWidth(120)
        self.lbl_int = QLabel("50 %")
        self.lbl_int.setStyleSheet(f"color:{C['gold']}; font-weight:700")
        self.sl_int.valueChanged.connect(lambda v: self.lbl_int.setText(f"{v} %"))
        self.chk_st = QCheckBox("Platos en estéreo")
        self.chk_st.setChecked(True)
        self.chk_nat = QCheckBox("Dinámica natural entre capas")
        self.chk_gm = QCheckBox("Completar teclas GM")
        self.chk_gm.setChecked(True)
        self.chk_gm.toggled.connect(lambda _: self.auto())
        self.chk_lvl = QCheckBox("Nivel como el teclado")
        self.chk_lvl.setChecked(True)
        self.chk_lvl.setToolTip("Ajusta el volumen de cada pieza a un nivel de referencia parecido al de los kits\n"
                                "de fábrica, para que el kit no salte de volumen al cambiar de voz.")
        self.lbl_sala = QLabel("Sala 0 %")
        self.sl_sala = QSlider(Qt.Orientation.Horizontal)
        self.sl_sala.setRange(0, 100)
        self.sl_sala.setValue(0)
        self.sl_sala.setFixedWidth(90)
        self.sl_sala.setToolTip("Sala corta integrada en cada muestra: suena más grande sin gastar\n"
                                "los efectos del teclado. Alarga un poco las colas (más memoria).")
        self.sl_sala.valueChanged.connect(lambda v: self.lbl_sala.setText(f"Sala {v} %"))
        self.sl_sala.sliderReleased.connect(self._schedule_estimate)
        self.lbl_amb = QLabel("Ambiente 40 %")
        self.sl_amb = QSlider(Qt.Orientation.Horizontal)
        self.sl_amb.setRange(0, 100)
        self.sl_amb.setValue(40)
        self.sl_amb.setFixedWidth(90)
        self.sl_amb.setToolTip("Kit multi-micrófono: cuánto de overheads y sala se mezcla con los micrófonos cercanos.")
        self.sl_amb.valueChanged.connect(lambda v: self.lbl_amb.setText(f"Ambiente {v} %"))
        for w in (self.lbl_amb, self.sl_amb):
            w.setVisible(False)
        for w in (self.chk_proc, self.sl_int, self.lbl_int, self.chk_st, self.chk_nat, self.chk_gm, self.chk_lvl):
            opts.addWidget(w)
            if isinstance(w, QCheckBox):
                w.toggled.connect(self._schedule_estimate)
        opts.addStretch(1)
        root.addLayout(opts)
        opts = hbox(None, 0, 16)
        for w in (self.lbl_sala, self.sl_sala, self.lbl_amb, self.sl_amb):
            opts.addWidget(w)
        opts.addStretch(1)
        self.b_empty = btn("Kit vacío", "doc")
        self.b_empty.setToolTip("Empieza un kit desde cero y añade muestras desde la Biblioteca")
        self.b_empty.clicked.connect(self.nuevo_vacio)
        opts.addWidget(self.b_empty)
        self.b_auto = btn("Volver a armar automático", "refresh")
        self.b_auto.clicked.connect(self.auto)
        opts.addWidget(self.b_auto)
        root.addLayout(opts)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # ---- piano
        pc = card()
        pl = vbox(pc, 12, 6)
        hint = QLabel("Clic en una tecla para escucharla · arrastra una fila (columna Tecla) o un archivo hasta una tecla para moverla o asignarla")
        hint.setObjectName("Mut")
        pl.addWidget(hint)
        self.piano = DropPiano(height=92)
        self.piano.keyClicked.connect(self._piano_click)
        self.piano.dropped.connect(self._dropped)
        pl.addWidget(self.piano)
        root.addWidget(pc)

        # ---- cuerpo
        body = hbox(None, 0, 12)
        root.addLayout(body, 1)
        kc = card()
        kl = vbox(kc, 12, 6)
        row = hbox(None, 0, 8)
        row.addWidget(caption("Tu kit"))
        row.addStretch(1)
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("Mut")
        row.addWidget(self.lbl_count)
        b_del = btn("Quitar", "stop")
        b_del.clicked.connect(self.remove_selected)
        row.addWidget(b_del)
        kl.addLayout(row)
        self.tbl = KitTable(0, 11)
        self.tbl.setHorizontalHeaderLabels(["", "Usar", "Tecla", "Pieza", "Muestra", "Versión", "Capas", "Variar", "Estéreo", "Afin.", ""])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setShowGrid(False)
        self.tbl.verticalHeader().setDefaultSectionSize(40)
        hh = self.tbl.horizontalHeader()
        for i, w in enumerate((24, 40, 140, 108, 0, 54, 48, 48, 66, 52, 34)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch if w == 0 else QHeaderView.ResizeMode.Fixed)
            if w:
                self.tbl.setColumnWidth(i, w)
        self.tbl.itemSelectionChanged.connect(self._sel)
        kl.addWidget(self.tbl)
        body.addWidget(kc, 7)

        side = QVBoxLayout()
        side.setSpacing(12)
        fc = card()
        fl = vbox(fc, 12, 6)
        fl.addWidget(caption("Archivos encontrados"))
        self.tree = FilesTree()
        self.tree.itemDoubleClicked.connect(self._tree_play)
        fl.addWidget(self.tree, 1)
        r2 = hbox(None, 0, 8)
        b_play = btn("Escuchar", "play")
        b_play.clicked.connect(lambda: self._tree_play(self.tree.currentItem()))
        b_add = btn("Añadir a tecla libre", "sparkle")
        b_add.clicked.connect(self.add_from_tree)
        b_lib = btn("A la biblioteca", "library")
        b_lib.setToolTip("Guarda el grupo o archivo elegido (o todos) en tu Biblioteca de muestras")
        b_lib.clicked.connect(self.to_library)
        r2.addWidget(b_play)
        r2.addWidget(b_add)
        r2.addWidget(b_lib)
        fl.addLayout(r2)
        side.addWidget(fc, 3)
        mc = card()
        ml = vbox(mc, 12, 6)
        r3 = hbox(None, 0, 8)
        r3.addWidget(caption("Memoria del kit"))
        r3.addStretch(1)
        self.lbl_mb = QLabel("—")
        self.lbl_mb.setStyleSheet("font-weight:700")
        r3.addWidget(self.lbl_mb)
        ml.addLayout(r3)
        self.bars = MemoryBars()
        ml.addWidget(self.bars)
        self.lbl_steps = QLabel("")
        self.lbl_steps.setObjectName("Mut")
        self.lbl_steps.setWordWrap(True)
        ml.addWidget(self.lbl_steps)
        side.addWidget(mc, 2)
        side_w = QWidget()
        side_w.setLayout(side)
        side_w.setMaximumWidth(370)
        body.addWidget(side_w, 3)

        self.est_timer = QTimer(self)
        self.est_timer.setSingleShot(True)
        self.est_timer.timeout.connect(self.estimate)
        self._est_gen = 0

    # ------------------------------------------------------------ carga
    def choose(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta con tus WAV de batería")
        if d:
            self.load_folder(d)

    def load_folder(self, path):
        self.carpeta = path
        self.lbl_path.setText(path)
        base = os.path.basename(path.rstrip("\\/"))
        self.e_name.setText(base[:20] or "Mi Kit")
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self.b_build.setEnabled(False)

        def job():
            arch = I.escanear(path)
            return arch, I.agrupar(I.preparar_archivos(arch, self.sl_amb.value() / 100))

        def done(res):
            self.progress.setVisible(False)
            self.archivos, self.grupos = res
            import sonido
            multi = sonido.hay_multimic(self.archivos)
            for w in (self.lbl_amb, self.sl_amb):
                w.setVisible(multi)
            if multi:
                mics = sorted({a.mic for a in self.archivos if a.mic})
                self.ctx.toast("Kit multi-micrófono (" + ", ".join(sonido.MIC_NOMBRE.get(m, m) for m in mics) +
                               "): ajusta «Ambiente» para la mezcla", "INFO", 6000)
            if not self.grupos:
                self.ctx.toast("No encontré golpes WAV en esa carpeta.", "AVISO")
                return
            self._fill_tree()
            self.auto()
            exc = sum(1 for a in self.archivos if a.excluido)
            self.ctx.toast(f"{len(self.archivos) - exc} golpes en {len(self.grupos)} grupos"
                           + (f" · {exc} loops/demos ignorados" if exc else ""), "OK", 4500)

        self.ctx.run_bg(job, done, lambda: self.progress.setVisible(False))

    def _fill_tree(self):
        self.tree.clear()
        for gi, g in enumerate(self.grupos):
            top = QTreeWidgetItem([f"{g.nombre}  ·  {I.PIEZAS[g.tipo][0]}  ({len(g.archivos)})"])
            top.setForeground(0, q("gold"))
            top.setData(0, Qt.ItemDataRole.UserRole, (gi, 0))
            for vi, a in enumerate(g.archivos):
                ch = "estéreo" if a.canales == 2 else "mono"
                it = QTreeWidgetItem([f"{a.nombre}   {a.dur:.2f}s · {ch}"])
                it.setData(0, Qt.ItemDataRole.UserRole, (gi, vi))
                it.setToolTip(0, a.rel)
                top.addChild(it)
            self.tree.addTopLevelItem(top)
        exc = [a for a in self.archivos if a.excluido]
        if exc:
            top = QTreeWidgetItem([f"Ignorados ({len(exc)})"])
            top.setForeground(0, q("mut"))
            for a in exc:
                it = QTreeWidgetItem([f"{a.nombre} — {a.excluido}"])
                it.setForeground(0, q("dim"))
                top.addChild(it)
            self.tree.addTopLevelItem(top)

    # ------------------------------------------------------------ deshacer
    def _snap(self):
        import dataclasses
        self._undo.append([dataclasses.replace(p) for p in self.piezas])
        del self._undo[:-30]
        self._redo.clear()

    def undo(self):
        import dataclasses
        if not self._undo:
            self.ctx.toast("No hay nada que deshacer.", "INFO", 1800)
            return
        self._redo.append([dataclasses.replace(p) for p in self.piezas])
        self.piezas = self._undo.pop()
        self.refresh()
        self.ctx.toast("Deshecho", "INFO", 1500)

    def redo(self):
        import dataclasses
        if not self._redo:
            self.ctx.toast("No hay nada que rehacer.", "INFO", 1800)
            return
        self._undo.append([dataclasses.replace(p) for p in self.piezas])
        self.piezas = self._redo.pop()
        self.refresh()
        self.ctx.toast("Rehecho", "INFO", 1500)

    def auto(self):
        if not self.grupos:
            return
        if self.piezas:
            self._snap()
        self.piezas = I.auto_kit(self.grupos, self.chk_gm.isChecked())
        self.refresh()

    # ------------------------------------------------------------ tabla
    def refresh(self, keep_row=None):
        self._loading = True
        self.piezas.sort(key=lambda p: p.nota)
        self.tbl.setRowCount(0)
        for r, p in enumerate(self.piezas):
            self.tbl.insertRow(r)
            grip = QTableWidgetItem("⠿")
            grip.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            grip.setForeground(q("mut"))
            grip.setToolTip("Arrastra hasta una tecla del piano para mover esta pieza")
            self.tbl.setItem(r, 0, grip)
            chk = QCheckBox()
            chk.setChecked(p.usar)
            chk.toggled.connect(lambda v, p=p: self._set(p, "usar", v))
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(8, 0, 0, 0)
            l.addWidget(chk)
            self.tbl.setCellWidget(r, 1, w)
            cb = QComboBox()
            for n in NOTAS:
                cb.addItem(I.nombre_tecla(n), n)
            cb.setCurrentIndex(NOTAS.index(p.nota) if p.nota in NOTAS else 0)
            cb.currentIndexChanged.connect(lambda i, p=p: self.move(p, NOTAS[i]))
            self.tbl.setCellWidget(r, 2, cb)
            ct = QComboBox()
            for t in I.TIPOS:
                ct.addItem(I.PIEZAS[t][0], t)
            ct.setCurrentIndex(I.TIPOS.index(p.tipo))
            ct.currentIndexChanged.connect(lambda i, p=p: self._set(p, "tipo", I.TIPOS[i]))
            self.tbl.setCellWidget(r, 3, ct)
            cg = QComboBox()
            for g in self.grupos:
                cg.addItem(f"{g.nombre} ({len(g.archivos)})")
            cg.setCurrentIndex(self.grupos.index(p.grupo) if p.grupo in self.grupos else 0)
            cg.currentIndexChanged.connect(lambda i, p=p: self._set_group(p, i))
            if p.copia_de is not None:
                cg.setToolTip(f"Reutiliza la muestra de {I.nombre_tecla(p.copia_de)} (no ocupa memoria extra)")
            self.tbl.setCellWidget(r, 4, cg)
            sv = QSpinBox()
            sv.setRange(1, max(1, len(p.grupo.archivos)))
            sv.setValue(p.version + 1)
            sv.setToolTip("Versión del golpe dentro del grupo")
            sv.valueChanged.connect(lambda v, p=p: self._set(p, "version", v - 1))
            self.tbl.setCellWidget(r, 5, sv)
            sc = QSpinBox()
            sc.setRange(1, max(1, min(5, len(p.grupo.archivos))))
            sc.setValue(p.capas)
            sc.setToolTip("Capas de velocidad: golpes suaves y fuertes distintos")
            sc.valueChanged.connect(lambda v, p=p: self._set(p, "capas", v))
            self.tbl.setCellWidget(r, 6, sc)
            svr = QSpinBox()
            svr.setRange(1, max(1, min(3, len(p.grupo.archivos))))
            svr.setValue(p.variacion)
            svr.setToolTip("Variación humana: alterna hasta 3 versiones del golpe según la velocidad\n"
                           "(el PSR no tiene round robin real; esto lo aproxima y ocupa más memoria)")
            svr.valueChanged.connect(lambda v, p=p: self._set(p, "variacion", v))
            self.tbl.setCellWidget(r, 7, svr)
            cst = QComboBox()
            cst.addItems(["Auto", "Sí", "No"])
            cst.setCurrentIndex(0 if p.estereo is None else (1 if p.estereo else 2))
            cst.setToolTip("Estéreo real (solo si el WAV es estéreo). Ocupa el doble de memoria.")
            cst.currentIndexChanged.connect(lambda i, p=p: self._set(p, "estereo", [None, True, False][i]))
            if all(a.canales == 1 for a in p.grupo.archivos):
                cst.setEnabled(False)
            self.tbl.setCellWidget(r, 8, cst)
            sa = QSpinBox()
            sa.setRange(-12, 12)
            sa.setValue(p.afinacion)
            sa.valueChanged.connect(lambda v, p=p: self._set(p, "afinacion", v, est=False))
            self.tbl.setCellWidget(r, 9, sa)
            bp = QPushButton()
            bp.setIcon(icon("play", "gold", 14))
            bp.setObjectName("Ghost")
            bp.setCursor(Qt.CursorShape.PointingHandCursor)
            bp.clicked.connect(lambda _=False, p=p: self.play(p))
            self.tbl.setCellWidget(r, 10, bp)
        self._loading = False
        self.piano.set_keys({p.nota: ("OK" if p.usar else "INFO") for p in self.piezas})
        self.piano.labels = {}
        n_on = sum(p.usar for p in self.piezas)
        self.lbl_count.setText(f"{n_on} teclas")
        self.b_build.setEnabled(n_on > 0)
        if keep_row is not None and self.piezas:
            self.tbl.selectRow(min(keep_row, len(self.piezas) - 1))
        self._schedule_estimate()

    def _set(self, p, attr, val, est=True):
        if self._loading:
            return
        self._snap()
        setattr(p, attr, val)
        if attr == "tipo" or attr == "usar":
            self.piano.set_keys({x.nota: ("OK" if x.usar else "INFO") for x in self.piezas})
        if attr in ("version", "afinacion", "capas") and attr != "capas":
            p.copia_de = None if attr == "version" else p.copia_de
        if est:
            self._schedule_estimate()

    def _set_group(self, p, i):
        if self._loading:
            return
        self._snap()
        p.grupo = self.grupos[i]
        p.version = 0
        p.capas = 1
        p.copia_de = None
        p.tipo = p.grupo.tipo
        self.refresh(keep_row=self.piezas.index(p))

    def move(self, p, nota):
        """Mueve la pieza a otra tecla; si estaba ocupada, intercambia."""
        if self._loading or p.nota == nota:
            return
        self._snap()
        otra = next((x for x in self.piezas if x.nota == nota and x is not p), None)
        if otra is not None:
            otra.nota = p.nota
        p.nota = nota
        self.refresh(keep_row=sorted(self.piezas, key=lambda x: x.nota).index(p))
        self.piano.flash(nota)
        self.ctx.toast(f"{p.nombre} → {I.nombre_tecla(nota)}" + (f"  (intercambiada con {otra.nombre})" if otra else ""), "INFO", 2200)

    def remove_selected(self):
        r = self.tbl.currentRow()
        if 0 <= r < len(self.piezas):
            self._snap()
            del self.piezas[r]
            self.refresh(keep_row=r)

    def add_from_tree(self, nota=None):
        it = self.tree.currentItem()
        if it is None or it.data(0, Qt.ItemDataRole.UserRole) is None:
            self.ctx.toast("Selecciona un archivo o grupo en la lista.", "AVISO")
            return
        gi, vi = it.data(0, Qt.ItemDataRole.UserRole)
        self._add(gi, vi, nota)

    def _add(self, gi, vi, nota=None):
        g = self.grupos[gi]
        self._snap()
        usadas = {p.nota for p in self.piezas}
        if nota is None:
            cand = I.PIEZAS[g.tipo][1] + I.PIEZAS["perc"][1] + list(range(27, 88))
            nota = next((n for n in cand if n not in usadas), None)
            if nota is None:
                self.ctx.toast("No quedan teclas libres.", "AVISO")
                return
        else:
            for x in [x for x in self.piezas if x.nota == nota]:
                self.piezas.remove(x)
        p = I.Pieza(nota, g.tipo, g, version=vi)
        self.piezas.append(p)
        self.refresh(keep_row=sorted(self.piezas, key=lambda x: x.nota).index(p))
        self.piano.flash(nota)
        self.ctx.toast(f"{g.nombre} (versión {vi + 1}) → {I.nombre_tecla(nota)}", "OK", 2200)

    def _dropped(self, nota, data):
        if data.startswith("row:"):
            r = int(data[4:])
            if 0 <= r < len(self.piezas):
                self.move(self.piezas[r], nota)
        elif data.startswith("file:"):
            _, gi, vi = data.split(":")
            self._add(int(gi), int(vi), nota)

    def _sel(self):
        r = self.tbl.currentRow()
        if 0 <= r < len(self.piezas):
            self.piano.selected = self.piezas[r].nota
            self.piano.update()

    def _piano_click(self, n, _y):
        for r, p in enumerate(self.piezas):
            if p.nota == n:
                self.tbl.selectRow(r)
                self.play(p)
                return

    # ------------------------------------------------------------ audio
    def _play_x(self, x):
        if x is None or not len(x):
            return
        x = x if x.shape[1] == 2 else np.repeat(x, 2, axis=1)
        try:
            self.ctx.audio.play(x.astype(np.float32))
        except Exception as e:  # noqa: BLE001
            self.ctx.toast(f"Audio: {e}", "ERROR")

    def play(self, p):
        sel = p.seleccion()
        a = sel[-1]
        import sonido
        x = sonido.audio_archivo(a, self.sl_amb.value() / 100)
        if p.afinacion:
            import dsp
            x = dsp.to_rate(x, I.SR * 2 ** (p.afinacion / 12), I.SR)
        self.piano.flash(p.nota)
        self._play_x(x)

    def _tree_play(self, it, _col=0):
        if it is None or it.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        gi, vi = it.data(0, Qt.ItemDataRole.UserRole)
        import sonido
        self._play_x(sonido.audio_archivo(self.grupos[gi].archivos[vi], self.sl_amb.value() / 100))

    # ------------------------------------------------------------ memoria
    def _opts(self):
        return I.OpcionesImport(nombre=self.e_name.text().strip() or "Mi Kit", modelo=self.cb_model.currentText(),
                                estereo_platos=self.chk_st.isChecked(), procesar=False,
                                dinamica_natural=self.chk_nat.isChecked(), ambiente=self.sl_amb.value() / 100,
                                sala=self.sl_sala.value() / 100, nivel_teclado=self.chk_lvl.isChecked())

    # ------------------------------------------------------------ kit desde cero / biblioteca
    def nuevo_vacio(self):
        if self.piezas and QMessageBox.question(self, "PPF Tester", "¿Empezar un kit vacío? Se descarta el kit que estás armando.") \
                != QMessageBox.StandardButton.Yes:
            return
        self.carpeta = ""
        self.archivos, self.grupos, self.piezas = [], [], []
        self._undo.clear()
        self._redo.clear()
        self.e_name.setText("Kit nuevo")
        self.lbl_path.setText("Kit desde cero: añade muestras desde la Biblioteca (botón «Añadir al kit…»).")
        self._fill_tree()
        self.refresh()

    def agregar_archivos(self, paths, tipos=None, nombres=None, nota=None):
        """Añade WAV sueltos (p. ej. de la Biblioteca) al kit, cada uno en una tecla libre de su pieza."""
        tipos, nombres = tipos or {}, nombres or {}

        def job():
            arch = I.escanear(paths)
            for a in arch:
                if a.path in tipos:
                    a.tipo, a.seguro = tipos[a.path], True
                if a.path in nombres:
                    a.nombre = nombres[a.path] + ".wav"
                    a.base = I.base_nombre(a.nombre, a.tipo)
                a.rel = os.path.join("Biblioteca", a.nombre)
            return arch, I.agrupar(arch)

        def done(res):
            arch, grupos = res
            if not grupos:
                self.ctx.toast("Esas muestras no se pudieron leer.", "AVISO")
                return
            self.archivos += arch
            self._snap()
            for g in grupos:
                self.grupos.append(g)
                usadas = {p.nota for p in self.piezas}
                cand = ([nota] if nota is not None else []) + I.PIEZAS[g.tipo][1] + I.PIEZAS["perc"][1] + list(range(27, 88))
                n = next((c for c in cand if c not in usadas), None)
                if n is None:
                    break
                self.piezas.append(I.Pieza(n, g.tipo, g))
            self._fill_tree()
            self.refresh()
            self.ctx.toast(f"{len(grupos)} pieza(s) añadidas al kit", "OK")
        self.ctx.run_bg(job, done)

    def to_library(self):
        it = self.tree.currentItem()
        arch = []
        if it is not None and it.data(0, Qt.ItemDataRole.UserRole) is not None:
            gi, vi = it.data(0, Qt.ItemDataRole.UserRole)
            g = self.grupos[gi]
            arch = g.archivos if it.childCount() else [g.archivos[vi]]
        else:
            arch = [a for g in self.grupos for a in g.archivos]
        if not arch:
            return
        import sonido
        amb = self.sl_amb.value() / 100
        import dataclasses
        listos = [dataclasses.replace(a, x=sonido.audio_archivo(a, amb)) for a in arch]
        n = self.ctx.library.add_archivos(listos, os.path.basename(self.carpeta.rstrip("\\/")) if self.carpeta else "")
        self.ctx.toast(f"{n} muestra(s) nuevas en la Biblioteca" if n else "Ya estaban en la Biblioteca", "OK")

    def _schedule_estimate(self, *_):
        if self.piezas:
            self.est_timer.start(700)

    def estimate(self):
        """Calcula la memoria (sin el procesado, que no cambia el tamaño)."""
        if not self.piezas:
            return
        self._est_gen += 1
        gen = self._est_gen
        import dataclasses
        piezas = [dataclasses.replace(p) for p in self.piezas]
        op = self._opts()

        def done(plan):
            if gen != self._est_gen:
                return
            m = modelos.MODELOS[op.modelo]
            col = C["OK"] if plan.mb <= m.kit_max_mb else C["AVISO"] if plan.mb <= m.memoria_mb else C["ERROR"]
            self.lbl_mb.setText(f"<span style='color:{col}'>{plan.mb:.2f} MB</span>")
            self.bars.set_rows([(n, plan.mb, modelos.MODELOS[n].memoria_mb, st) for n, st, _ in modelos.compatibilidad(plan.mb)])
            self.lbl_steps.setText(("Para que entre en el " + m.nombre + ": " + ", ".join(plan.pasos) + ".") if plan.pasos
                                   else f"Entra sin recortes en el {m.nombre} (≤ {m.kit_max_mb:.0f} MB recomendados por kit).")

        self.ctx.run_bg(lambda: I.planificar(piezas, op), done)

    # ------------------------------------------------------------ crear
    def build(self):
        if not self.piezas:
            return
        nombre = self.e_name.text().strip() or "Mi Kit"
        mod = self.cb_model.currentText().replace("PSR-", "")
        start = os.path.join(os.path.dirname(self.carpeta.rstrip("\\/")) if self.carpeta else "", f"{nombre}_{mod}.ppf")
        out, _ = QFileDialog.getSaveFileName(self, "Guardar kit", start, "Yamaha Expansion Manager (*.ppf)")
        if not out:
            return
        op = self._opts()
        op.procesar = self.chk_proc.isChecked()
        op.intensidad = self.sl_int.value() / 100
        piezas = list(self.piezas)
        self.b_build.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)

        def job():
            plan = I.planificar(piezas, op)
            pack = I.construir(plan, op, out)
            return plan, pack

        def done(res):
            plan, pack = res
            self.progress.setVisible(False)
            self.b_build.setEnabled(True)
            if pack.errors:
                self.ctx.toast("El archivo creado no pasó la verificación: " + "; ".join(pack.errors), "ERROR", 8000)
                return
            self.ctx.add_recent(out)
            self.ctx.toast(f"Kit creado: {os.path.basename(out)} · {plan.mb:.2f} MB", "OK", 5000)
            self.ctx.open_file(out)

        self.ctx.run_bg(job, done, lambda: (self.progress.setVisible(False), self.b_build.setEnabled(True)))
