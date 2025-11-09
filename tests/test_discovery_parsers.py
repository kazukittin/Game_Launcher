from __future__ import annotations

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launcher import discovery


def test_scan_steam_extracts_appid(tmp_path, monkeypatch):
    steam_root = tmp_path / "Steam"
    steamapps = steam_root / "steamapps"
    manifest_dir = steamapps
    common_dir = steamapps / "common" / "ExampleGame"
    common_dir.mkdir(parents=True)

    manifest_content = (
        '"AppState"\n'
        '{\n'
        '    "appid" "12345"\n'
        '    "name" "Example Game"\n'
        '    "installdir" "ExampleGame"\n'
        '}\n'
    )
    (manifest_dir / "appmanifest_12345.acf").write_text(manifest_content, encoding="utf-8")

    library_content = (
        '"libraryfolders"\n'
        '{\n'
        '    "0"\n'
        '    {\n'
        f'        "path" "{steam_root.as_posix()}"\n'
        '    }\n'
        '}\n'
    )
    (steamapps / "libraryfolders.vdf").write_text(library_content, encoding="utf-8")

    monkeypatch.setattr(discovery, "_steam_registry_paths", lambda: [steam_root])

    results = discovery.scan_steam(max_items=5)
    assert results
    game = results[0]
    assert game["steam_appid"] == "12345"
    assert game["name"] == "Example Game"
    assert game["exec_path"] == "steam://rungameid/12345"


def test_scan_epic_extracts_app_name(tmp_path, monkeypatch):
    manifest_path = tmp_path / "Sample.item"
    payload = {
        "AppName": "ExampleApp",
        "DisplayName": "Example App",
        "InstallLocation": str((tmp_path / "ExampleApp").as_posix()),
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(discovery, "_epic_manifest_paths", lambda: [manifest_path])

    results = discovery.scan_epic(max_items=5)
    assert results
    app = results[0]
    assert app["epic_appname"] == "ExampleApp"
    assert app["name"] == "Example App"
    assert app["exec_path"] == "com.epicgames.launcher://apps/ExampleApp?action=launch"
