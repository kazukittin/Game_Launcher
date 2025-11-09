"""Data models and persistence for the launcher."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

APP_TITLE = "Card Launcher"
SETTINGS_FILE = "settings.json"


class Game(BaseModel):
    """Application/game entry managed by the launcher."""

    id: str
    name: str
    exec_path: str
    args: Optional[str] = None
    working_dir: Optional[str] = None
    favorite: bool = False
    tags: List[str] = Field(default_factory=list)
    cover: Optional[str] = None
    kind: Literal["exe", "lnk", "steam", "epic"] = "exe"
    steam_appid: Optional[str] = None
    epic_appname: Optional[str] = None
    run_as_admin: bool = False
    fallback_exe: Optional[str] = None

    class Config:
        validate_assignment = True

    def display_tags(self) -> str:
        return ",".join(self.tags)

    def clone(self, **updates: Any) -> "Game":
        if hasattr(self, "model_copy"):
            return getattr(self, "model_copy")(update=updates)
        return getattr(self, "copy")(update=updates)


class AppSettings(BaseModel):
    dark: bool = True
    click_to_launch: bool = True
    sort: str = "created"
    games: List[Game] = Field(default_factory=list)

    class Config:
        validate_assignment = True


class SettingsStore:
    """Persist and mutate launcher settings/games."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.settings_path = base_dir / SETTINGS_FILE
        self.settings = self._load()

    # ----- Persistence -------------------------------------------------
    def _load(self) -> AppSettings:
        if self.settings_path.exists():
            try:
                data = self.settings_path.read_text(encoding="utf-8")
                if hasattr(AppSettings, "model_validate_json"):
                    return AppSettings.model_validate_json(data)
                return AppSettings.parse_raw(data)  # type: ignore[attr-defined]
            except (OSError, ValidationError):
                pass
        return AppSettings()

    def save(self) -> None:
        if hasattr(self.settings, "model_dump_json"):
            payload = self.settings.model_dump_json(indent=2, ensure_ascii=False)
        else:
            payload = self.settings.json(indent=2, ensure_ascii=False)  # type: ignore[attr-defined]
        self.settings_path.write_text(payload, encoding="utf-8")

    # ----- Game access -------------------------------------------------
    @property
    def games(self) -> List[Game]:
        return self.settings.games

    def add(self, game: Game) -> None:
        self.settings.games.append(game)
        self.save()

    def add_many(self, games: Iterable[Game]) -> int:
        added = 0
        for game in games:
            if not self.contains(game):
                self.settings.games.append(game)
                added += 1
        if added:
            self.save()
        return added

    def update(self, updated: Game) -> None:
        for idx, game in enumerate(self.settings.games):
            if game.id == updated.id:
                self.settings.games[idx] = updated
                self.save()
                break

    def delete(self, ids: Iterable[str]) -> None:
        ids_set = set(ids)
        self.settings.games = [g for g in self.settings.games if g.id not in ids_set]
        self.save()

    def contains(self, candidate: Game) -> bool:
        key = discovery_key(candidate)
        return any(discovery_key(g) == key for g in self.settings.games)

    def by_id(self, game_id: str) -> Optional[Game]:
        for game in self.settings.games:
            if game.id == game_id:
                return game
        return None

    def all_tags(self) -> List[str]:
        tags = {tag for game in self.settings.games for tag in game.tags}
        return sorted(tags)


def discovery_key(game: Game) -> tuple[str, str]:
    if game.kind == "steam" and game.steam_appid:
        return ("steam", game.steam_appid)
    if game.kind == "epic" and game.epic_appname:
        return ("epic", game.epic_appname)
    return ("path", game.exec_path.lower())


__all__ = [
    "APP_TITLE",
    "Game",
    "AppSettings",
    "SettingsStore",
    "discovery_key",
]
