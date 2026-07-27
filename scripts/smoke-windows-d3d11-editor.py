#!/usr/bin/env python3
"""Run the repository scene through the installed D3D11 editor host."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from windows_d3d11_editor_smoke import main


if __name__ == "__main__":
    raise SystemExit(main())
