#!/usr/bin/env python3
"""Find files exceeding a line-count threshold in the project.

Usage:
    python scripts/find-long-files.py [--threshold N] [--exclude GLOB] [dir]

Defaults:
    threshold  2000
    dir        project root
    exclude    .git, node_modules, __pycache__, .venv, build, dist, thirdparty, termin-thirdparty
"""

import argparse
import os
import sys
from pathlib import Path


DEFAULT_THRESHOLD = 2000
DEFAULT_EXCLUDES = (
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "build",
    "dist",
    "thirdparty",
    "termin-thirdparty",
)


def count_lines(path: Path) -> int:
    """Count lines in a file, skipping binary files."""
    try:
        with open(path, "rb") as f:
            count = 0
            for _ in f:
                count += 1
            return count
    except (PermissionError, IsADirectoryError):
        return 0
    except UnicodeDecodeError:
        return 0


def should_skip(dirname: str, excludes: tuple) -> bool:
    return dirname in excludes or dirname.endswith(".pyc")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find files with more than N lines"
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to scan (default: project root)",
    )
    parser.add_argument(
        "-t", "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Minimum line count (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "-e", "--exclude",
        action="append",
        default=list(DEFAULT_EXCLUDES),
        help="Directory name to exclude (may be repeated)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    excludes = tuple(args.exclude)
    results: list[tuple[Path, int]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if not should_skip(d, excludes)]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.suffix in (".pyc", ".png"):
                continue
            lines = count_lines(fpath)
            if lines >= args.threshold:
                results.append((fpath, lines))

    # Sort by line count descending
    results.sort(key=lambda x: x[1], reverse=True)

    if not results:
        print(f"No files with >= {args.threshold} lines found.")
        return

    print(f"Files with >= {args.threshold} lines:\n")
    rel_root = root
    for fpath, lines in results:
        rel = fpath.relative_to(rel_root)
        print(f"  {lines:>6}  {rel}")

    print(f"\nTotal: {len(results)} file(s)")


if __name__ == "__main__":
    main()
