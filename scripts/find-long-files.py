#!/usr/bin/env python3
"""Compatibility launcher for the manifest-driven source-size policy."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "termin-build-tools"))

from termin_build.source_size_policy import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
