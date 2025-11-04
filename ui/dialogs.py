
# ------------------------------
# ui/dialogs.py
# ------------------------------
from __future__ import annotations
from pathlib import Path
from typing import Optional
from PySide6 import QtCore, QtWidgets
from models import Entry, APP_TITLE

class EntryDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, entry: Optional[Entry]=None):
        super().__init__(parent)
        self.setWindowTitle("エントリ編集" if entry else "エントリ追加")
        self.setModal(True)
        self.resize(560, 300)
        self.entry = entry

        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        self.path_edit = QtWidgets.QLineEdit()
        self.args_edit = QtWidgets.QLineEdit()
        self.workdir_edit = QtWidgets.QLineEdit()
        self.tags_edit = QtWidgets.QLineEdit()
        self.cover_edit = QtWidgets.QLineEdit()

        def row_with_browse(line_edit, caption, filt=""):
            btn = QtWidgets.QPushButton("参照…")
            h = QtWidgets.QHBoxLayout(); h.addWidget(line_edit); h.addWidget(btn)
            if filt: btn.clicked.connect(lambda: self._browse_file(line_edit, caption, filt))
            else: btn.clicked.connect(lambda: self._browse_file(line_edit, caption, "All (*.*)"))
            return h

        form.addRow("名前", self.name_edit)
        form.addRow("パス", row_with_browse(self.path_edit, "実行ファイル/ショートカット/フォルダ", "Executables/Shortcuts (*.*)"))
        form.addRow("引数", self.args_edit)
        form.addRow("作業ディレクトリ", row_with_browse(self.workdir_edit, "作業ディレクトリ"))
        form.addRow("タグ(カンマ)", self.tags_edit)
        form.addRow("カバー画像", row_with_browse(self.cover_edit, "カバー画像", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.ico)"))

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept); btn_box.rejected.connect(self.reject)

        lay = QtWidgets.QVBoxLayout(self); lay.addLayout(form); lay.addWidget(btn_box)

        if entry:
            self.name_edit.setText(entry.name)
            self.path_edit.setText(entry.path)
            self.args_edit.setText(entry.args)
            self.workdir_edit.setText(entry.workdir)
            self.tags_edit.setText(", ".join(entry.tags or []))
            self.cover_edit.setText(entry.cover)

    def _browse_file(self, target: QtWidgets.QLineEdit, caption: str, filt: str = ""):
        if caption == "作業ディレクトリ":
            d = QtWidgets.QFileDialog.getExistingDirectory(self, caption)
            if d: target.setText(d)
        else:
            f, _ = QtWidgets.QFileDialog.getOpenFileName(self, caption, "", filt or "All (*.*)")
            if f:
                target.setText(f)
                if target is self.path_edit and not self.name_edit.text().strip():
                    self.name_edit.setText(Path(f).stem)

    def get_value(self) -> Optional[Entry]:
        name = self.name_edit.text().strip(); path = self.path_edit.text().strip()
        args = self.args_edit.text().strip(); workdir = self.workdir_edit.text().strip()
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        cover = self.cover_edit.text().strip()
        if not name or not path:
            QtWidgets.QMessageBox.warning(self, APP_TITLE, "名前とパスは必須だよ"); return None
        if self.entry:
            e = Entry(id=self.entry.id, name=name, path=path, args=args, workdir=workdir,
                      favorite=self.entry.favorite, tags=tags, cover=cover)
        else:
            e = Entry(id=str(QtCore.QUuid.createUuid()), name=name, path=path, args=args,
                      workdir=workdir, favorite=False, tags=tags, cover=cover)
        return e
