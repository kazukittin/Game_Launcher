"""Discovery helpers for Steam and Epic libraries."""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import Game, discovery_key

_LOGGER = logging.getLogger(__name__)

MAX_DEFAULT_ITEMS = 200

URI_TEMPLATES = {
    "steam": "steam://rungameid/{id}",
    "epic": "com.epicgames.launcher://apps/{name}?action=launch",
}


def _tokenize_vdf(text: str) -> List[tuple[str, Optional[str]]]:
    tokens: List[tuple[str, Optional[str]]] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch in "\r\n\t ":
            i += 1
            continue
        if ch == "/" and i + 1 < length and text[i + 1] == "/":
            # comment until end of line
            i += 2
            while i < length and text[i] not in "\r\n":
                i += 1
            continue
        if ch == '"':
            i += 1
            buf = []
            while i < length:
                ch = text[i]
                if ch == "\\":
                    i += 1
                    if i < length:
                        buf.append(text[i])
                        i += 1
                    continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            tokens.append(("STRING", "".join(buf)))
            continue
        if ch == "{":
            tokens.append(("LBRACE", None))
            i += 1
            continue
        if ch == "}":
            tokens.append(("RBRACE", None))
            i += 1
            continue
        # fallback: bare token
        start = i
        while i < length and text[i] not in "\r\n\t {}":
            i += 1
        tokens.append(("STRING", text[start:i]))
    return tokens


def _parse_tokens(tokens: Iterable[tuple[str, Optional[str]]], start: int = 0) -> tuple[int, Dict[str, Any]]:
    tokens_list = list(tokens)
    length = len(tokens_list)
    idx = start
    result: Dict[str, Any] = {}
    current_key: Optional[str] = None

    while idx < length:
        token_type, value = tokens_list[idx]
        if token_type == "STRING":
            if current_key is None:
                current_key = value or ""
            else:
                result[current_key] = value
                current_key = None
            idx += 1
            continue
        if token_type == "LBRACE":
            idx, nested = _parse_tokens(tokens_list, idx + 1)
            if current_key is not None:
                result[current_key] = nested
                current_key = None
            continue
        if token_type == "RBRACE":
            return idx + 1, result
        idx += 1
    return idx, result


def parse_vdf(text: str) -> Dict[str, Any]:
    tokens = _tokenize_vdf(text)
    if not tokens:
        return {}
    _, data = _parse_tokens(tokens)
    return data


def _read_vdf(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        _LOGGER.error("Failed to read VDF %s: %s", path, exc)
        return {}
    return parse_vdf(text)


def _steam_registry_paths() -> List[Path]:
    paths: List[Path] = []
    if not sys.platform.startswith("win"):
        return paths
    try:
        import winreg  # type: ignore
    except ImportError:  # pragma: no cover - depends on platform
        return paths

    registry_keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\\Valve\\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Valve\\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Valve\\Steam", "InstallPath"),
    ]
    for hive, key, value_name in registry_keys:
        try:
            with winreg.OpenKey(hive, key) as opened:
                path, _ = winreg.QueryValueEx(opened, value_name)
                if path:
                    paths.append(Path(path))
        except OSError:
            continue
    return paths


def _library_paths(steam_root: Path) -> List[Path]:
    library_paths: List[Path] = []
    library_file = steam_root / "steamapps" / "libraryfolders.vdf"
    if not library_file.exists():
        return library_paths
    data = _read_vdf(library_file)
    root = data.get("libraryfolders") if isinstance(data, dict) else {}
    if not root:
        root = data
    if isinstance(root, dict):
        for value in root.values():
            if isinstance(value, dict):
                candidate = value.get("path") or value.get("libraryfolderpath")
                if candidate:
                    library_paths.append(Path(candidate))
            elif isinstance(value, str):
                library_paths.append(Path(value))
    return library_paths


def _guess_fallback_exe(folder: Path) -> Optional[str]:
    if not folder.exists() or not folder.is_dir():
        return None
    exe_candidates = sorted(folder.glob("*.exe"))
    if not exe_candidates:
        try:
            children = list(folder.iterdir())
        except OSError as exc:
            _LOGGER.error("Failed to enumerate %s: %s", folder, exc)
            return None
        for child in children:
            if child.is_dir():
                nested = sorted(child.glob("*.exe"))
                if nested:
                    return str(nested[0])
        return None
    return str(exe_candidates[0])


def scan_steam(max_items: int = MAX_DEFAULT_ITEMS) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen = set()

    roots = _steam_registry_paths()
    for root in roots:
        steamapps_dir = root / "steamapps"
        libraries = [steamapps_dir]
        libraries.extend(Path(path) / "steamapps" for path in _library_paths(root))

        for library in libraries:
            if not library.exists():
                continue
            for manifest in sorted(library.glob("appmanifest_*.acf")):
                if len(results) >= max_items:
                    return results
                data = _read_vdf(manifest)
                app_state = data.get("AppState") if isinstance(data, dict) else None
                node = app_state if isinstance(app_state, dict) else data
                if not isinstance(node, dict):
                    continue
                appid = str(node.get("appid", "")).strip()
                name = (node.get("name") or node.get("UserConfig", {}).get("name")) if isinstance(node, dict) else None
                install_dir = node.get("installdir") if isinstance(node, dict) else None
                if not (appid and name and install_dir):
                    continue
                key = ("steam", appid)
                if key in seen:
                    continue
                seen.add(key)
                install_path = library / "common" / install_dir
                fallback = _guess_fallback_exe(install_path)
                results.append(
                    {
                        "name": name,
                        "exec_path": URI_TEMPLATES["steam"].format(id=appid),
                        "kind": "steam",
                        "steam_appid": appid,
                        "tags": ["Steam"],
                        "fallback_exe": fallback,
                    }
                )
    return results


def _epic_manifest_paths() -> List[Path]:
    base = Path(os.environ.get("PROGRAMDATA", r"C:\\ProgramData"))
    manifests_dir = base / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if manifests_dir.exists():
        return sorted(manifests_dir.glob("*.json")) + sorted(manifests_dir.glob("*.item")) + sorted(
            manifests_dir.glob("*.manifest")
        )
    return []


def scan_epic(max_items: int = MAX_DEFAULT_ITEMS) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for manifest_path in _epic_manifest_paths():
        if len(results) >= max_items:
            break
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, json.JSONDecodeError) as exc:
            _LOGGER.error("Failed to parse Epic manifest %s: %s", manifest_path, exc)
            continue
        app_name = data.get("AppName") or data.get("CatalogItemId")
        display_name = data.get("DisplayName") or data.get("AppTitle")
        install_location = data.get("InstallLocation") or data.get("InstallFolder")
        if not (app_name and display_name):
            continue
        fallback = _guess_fallback_exe(Path(install_location)) if install_location else None
        results.append(
            {
                "name": display_name,
                "exec_path": URI_TEMPLATES["epic"].format(name=app_name),
                "kind": "epic",
                "epic_appname": app_name,
                "tags": ["Epic"],
                "fallback_exe": fallback,
            }
        )
    return results


def initial_discovery(limit: int = 300) -> List[Dict[str, Any]]:
    steam = scan_steam(limit)
    remaining = max(0, limit - len(steam))
    epic = scan_epic(remaining)

    combined = steam + epic
    deduped: Dict[tuple[str, str], Dict[str, Any]] = {}
    for entry in combined:
        key = (entry.get("kind", "path"), entry.get("steam_appid") or entry.get("epic_appname") or entry.get("exec_path"))
        if key not in deduped:
            deduped[key] = entry
    return list(deduped.values())


def to_game(entry: Dict[str, Any]) -> Game:
    game = Game(
        id=entry.get("id") or entry.get("steam_appid") or entry.get("epic_appname") or entry["exec_path"],
        name=entry["name"],
        exec_path=entry["exec_path"],
        kind=entry.get("kind", "exe"),
        steam_appid=entry.get("steam_appid"),
        epic_appname=entry.get("epic_appname"),
        tags=entry.get("tags", []),
        fallback_exe=entry.get("fallback_exe"),
    )
    return game


def merge_discovery(games: Iterable[Dict[str, Any]]) -> List[Game]:
    new_games = [to_game(entry) for entry in games]
    unique: Dict[tuple[str, str], Game] = {}
    for game in new_games:
        unique[discovery_key(game)] = game
    return list(unique.values())


__all__ = [
    "scan_steam",
    "scan_epic",
    "initial_discovery",
    "parse_vdf",
    "merge_discovery",
    "to_game",
]
