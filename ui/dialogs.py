"""Dialog windows used in the launcher."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from launcher.models import APP_TITLE, Game


class EntryDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, entry: Optional[Game] = None):
        super().__init__(parent)
        self.setWindowTitle("ゲーム編集" if entry else "ゲーム追加")
        self.setModal(True)
        self.resize(580, 360)
        self.entry = entry

        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        self.path_edit = QtWidgets.QLineEdit()
        self.args_edit = QtWidgets.QLineEdit()
        self.workdir_edit = QtWidgets.QLineEdit()
        self.tags_edit = QtWidgets.QLineEdit()
        self.cover_edit = QtWidgets.QLineEdit()
        self.fallback_edit = QtWidgets.QLineEdit()
        self.run_as_admin_chk = QtWidgets.QCheckBox("管理者として実行")

        def row_with_browse(line_edit: QtWidgets.QLineEdit, caption: str, filt: str = "") -> QtWidgets.QWidget:
            btn = QtWidgets.QPushButton("参照…")
            layout = QtWidgets.QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(line_edit)
            layout.addWidget(btn)
            container = QtWidgets.QWidget()
            container.setLayout(layout)
            if caption == "作業ディレクトリ":
                btn.clicked.connect(lambda: self._browse_dir(line_edit, caption))
            else:
                btn.clicked.connect(lambda: self._browse_file(line_edit, caption, filt))
            return container

        form.addRow("名前", self.name_edit)
        form.addRow("パス", row_with_browse(self.path_edit, "実行ファイル/ショートカット/フォルダ", "Executables/Shortcuts (*.*)"))
        form.addRow("引数", self.args_edit)
        form.addRow("作業ディレクトリ", row_with_browse(self.workdir_edit, "作業ディレクトリ"))
        form.addRow("タグ(カンマ)", self.tags_edit)
        form.addRow("カバー画像", row_with_browse(self.cover_edit, "カバー画像", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.ico)"))
        form.addRow("フォールバックexe", row_with_browse(self.fallback_edit, "フォールバックexe", "Executables (*.exe)"))
        form.addRow("", self.run_as_admin_chk)

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btn_box)

        if entry:
            self.name_edit.setText(entry.name)
            self.path_edit.setText(entry.exec_path)
            self.args_edit.setText(entry.args or "")
            self.workdir_edit.setText(entry.working_dir or "")
            self.tags_edit.setText(", ".join(entry.tags))
            self.cover_edit.setText(entry.cover or "")
            self.fallback_edit.setText(entry.fallback_exe or "")
            self.run_as_admin_chk.setChecked(entry.run_as_admin)

    def _browse_dir(self, target: QtWidgets.QLineEdit, caption: str) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, caption)
        if directory:
            target.setText(directory)

    def _browse_file(self, target: QtWidgets.QLineEdit, caption: str, filt: str = "") -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, caption, "", filt or "All (*.*)")
        if file_path:
            target.setText(file_path)
            if target is self.path_edit and not self.name_edit.text().strip():
                self.name_edit.setText(Path(file_path).stem)

    def _detect_kind(self, exec_path: str) -> str:
        if exec_path.startswith("steam://"):
            return "steam"
        if exec_path.startswith("com.epicgames.launcher://"):
            return "epic"
        if exec_path.lower().endswith(".lnk"):
            return "lnk"
        return "exe"

    def get_value(self) -> Optional[Game]:
        name = self.name_edit.text().strip()
        exec_path = self.path_edit.text().strip()
        args = self.args_edit.text().strip() or None
        working_dir = self.workdir_edit.text().strip() or None
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        cover = self.cover_edit.text().strip() or None
        fallback = self.fallback_edit.text().strip() or None
        run_as_admin = self.run_as_admin_chk.isChecked()

        if not name or not exec_path:
            QtWidgets.QMessageBox.warning(self, APP_TITLE, "名前とパスは必須だよ")
            return None

        kind = self._detect_kind(exec_path)
        if self.entry:
            game = Game(
                id=self.entry.id,
                name=name,
                exec_path=exec_path,
                args=args,
                working_dir=working_dir,
                tags=tags,
                cover=cover,
                kind=kind,
                run_as_admin=run_as_admin,
                fallback_exe=fallback,
                favorite=self.entry.favorite,
                steam_appid=self.entry.steam_appid,
                epic_appname=self.entry.epic_appname,
            )
        else:
            game = Game(
                id=str(QtCore.QUuid.createUuid()),
                name=name,
                exec_path=exec_path,
                args=args,
                working_dir=working_dir,
                tags=tags,
                cover=cover,
                kind=kind,
                run_as_admin=run_as_admin,
                fallback_exe=fallback,
            )
        return game
