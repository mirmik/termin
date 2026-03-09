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

    # Add SDK Python packages to sys.path and extend termin.__path__
    # so that subpackages from external repos (termin.scene, termin.inspect, etc.)
    # installed into /opt/termin/lib/python/termin/ are discoverable.
    sdk_python_dir = os.path.join(os.sep, "opt", "termin", "lib", "python")
    if os.path.isdir(sdk_python_dir) and sdk_python_dir not in sys.path:
        sys.path.insert(0, sdk_python_dir)
    sdk_termin_dir = os.path.join(sdk_python_dir, "termin")
    import termin as _termin_pkg
    if os.path.isdir(sdk_termin_dir) and sdk_termin_dir not in _termin_pkg.__path__:
        _termin_pkg.__path__.append(sdk_termin_dir)

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


