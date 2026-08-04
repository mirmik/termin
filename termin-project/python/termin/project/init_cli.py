"""Command-line entry point for initializing a Termin project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from termin.project.creation import ProjectCreationError, initialize_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="termin init",
        description="Initialize a minimal Termin project in the current directory.",
    )
    parser.add_argument(
        "--name",
        help="Project name (defaults to the current directory name).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project_file = initialize_project(Path.cwd(), args.name)
    except ProjectCreationError as exc:
        print(f"termin init: {exc}", file=sys.stderr)
        return 2

    print(f"Initialized Termin project: {project_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
