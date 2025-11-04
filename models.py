
# ------------------------------
# models.py
# ------------------------------
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

APP_TITLE = "Card Launcher"
DB_FILE = "entries.json"

@dataclass
class Entry:
    id: str
    name: str
    path: str
    args: str = ""
    workdir: str = ""
    favorite: bool = False
    tags: List[str] = None
    cover: str = ""

    def to_dict(self):
        d = asdict(self)
        d["tags"] = self.tags or []
        return d

    @staticmethod
    def from_dict(d: dict) -> "Entry":
        return Entry(
            id=str(d.get("id", "")),
            name=d.get("name", ""),
            path=d.get("path", ""),
            args=d.get("args", ""),
            workdir=d.get("workdir", ""),
            favorite=bool(d.get("favorite", False)),
            tags=list(d.get("tags", [])),
            cover=d.get("cover", ""),
        )

class EntryStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.db_path = base_dir / DB_FILE
        self.entries: List[Entry] = []
        self._load()

    def _load(self):
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
                self.entries = [Entry.from_dict(x) for x in data.get("entries", [])]
            except Exception:
                self.entries = []
        else:
            self.entries = []

    def _save(self):
        payload = {"entries": [e.to_dict() for e in self.entries]}
        self.db_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, e: Entry):
        self.entries.append(e)
        self._save()

    def update(self, e: Entry):
        for i, old in enumerate(self.entries):
            if old.id == e.id:
                self.entries[i] = e
                break
        self._save()

    def delete(self, ids: List[str]):
        self.entries = [e for e in self.entries if e.id not in ids]
        self._save()

    def all_tags(self) -> List[str]:
        # kept for compatibility; not used by UI
        tags = set()
        for e in self.entries:
            for t in (e.tags or []):
                tags.add(t)
        return sorted(tags)
