#!/usr/bin/env python3
"""Discover and remove generated repository artifacts on every host OS."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Iterable


ARTIFACT_DIRECTORY_NAMES = ("build", "build_win", "dist", "install", "install_win")
PYTHON_CACHE_DIRECTORY_NAMES = ("__pycache__", ".pytest_cache")
PRUNED_DIRECTORY_NAMES = {".git", ".venv", "termin-thirdparty"}


def _is_directory_or_link(path: Path) -> bool:
    return path.is_dir() or path.is_symlink()


def _walk_source_tree(root: Path) -> Iterable[tuple[Path, list[str], list[str]]]:
    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directory_names[:] = [
            name
            for name in directory_names
            if name not in PRUNED_DIRECTORY_NAMES
            and name not in ARTIFACT_DIRECTORY_NAMES
            and name != "sdk"
            and not (current_path == root and name.startswith("sdk-"))
        ]
        yield current_path, directory_names, file_names


def _project_roots(root: Path) -> tuple[set[Path], set[Path]]:
    python_roots = {root}
    dotnet_roots: set[Path] = set()
    for current, _directory_names, file_names in _walk_source_tree(root):
        if "pyproject.toml" in file_names:
            python_roots.add(current)
        if any(name.endswith(".csproj") for name in file_names):
            dotnet_roots.add(current)
    return python_roots, dotnet_roots


def _sdk_prefixes(root: Path) -> set[Path]:
    prefixes = {root / "sdk"}
    profiles = root / "build-system" / "sdk-profiles.json"
    try:
        document = json.loads(profiles.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return prefixes
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"failed to read SDK profile inventory {profiles}: {error}") from error

    profile_values = document.get("profiles", document)
    if isinstance(profile_values, dict):
        iterable = profile_values.values()
    elif isinstance(profile_values, list):
        iterable = profile_values
    else:
        raise RuntimeError(f"SDK profile inventory has invalid shape: {profiles}")
    for profile in iterable:
        if not isinstance(profile, dict):
            continue
        prefix = profile.get("sdk_prefix")
        if isinstance(prefix, str) and prefix and Path(prefix).name == prefix:
            prefixes.add(root / prefix)
    return prefixes


def collect_clean_targets(
    root: Path,
    *,
    include_sdk: bool,
    system_sdk: Path | None = None,
) -> list[Path]:
    root = root.resolve()
    python_roots, dotnet_roots = _project_roots(root)
    targets: set[Path] = set()

    for project_root in python_roots:
        for name in ARTIFACT_DIRECTORY_NAMES:
            candidate = project_root / name
            if _is_directory_or_link(candidate):
                targets.add(candidate)

    for project_root in dotnet_roots:
        for name in ("bin", "obj"):
            candidate = project_root / name
            if _is_directory_or_link(candidate):
                targets.add(candidate)

    for current, directory_names, _file_names in _walk_source_tree(root):
        retained_names: list[str] = []
        for name in directory_names:
            candidate = current / name
            if name in PYTHON_CACHE_DIRECTORY_NAMES or name.endswith(".egg-info"):
                targets.add(candidate)
            else:
                retained_names.append(name)
        directory_names[:] = retained_names

    if include_sdk:
        for candidate in _sdk_prefixes(root):
            if _is_directory_or_link(candidate):
                targets.add(candidate)
        if system_sdk is not None and _is_directory_or_link(system_sdk):
            targets.add(system_sdk)

    return sorted(targets, key=lambda path: (-len(str(path)), str(path)))


def _default_system_sdk() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "termin-sdk"
        return Path.home() / "AppData" / "Local" / "termin-sdk"
    return Path("/opt/termin")


def _remove_target(target: Path, *, root: Path, system_sdk: Path) -> bool:
    lexical_target = Path(os.path.abspath(target))
    lexical_root = Path(os.path.abspath(root))
    lexical_system_sdk = Path(os.path.abspath(system_sdk))
    if lexical_target != lexical_system_sdk:
        try:
            lexical_target.relative_to(lexical_root)
        except ValueError as error:
            raise RuntimeError(f"refusing to remove target outside repository: {target}") from error
        if lexical_target == lexical_root:
            raise RuntimeError(f"refusing to remove repository root: {target}")

    if target.is_symlink():
        target.unlink()
        return True
    if target.is_dir():
        shutil.rmtree(target)
        return True
    return False


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show targets without deleting them")
    parser.add_argument("--include-sdk", action="store_true", help="also remove configured SDK prefixes")
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    root = (args.root or Path(__file__).resolve().parents[2]).resolve()
    system_sdk = _default_system_sdk()
    try:
        targets = collect_clean_targets(root, include_sdk=args.include_sdk, system_sdk=system_sdk)
    except RuntimeError as error:
        print(f"Clean inventory failed: {error}", file=sys.stderr)
        return 1

    if not targets:
        print("Nothing to clean.")
        return 0

    print(f"Targets to clean: {len(targets)}")
    for target in targets:
        print(f"  {target}")

    if args.dry_run:
        print("\nDry run complete. Nothing was deleted.")
        return 0

    removed = 0
    try:
        for target in targets:
            removed += int(_remove_target(target, root=root, system_sdk=system_sdk))
    except OSError as error:
        print(f"Clean failed while removing {target}: {error}", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(f"Clean failed: {error}", file=sys.stderr)
        return 1

    print(f"\nClean complete. Removed: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
