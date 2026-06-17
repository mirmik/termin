"""Compatibility entry point for the canonical project build profile backend."""

from __future__ import annotations

import sys

from termin.project_build.profile_build import main


if __name__ == "__main__":
    sys.exit(main())
