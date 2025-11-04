
# ------------------------------
# ui/main_window.py
# ------------------------------
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, List
from PySide6 import QtCore, QtGui, QtWidgets

from models import APP_TITLE, Entry, EntryStore
from utils.launcher import launch_path
from utils.pixcache import PixCache
from ui.card import CardWidget
from ui.dialogs import EntryDialog

CARD_WIDTH = 240
MAX_COLUMNS = 6  # 最大列数

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)

        self.base_dir = Path(sys.argv[0]).resolve().parent
        self.store = EntryStore(self.base_dir)
        self.pix_cache = PixCache()

        self.apply_light_style()

        # ===== ヘッダー（検索・★のみ・追加）=====
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("検索（名前/パス/タグを含む文字列検索）")
        self.search_edit.textChanged.connect(self.refresh_grid)

        self.only_fav_chk = QtWidgets.QCheckBox("★のみ")
        self.only_fav_chk.stateChanged.connect(self.refresh_grid)

        add_btn = QtWidgets.QPushButton("追加")
        add_btn.clicked.connect(self.add_entry)

        top_bar = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(top_bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)
        h.addWidget(self.search_edit, 2)
        h.addWidget(self.only_fav_chk, 0)
        h.addStretch(1)
        h.addWidget(add_btn, 0)

        tb = QtWidgets.QToolBar()
        tb.setMovable(False)
        self.addToolBar(QtCore.Qt.TopToolBarArea, tb)
        tb.addWidget(top_bar)

        # ===== グリッド =====
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAcceptDrops(True)

        self.center_w = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.center_w)
        self.grid.setContentsMargins(24, 24, 24, 40)
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(22)
        self.grid.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)

        self.scroll.setWidget(self.center_w)
        self.setCentralWidget(self.scroll)

        self.setAcceptDrops(True)
        self.refresh_grid()

    # ===== テーマ =====
    def apply_light_style(self):
        QtWidgets.QApplication.setStyle("Fusion")
        QtWidgets.QApplication.instance().setPalette(QtWidgets.QApplication.style().standardPalette())
        self.setStyleSheet(
            """
            QToolBar { spacing: 8px; padding: 6px; }
            QLineEdit { padding: 8px; border-radius: 10px; }
            QCheckBox { padding: 4px; }
            QPushButton { padding: 6px 12px; border-radius: 8px; }
            """
        )

    # ===== 追加ダイアログ =====
    def add_entry(self):
        dlg = EntryDialog(self)
        if dlg.exec():
            e = dlg.get_value()
            if e:
                self.store.add(e)
                self.refresh_grid()

    # ===== D&Dで追加 =====
    def dragEnterEvent(self, ev: QtGui.QDragEnterEvent):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
        else:
            super().dragEnterEvent(ev)

    def dropEvent(self, ev: QtGui.QDropEvent):
        urls = ev.mimeData().urls()
        added = 0
        for u in urls:
            p = u.toLocalFile()
            if not p:
                continue
            path = Path(p)
            if path.is_dir() or path.suffix.lower() in {".exe", ".bat", ".lnk"} or "://" in p:
                e = Entry(
                    id=str(QtCore.QUuid.createUuid()),
                    name=path.stem,
                    path=str(path),
                    workdir=str(path.parent),
                    tags=[],
                    favorite=False,
                    cover=""
                )
                self.store.add(e)
                added += 1
        if added:
            self.refresh_grid()
        ev.acceptProposedAction()

    # ===== 絞り込み（タグ条件は撤廃）=====
    def filtered_entries(self) -> List[Entry]:
        q = self.search_edit.text().strip().lower()
        only_fav = self.only_fav_chk.isChecked()

        out: List[Entry] = []
        for e in self.store.entries:
            if only_fav and not e.favorite:
                continue
            if q:
                hay = " ".join([
                    e.name.lower(),
                    e.path.lower(),
                    e.args.lower(),
                    ",".join((e.tags or [])).lower()
                ])
                if q not in hay:
                    continue
            out.append(e)
        return out

    # ===== グリッド更新 =====
    def refresh_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        width = CARD_WIDTH
        card_size = QtCore.QSize(width, int(width * 1.5))
        entries = self.filtered_entries()

        avail = max(600, self.scroll.viewport().width() - 32)
        col = max(3, min(MAX_COLUMNS, int(avail / (card_size.width() + 24))))

        r = c = 0
        for e in entries:
            card = CardWidget(e, card_size, self.pix_cache)
            card.clicked.connect(self.on_card_clicked)
            card.editRequested.connect(self.on_edit)
            card.deleteRequested.connect(self.on_delete)
            card.favToggled.connect(self.on_fav)
            card.coverDropped.connect(self.on_cover_dropped)
            self.grid.addWidget(card, r, c)
            c += 1
            if c >= col:
                c = 0
                r += 1

        self.center_w.adjustSize()

    def resizeEvent(self, e: QtGui.QResizeEvent):
        super().resizeEvent(e)
        QtCore.QTimer.singleShot(0, self.refresh_grid)

    # ===== 操作 =====
    def entry_by_id(self, id_: str) -> Optional[Entry]:
        for e in self.store.entries:
            if e.id == id_:
                return e
        return None

    def on_card_clicked(self, id_: str):
        e = self.entry_by_id(id_)
        if not e:
            return
        ok = launch_path(e.path, e.args, e.workdir)
        if not ok:
            QtWidgets.QMessageBox.warning(self, APP_TITLE, "起動に失敗。パス/権限を確認してね")

    def on_edit(self, id_: str):
        e = self.entry_by_id(id_)
        if not e:
            return
        dlg = EntryDialog(self, e)
        if dlg.exec():
            new_e = dlg.get_value()
            if new_e:
                new_e.favorite = e.favorite
                self.store.update(new_e)
                self.refresh_grid()

    def on_delete(self, id_: str):
        e = self.entry_by_id(id_)
        if not e:
            return
        if QtWidgets.QMessageBox.question(self, APP_TITLE, f"『{e.name}』を削除する？") == QtWidgets.QMessageBox.Yes:
            self.store.delete([e.id])
            self.refresh_grid()

    def on_fav(self, id_: str):
        e = self.entry_by_id(id_)
        if not e:
            return
        e.favorite = not e.favorite
        self.store.update(e)
        self.refresh_grid()

    def on_cover_dropped(self, id_: str, img_path: str):
        e = self.entry_by_id(id_)
        if not e:
            return
        e.cover = img_path
        self.store.update(e)
        self.refresh_grid()
