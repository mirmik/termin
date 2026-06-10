#!/usr/bin/env python3
"""Check all Slang shader sources for backend-specific annotations.

Target architecture: shader source is clean Slang — no [[vk::...]],
no bare register(...) without semantic justification.

Exits 0 if clean, 1 if violations found.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Patterns that must NOT appear in .slang files
FORBIDDEN = [
    (r"\[\[vk::", "[[vk::...]] — Vulkan-specific annotation"),
]

# Warning patterns — should be reviewed
WARNINGS = [
    (r"\bregister\s*\(", "register(...) — D3D/HLSL register syntax, prefer clean declarations"),
]


def scan_file(filepath: Path) -> list[tuple[str, int, str]]:
    """Returns list of (severity, lineno, message)."""
    issues = []
    try:
        text = filepath.read_text()
    except Exception as e:
        return [("ERROR", 0, f"cannot read: {e}")]

    for lineno, line in enumerate(text.splitlines(), 1):
        for pattern, msg in FORBIDDEN:
            if re.search(pattern, line):
                issues.append(("FORBIDDEN", lineno, msg))
        for pattern, msg in WARNINGS:
            if re.search(pattern, line):
                issues.append(("WARNING", lineno, msg))
    return issues


def main() -> int:
    slang_files = list(ROOT.rglob("*.slang"))
    # Exclude build and .venv dirs
    slang_files = [
        f for f in slang_files
        if "build" not in f.parts
        and ".venv" not in f.parts
        and "thirdparty" not in f.parts
        and "site-packages" not in f.parts
    ]

    if not slang_files:
        print("No .slang files found.")
        return 0

    total_issues = 0
    forbidden_count = 0
    for fpath in sorted(slang_files):
        issues = scan_file(fpath)
        if issues:
            rel = fpath.relative_to(ROOT)
            print(f"\n{rel}:")
            for severity, lineno, msg in issues:
                print(f"  {severity:9s}  line {lineno}: {msg}")
                total_issues += 1
                if severity == "FORBIDDEN":
                    forbidden_count += 1

    print(f"\n=== Summary ===")
    print(f"  Files scanned: {len(slang_files)}")
    print(f"  Issues: {total_issues} ({forbidden_count} forbidden)")

    if forbidden_count > 0:
        print("FAIL: forbidden annotations found.")
        return 1
    if total_issues > 0:
        print("WARN: warnings found (review recommended).")
    else:
        print("PASS: all Slang sources are clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
