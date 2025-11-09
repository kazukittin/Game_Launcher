"""Main window for the launcher UI."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from launcher import discovery, launch_win
from launcher.models import APP_TITLE, Game, SettingsStore
from ui.card import CardWidget
from ui.dialogs import EntryDialog
from utils.launcher import launch_path
from utils.pixcache import PixCache

LOGGER = logging.getLogger(__name__)

CARD_WIDTH = 240
MAX_COLUMNS = 6


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)

        self.base_dir = Path(sys.argv[0]).resolve().parent
        self.store = SettingsStore(self.base_dir)

        self.pix_cache = PixCache()

        self.apply_light_style()

        # ----- Header -----
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("検索（名前/パス/タグを含む文字列検索）")
        self.search_edit.textChanged.connect(self.refresh_grid)

        self.only_fav_chk = QtWidgets.QCheckBox("★のみ")
        self.only_fav_chk.stateChanged.connect(self.refresh_grid)

        add_btn = QtWidgets.QToolButton()
        add_btn.setText("追加")
        add_btn.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        add_menu = QtWidgets.QMenu(add_btn)
        add_menu.addAction("手動追加", self.add_entry)
        add_menu.addAction("自動スキャン", self.auto_scan)
        add_btn.setMenu(add_menu)

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

        # ----- Grid -----
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

    def apply_light_style(self) -> None:
        QtWidgets.QApplication.setStyle("Fusion")
        QtWidgets.QApplication.instance().setPalette(QtWidgets.QApplication.style().standardPalette())
        self.setStyleSheet(
            """
            QToolBar { spacing: 8px; padding: 6px; }
            QLineEdit { padding: 8px; border-radius: 10px; }
            QCheckBox { padding: 4px; }
            QPushButton, QToolButton { padding: 6px 12px; border-radius: 8px; }
            """
        )

    def add_entry(self) -> None:
        dlg = EntryDialog(self)
        if dlg.exec():
            game = dlg.get_value()
            if game:
                self.store.add(game)
                self.refresh_grid()

    def auto_scan(self) -> None:
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BusyCursor)
        try:
            found = discovery.initial_discovery()
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("Auto discovery failed: %s", exc)
            QtWidgets.QMessageBox.critical(
                self, APP_TITLE, "自動スキャンに失敗しました。ログを確認してください。"
            )
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        games = discovery.merge_discovery(found)
        new_games = []
        for game in games:
            if self.store.contains(game):
                continue
            new_games.append(game.clone(id=str(QtCore.QUuid.createUuid())))
        added = self.store.add_many(new_games)
        if added:
            QtWidgets.QMessageBox.information(self, APP_TITLE, f"{added} 件のゲームを追加しました。")
            self.refresh_grid()
        else:
            QtWidgets.QMessageBox.information(self, APP_TITLE, "新しいゲームは見つかりませんでした。")

    def dragEnterEvent(self, ev: QtGui.QDragEnterEvent) -> None:
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
        else:
            super().dragEnterEvent(ev)

    def dropEvent(self, ev: QtGui.QDropEvent) -> None:
        urls = ev.mimeData().urls()
        added = 0
        for u in urls:
            p = u.toLocalFile()
            if not p:
                continue
            if "://" in p:
                exec_path = p
                name = p
                working_dir = None
                kind = self._detect_kind(exec_path)
            else:
                path = Path(p)
                if not (
                    path.is_dir() or path.suffix.lower() in {".exe", ".bat", ".lnk"}
                ):
                    continue
                exec_path = str(path)
                name = path.stem
                working_dir = str(path.parent)
                kind = self._detect_kind(exec_path)
            game = Game(
                id=str(QtCore.QUuid.createUuid()),
                name=name,
                exec_path=exec_path,
                working_dir=working_dir,
                tags=[],
                cover=None,
                kind=kind,
            )
            self.store.add(game)
            added += 1
        if added:
            self.refresh_grid()
        ev.acceptProposedAction()

    def _detect_kind(self, exec_path: str) -> str:
        if exec_path.startswith("steam://"):
            return "steam"
        if exec_path.startswith("com.epicgames.launcher://"):
            return "epic"
        if exec_path.lower().endswith(".lnk"):
            return "lnk"
        return "exe"

    def filtered_games(self) -> List[Game]:
        query = self.search_edit.text().strip().lower()
        only_fav = self.only_fav_chk.isChecked()
        filtered: List[Game] = []
        for game in self.store.games:
            if only_fav and not game.favorite:
                continue
            if query:
                haystack = " ".join(
                    [
                        game.name.lower(),
                        game.exec_path.lower(),
                        (game.args or "").lower(),
                        ",".join(game.tags).lower(),
                    ]
                )
                if query not in haystack:
                    continue
            filtered.append(game)
        return filtered

    def refresh_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        card_size = QtCore.QSize(CARD_WIDTH, int(CARD_WIDTH * 1.5))
        games = self.filtered_games()

        avail = max(600, self.scroll.viewport().width() - 32)
        cols = max(3, min(MAX_COLUMNS, int(avail / (card_size.width() + 24))))

        r = c = 0
        for game in games:
            card = CardWidget(game, card_size, self.pix_cache)
            card.clicked.connect(self.on_card_clicked)
            card.editRequested.connect(self.on_edit)
            card.deleteRequested.connect(self.on_delete)
            card.favToggled.connect(self.on_fav)
            card.coverDropped.connect(self.on_cover_dropped)
            self.grid.addWidget(card, r, c)
            c += 1
            if c >= cols:
                c = 0
                r += 1

        self.center_w.adjustSize()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self.refresh_grid)

    def entry_by_id(self, game_id: str) -> Optional[Game]:
        return self.store.by_id(game_id)

    def launch_game(self, game: Game) -> bool:
        if sys.platform.startswith("win"):
            status = launch_win.launch(game.exec_path, args=game.args, run_as_admin=game.run_as_admin)
            if status != 0 and game.fallback_exe:
                LOGGER.info("Retrying %s using fallback executable", game.name)
                status = launch_win.launch(game.fallback_exe, args=game.args, run_as_admin=game.run_as_admin)
            return status == 0
        return launch_path(game.exec_path, game.args or "", game.working_dir or "")

    def on_card_clicked(self, game_id: str) -> None:
        game = self.entry_by_id(game_id)
        if not game:
            return
        if not self.launch_game(game):
            QtWidgets.QMessageBox.warning(self, APP_TITLE, "起動に失敗。パス/権限を確認してね")

    def on_edit(self, game_id: str) -> None:
        game = self.entry_by_id(game_id)
        if not game:
            return
        dlg = EntryDialog(self, game)
        if dlg.exec():
            updated = dlg.get_value()
            if updated:
                self.store.update(updated)
                self.refresh_grid()

    def on_delete(self, game_id: str) -> None:
        game = self.entry_by_id(game_id)
        if not game:
            return
        if QtWidgets.QMessageBox.question(self, APP_TITLE, f"『{game.name}』を削除する？") == QtWidgets.QMessageBox.Yes:
            self.store.delete([game.id])
            self.refresh_grid()

    def on_fav(self, game_id: str) -> None:
        game = self.entry_by_id(game_id)
        if not game:
            return
        game.favorite = not game.favorite
        self.store.update(game)
        self.refresh_grid()

    def on_cover_dropped(self, game_id: str, img_path: str) -> None:
        game = self.entry_by_id(game_id)
        if not game:
            return
        game.cover = img_path
        self.store.update(game)
        self.refresh_grid()
