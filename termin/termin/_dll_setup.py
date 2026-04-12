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
_sdk_termin_dir = None


def _find_sdk_termin_dir():
    """Find SDK termin directory by checking known locations.

    Discovery order mirrors termin_nanobind.runtime.find_sdk():
      1. $TERMIN_SDK environment variable
      2. Relative to this file (when running from an already-extracted SDK install)
      3. /opt/termin (Linux/macOS system-wide install via install-to-opt.sh)
      4. %LOCALAPPDATA%/termin-sdk (Windows system-wide install)
    """
    candidates = []

    # 1. TERMIN_SDK environment variable
    sdk_env = os.environ.get("TERMIN_SDK")
    if sdk_env:
        candidates.append(os.path.join(sdk_env, "lib", "python", "termin"))

    # 2. Relative to this file (when running from sdk/lib/python/termin/)
    this_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(this_dir, "..", "..", "..", "lib", "python", "termin"))

    # 3/4. System-wide install fallback
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        candidates.append(os.path.join(local, "termin-sdk", "lib", "python", "termin"))
    else:
        candidates.append("/opt/termin/lib/python/termin")

    for c in candidates:
        c = os.path.normpath(c)
        if os.path.isdir(c):
            return c
    return None


def _setup_dll_paths():
    """Configure DLL search paths on Windows."""
    global _initialized, _sdk_termin_dir
    if _initialized:
        return
    _initialized = True

    _sdk_termin_dir = _find_sdk_termin_dir()

    # Add SDK Python packages to sys.path and extend termin.__path__
    # so that subpackages from external repos (termin.scene, termin.inspect, etc.)
    # installed into sdk/lib/python/termin/ are discoverable.
    if _sdk_termin_dir:
        sdk_python_dir = os.path.dirname(_sdk_termin_dir)
        if os.path.isdir(sdk_python_dir) and sdk_python_dir not in sys.path:
            sys.path.insert(0, sdk_python_dir)
        import termin as _termin_pkg
        if _sdk_termin_dir not in _termin_pkg.__path__:
            _termin_pkg.__path__.append(_sdk_termin_dir)

    if sys.platform != "win32":
        return

    # Directory containing termin package (where DLLs are located)
    dll_dir = os.path.dirname(os.path.abspath(__file__))

    # SDK bin directory (where SDL2.dll, termin_base.dll etc. are installed)
    sdk_bin_dir = None
    if _sdk_termin_dir:
        sdk_bin_dir = os.path.normpath(os.path.join(_sdk_termin_dir, "..", "..", "..", "bin"))
    if not sdk_bin_dir or not os.path.isdir(sdk_bin_dir):
        sdk_bin_dir = os.path.normpath(os.path.join(dll_dir, "..", "..", "..", "bin"))

    # Collect all directories that may contain DLLs
    dll_dirs = [dll_dir]

    # Add subdirectories of termin/ (namespace sub-packages like termin/scene/, termin/inspect/)
    for entry in os.scandir(dll_dir):
        if entry.is_dir() and not entry.name.startswith(("_", ".")):
            dll_dirs.append(entry.path)

    # Add upstream flat packages (tcbase, tmesh, tgfx, etc.)
    site_packages = os.path.dirname(dll_dir)
    for pkg in ("tcbase", "tmesh", "tgfx", "termin_modules", "termin_nanobind"):
        pkg_dir = os.path.join(site_packages, pkg)
        if os.path.isdir(pkg_dir):
            dll_dirs.append(pkg_dir)

    if sdk_bin_dir and os.path.isdir(sdk_bin_dir):
        dll_dirs.append(sdk_bin_dir)

    # Python 3.8+ requires explicit DLL directory registration
    if hasattr(os, "add_dll_directory"):
        for d in dll_dirs:
            os.add_dll_directory(d)

    # Also prepend to PATH for compatibility
    os.environ["PATH"] = os.pathsep.join(dll_dirs) + os.pathsep + os.environ.get("PATH", "")

    # Set PYSDL2_DLL_PATH so pysdl2 can find SDL2.dll
    if os.path.isdir(sdk_bin_dir) and not os.environ.get("PYSDL2_DLL_PATH"):
        os.environ["PYSDL2_DLL_PATH"] = sdk_bin_dir


# Run setup on import
_setup_dll_paths()


def extend_package_path(package_path, *relative_parts):
    """Extend subpackage __path__ with the installed SDK directory for this package."""
    if _sdk_termin_dir is None:
        return
    sdk_package_dir = os.path.join(_sdk_termin_dir, *relative_parts)
    if os.path.isdir(sdk_package_dir) and sdk_package_dir not in package_path:
        package_path.append(sdk_package_dir)

