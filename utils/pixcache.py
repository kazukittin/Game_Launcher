
# ------------------------------
# utils/pixcache.py
# ------------------------------
from __future__ import annotations
from typing import Tuple, Optional
from PySide6 import QtGui

class PixCache:
    def __init__(self):
        self._cache: dict[Tuple[str, int, int], QtGui.QPixmap] = {}
    def get(self, key: Tuple[str, int, int]) -> Optional[QtGui.QPixmap]:
        return self._cache.get(key)
    def put(self, key: Tuple[str, int, int], pix: QtGui.QPixmap):
        self._cache[key] = pix
