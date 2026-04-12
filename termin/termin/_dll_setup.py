"""DLL search path setup for Windows (legacy main-termin helper).

Historically this module extended ``sys.path`` and ``termin.__path__`` so
that the SDK layout at ``sdk/lib/python/termin/`` could be discovered at
runtime even when main termin was pip-installed into a different location.

In the current "thin pip packages + bundled site-packages" model, every
termin subpackage is pip-installed into a single site-packages directory
(either the user's pyenv or ``sdk/lib/python3.x/site-packages/`` for
bundled Python). There is no need to extend ``sys.path`` at runtime — the
packages are already where Python looks for them.

What remains needed:

- **Windows DLL loading**: on Windows the loader has no RPATH, so the
  directory containing termin shared libraries must be registered via
  ``os.add_dll_directory`` before any native extension is dlopened. On
  Linux/macOS the shared libraries are found via each .so's RPATH that
  was set by cmake at build time.

- ``extend_package_path(...)``: kept as a no-op shim so existing callers
  in main termin Python modules don't break. In the new layout there is
  nothing to extend.

This module used to be imported as ``from termin import _dll_setup`` from
every subpackage. Subprojects now use ``termin_nanobind.runtime.preload_sdk_libs``
instead; this legacy module remains only for main termin's own
``termin/__init__.py`` and a handful of internal submodules.
"""

import os
import sys


_initialized = False


def _find_sdk_root():
    """Locate the termin SDK root for Windows DLL directory registration.

    Only used on Windows. Checks $TERMIN_SDK and %LOCALAPPDATA%/termin-sdk.
    Does NOT fall back via file-relative path tricks — if the SDK isn't
    explicit, we do nothing and let the loader fail cleanly.
    """
    sdk_env = os.environ.get("TERMIN_SDK")
    if sdk_env and os.path.isdir(os.path.join(sdk_env, "lib")):
        return sdk_env

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        candidate = os.path.join(local, "termin-sdk")
        if os.path.isdir(os.path.join(candidate, "lib")):
            return candidate

    return None


def _setup_dll_paths():
    """On Windows, register SDK lib/bin dirs so the DLL loader can find them.

    No-op on Linux/macOS — RPATH in each .so handles library resolution.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    if sys.platform != "win32":
        return
    if not hasattr(os, "add_dll_directory"):
        return

    sdk_root = _find_sdk_root()
    if sdk_root is None:
        return

    for sub in ("lib", "bin"):
        d = os.path.join(sdk_root, sub)
        if os.path.isdir(d):
            os.add_dll_directory(d)

    # Also prepend bin/ to PATH for pysdl2 and other non-DLL-directory lookups
    sdk_bin = os.path.join(sdk_root, "bin")
    if os.path.isdir(sdk_bin):
        os.environ["PATH"] = sdk_bin + os.pathsep + os.environ.get("PATH", "")
        if not os.environ.get("PYSDL2_DLL_PATH"):
            os.environ["PYSDL2_DLL_PATH"] = sdk_bin


# Run setup on import
_setup_dll_paths()


def extend_package_path(package_path, *relative_parts):
    """Backward-compat shim. No-op in the current pip-packaged layout.

    Previously extended ``__path__`` of a subpackage with the SDK's copy of
    that subpackage. Now all subpackages are collocated in a single
    site-packages, so there is nothing to extend.
    """
    return
