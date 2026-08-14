#!/usr/bin/env python3
"""Validate unique package ownership in the district monorepo."""

from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "build-system" / "districts.json"


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []
    owners: dict[str, str] = {}
    roots: set[str] = set()

    for district in data["districts"]:
        district_id = district["id"]
        root = district["root"]
        if root in roots:
            errors.append(f"duplicate district root: {root}")
        roots.add(root)
        for package in district["packages"]:
            previous = owners.get(package)
            if previous is not None:
                errors.append(
                    f"package {package} is owned by both {previous} and {district_id}"
                )
                continue
            owners[package] = district_id
            migrated = REPO_ROOT / root / package
            legacy = REPO_ROOT / package
            if not migrated.exists():
                errors.append(f"owned package is absent: {root}/{package}")
            if legacy.exists():
                errors.append(f"legacy package root remains: {package}")

    shared_roots = set(data["shared_roots"])
    declared_top_levels = {Path(package).parts[0] for package in owners}
    for path in REPO_ROOT.iterdir():
        if not path.is_dir() or path.name in roots or path.name in shared_roots:
            continue
        if path.name.startswith("termin-") or path.name in {"tcplot", "tcplot-gui-native"}:
            if path.name not in declared_top_levels:
                errors.append(f"undeclared package root: {path.name}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"District ownership OK: {len(owners)} packages, {len(roots)} districts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
