
# ------------------------------
# ui/card.py
# ------------------------------
from __future__ import annotations
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets
from utils.pixcache import PixCache

class CardWidget(QtWidgets.QFrame):
    clicked = QtCore.Signal(str)
    editRequested = QtCore.Signal(str)
    deleteRequested = QtCore.Signal(str)
    favToggled = QtCore.Signal(str)
    coverDropped = QtCore.Signal(str, str)

    def __init__(self, entry, size: QtCore.QSize, pix_cache: PixCache):
        super().__init__()
        self.entry = entry
        self.cardSize = size
        self.pix_cache = pix_cache
        self.setObjectName("card")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame#card { border-radius: 12px; background-color: #f2f2f2; }
            QFrame#card:hover { background-color: #eaeaea; }
        """)
        self.shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        self.shadow.setOffset(0, 3)
        self.shadow.setBlurRadius(16)
        self.shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self.shadow)
        self.build_ui()

    def build_ui(self):
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(6,6,6,6); lay.setSpacing(6)
        favBtn = QtWidgets.QToolButton(); favBtn.setText("★" if self.entry.favorite else "☆")
        favBtn.setCursor(QtCore.Qt.PointingHandCursor); favBtn.clicked.connect(lambda: self.favToggled.emit(self.entry.id))
        favBtn.setStyleSheet("color:#d4a017;font-size:16px")
        top = QtWidgets.QHBoxLayout(); top.addWidget(favBtn, 0, QtCore.Qt.AlignLeft); top.addStretch(1)
        menuBtn = QtWidgets.QToolButton(); menuBtn.setText("⋯"); menuBtn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(menuBtn)
        menu.addAction("起動", lambda: self.clicked.emit(self.entry.id))
        menu.addAction("編集", lambda: self.editRequested.emit(self.entry.id))
        menu.addAction("削除", lambda: self.deleteRequested.emit(self.entry.id))
        menu.addAction("カバーを選択…", self.pick_cover)
        menuBtn.setMenu(menu); top.addWidget(menuBtn, 0, QtCore.Qt.AlignRight)
        lay.addLayout(top)

        self.container = QtWidgets.QFrame(); self.container.setObjectName("cardContainer")
        self.container.setStyleSheet("QFrame#cardContainer{border-radius:10px;background:#fff}")
        self.stacked = QtWidgets.QStackedLayout(self.container); self.stacked.setContentsMargins(0,0,0,0)
        self.coverLbl = QtWidgets.QLabel(); self.coverLbl.setFixedWidth(self.cardSize.width()); self.coverLbl.setAlignment(QtCore.Qt.AlignCenter)
        self.coverLbl.setScaledContents(False); self.stacked.addWidget(self.coverLbl)
        self.overlay = QtWidgets.QWidget(); self.overlay.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        ov_l = QtWidgets.QVBoxLayout(self.overlay); ov_l.setContentsMargins(0,0,0,0); ov_l.addStretch(1)
        self.bar = QtWidgets.QFrame(); self.bar.setStyleSheet("background-color: rgba(255,255,255,180); border-bottom-left-radius:10px; border-bottom-right-radius:10px;")
        bar_l = QtWidgets.QHBoxLayout(self.bar); bar_l.setContentsMargins(8,6,8,6)
        self.titleLbl = QtWidgets.QLabel(self.entry.name); self.titleLbl.setStyleSheet("color:#333; font-weight:600;"); self.titleLbl.setWordWrap(True)
        bar_l.addWidget(self.titleLbl); ov_l.addWidget(self.bar); self.stacked.addWidget(self.overlay)
        lay.addWidget(self.container, 0, QtCore.Qt.AlignHCenter)
        self.refresh()

    def refresh(self):
        self.titleLbl.setText(self.entry.name)
        self.set_cover(self.entry.cover)

    def _build_default_pixmap(self, w: int, h: int) -> QtGui.QPixmap:
        key = ("__generated__", w, h)
        cached = self.pix_cache.get(key)
        if cached: return cached
        pix = QtGui.QPixmap(w, h)
        p = QtGui.QPainter(pix)
        p.fillRect(pix.rect(), QtGui.QColor(230,232,237))
        p.setPen(QtGui.QPen(QtGui.QColor(120,120,130)))
        p.drawText(pix.rect(), QtCore.Qt.AlignCenter, "No Cover")
        p.end()
        self.pix_cache.put(key, pix)
        return pix

    def set_cover(self, path: str):
        pix = QtGui.QPixmap()
        if path and Path(path).exists():
            orig_key = (Path(path).as_posix(), -1, -1)
            cached = self.pix_cache.get(orig_key)
            if cached: pix = cached
            else:
                pix.load(path)
                if not pix.isNull(): self.pix_cache.put(orig_key, pix)
        if pix.isNull():
            w = self.cardSize.width(); h = int(w*1.5)
            pix = self._build_default_pixmap(w, h)
        ratio = max(0.1, pix.width()/max(1, pix.height()))
        target_w = self.cardSize.width(); target_h = int(target_w/ratio)
        target_h = max(int(target_w*0.9), min(int(target_w*1.8), target_h))
        self.coverLbl.setFixedSize(target_w, target_h)
        self.container.setFixedSize(target_w, target_h)
        self.overlay.setFixedSize(target_w, target_h)
        scale_key = ((Path(path).as_posix() if path else "__generated__"), target_w, target_h)
        cached_scaled = self.pix_cache.get(scale_key)
        if cached_scaled is None:
            scaled = pix.scaled(self.coverLbl.size(), QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
            self.pix_cache.put(scale_key, scaled); self.coverLbl.setPixmap(scaled)
        else: self.coverLbl.setPixmap(cached_scaled)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.entry.id)
        return super().mousePressEvent(e)

    def dragEnterEvent(self, ev: QtGui.QDragEnterEvent):
        if ev.mimeData().hasUrls(): ev.acceptProposedAction()
        else: super().dragEnterEvent(ev)

    def dropEvent(self, ev: QtGui.QDropEvent):
        urls = ev.mimeData().urls()
        for u in urls:
            p = u.toLocalFile()
            if not p: continue
            if Path(p).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".ico"}:
                self.coverDropped.emit(self.entry.id, p); break
        ev.acceptProposedAction()

    def pick_cover(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "カバー画像を選択", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.ico)")
        if f: self.coverDropped.emit(self.entry.id, f)
