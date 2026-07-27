#!/usr/bin/env python3
"""Build and run the repository scene through the packaged D3D11 player."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from windows_d3d11_player_smoke import main


if __name__ == "__main__":
    raise SystemExit(main())
