#!/usr/bin/env python
"""Run ChronoSquad tests."""

import subprocess
import sys

if __name__ == "__main__":
    sys.exit(subprocess.call([
        sys.executable, "-m", "pytest",
        "termin/chronosquad/tests/",
        "-v",
        *sys.argv[1:]
    ]))
