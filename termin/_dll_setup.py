"""
DLL search path setup for Windows.

This module must be imported BEFORE any native extension imports.
It configures os.add_dll_directory() so that entity_lib.dll and other
dependencies can be found.

Usage:
    # At the top of any __init__.py that imports native extensions:
    from termin import _dll_setup  # noqa: F401
    from ._native_module import ...
"""

import os
import sys

_initialized = False


def _setup_dll_paths():
    """Configure DLL search paths on Windows."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    if sys.platform != "win32":
        return

    # Directory containing termin package (where DLLs are located)
    dll_dir = os.path.dirname(os.path.abspath(__file__))

    # Python 3.8+ requires explicit DLL directory registration
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(dll_dir)

    # Also prepend to PATH for compatibility
    os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")


# Run setup on import
_setup_dll_paths()


