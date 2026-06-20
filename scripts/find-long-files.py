#!/usr/bin/env python3
"""Find files exceeding a line-count threshold in the project.

Usage:
    python scripts/find-long-files.py [--threshold N] [--fail] [dir]

Defaults:
    threshold  2000
    extensions .c, .cc, .cpp, .cxx, .h, .hh, .hpp, .hxx, .cs, .py
    dir        project root
    exclude    .git, node_modules, __pycache__, .venv, build, dist,
               thirdparty, termin-thirdparty, sdk,
               termin-csharp/Termin.Native/Generated
"""

import argparse
import os
import sys
from pathlib import Path


DEFAULT_THRESHOLD = 2000
DEFAULT_EXTENSIONS = (
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".py",
)
DEFAULT_EXCLUDES = (
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "build",
    "dist",
    "thirdparty",
    "termin-thirdparty",
    "sdk",
    "termin-csharp/Termin.Native/Generated",
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


def normalize_exclude(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def normalize_extension(value: str) -> str:
    value = value.strip().lower()
    if not value:
        raise ValueError("empty extension")
    if not value.startswith("."):
        value = "." + value
    return value


def should_skip_dir(dirname: str, rel_dir: str, excludes: tuple[str, ...]) -> bool:
    if dirname.endswith(".pyc"):
        return True
    for exclude in excludes:
        if dirname == exclude or rel_dir == exclude:
            return True
        if "/" in exclude and rel_dir.startswith(exclude + "/"):
            return True
    return False


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
    parser.add_argument(
        "-x", "--extension",
        action="append",
        default=None,
        help=(
            "Source file extension to include, for example .cpp or py. "
            "May be repeated; defaults to C/C++/C#/Python source extensions."
        ),
    )
    parser.add_argument(
        "--fail",
        action="store_true",
        help="Exit with status 1 when matching long source files are found.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    excludes = tuple(normalize_exclude(value) for value in args.exclude)
    try:
        extensions = tuple(
            normalize_extension(value)
            for value in (args.extension if args.extension is not None else DEFAULT_EXTENSIONS)
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
    results: list[tuple[Path, int]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        kept_dirnames = []
        for dirname in dirnames:
            full_dir = Path(dirpath) / dirname
            rel_dir = full_dir.relative_to(root).as_posix()
            if not should_skip_dir(dirname, rel_dir, excludes):
                kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames

        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.suffix.lower() not in extensions:
                continue
            lines = count_lines(fpath)
            if lines >= args.threshold:
                results.append((fpath, lines))

    # Sort by line count descending
    results.sort(key=lambda x: x[1], reverse=True)

    if not results:
        print(f"No source files with >= {args.threshold} lines found.")
        return

    print(f"Source files with >= {args.threshold} lines:\n")
    rel_root = root
    for fpath, lines in results:
        rel = fpath.relative_to(rel_root)
        print(f"  {lines:>6}  {rel}")

    print(f"\nTotal: {len(results)} file(s)")
    if args.fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
