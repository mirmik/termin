"""Runtime helpers for termin pip packages.

Termin packages can run in two layouts:

1. Standalone pip install: a package may carry its native dependencies in a
   local ``lib/`` directory next to the binding module.
2. SDK install: shared libraries live in ``$TERMIN_SDK/lib``.

At import time, packages call ``preload_sdk_libs(...)`` before importing their
nanobind module so dependent shared libraries are visible to the dynamic linker.
"""

import ctypes
import importlib.util
import json
import logging
import os
import sys
import sysconfig
from pathlib import Path

_sdk_root = None
_preloaded = set()
_windows_dll_directory_handles = {}
_log = logging.getLogger(__name__)


def find_sdk():
    """Locate the termin SDK root directory.

    Checks in order:
      1. $TERMIN_SDK environment variable
      2. ./sdk from the current project checkout
      3. /opt/termin (Linux/macOS)
      4. %LOCALAPPDATA%/termin-sdk (Windows)

    Returns a Path, or None if no SDK is found.
    """
    global _sdk_root
    if _sdk_root is not None:
        return _sdk_root

    env = os.environ.get("TERMIN_SDK")
    if env:
        p = Path(env)
        if (p / "lib").is_dir():
            _sdk_root = p
            return p

    cwd_sdk = Path.cwd() / "sdk"
    if (cwd_sdk / "lib").is_dir():
        _sdk_root = cwd_sdk
        return cwd_sdk

    module_path = Path(__file__).resolve()
    for parent in module_path.parents:
        checkout_sdk = parent / "sdk"
        if (checkout_sdk / "lib").is_dir():
            _sdk_root = checkout_sdk
            return checkout_sdk

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
        default = Path(local) / "termin-sdk"
    else:
        default = Path("/opt/termin")

    if (default / "lib").is_dir():
        _sdk_root = default
        return default

    return None


def _require_sdk():
    sdk = find_sdk()
    if sdk is None:
        raise ImportError(
            "termin SDK not found. Set TERMIN_SDK environment variable or "
            "install the SDK to /opt/termin (Linux/macOS) or "
            "%LOCALAPPDATA%/termin-sdk (Windows)."
        )
    return sdk


def _caller_lib_dirs():
    dirs = []
    try:
        frame = sys._getframe(2)
    except ValueError:
        return dirs
    module_file = frame.f_globals.get("__file__")
    if not module_file:
        return dirs

    start = Path(module_file).resolve().parent
    for parent in (start, *start.parents):
        lib_dir = parent / "lib"
        if lib_dir.is_dir():
            dirs.append(lib_dir)
        if parent.name in {"site-packages", "dist-packages"}:
            break
    return dirs


def _installed_product_lib_dirs():
    """Return native-library roots owned by installed Termin product wheels."""
    try:
        spec = importlib.util.find_spec("termin_graphics_profile")
    except (ImportError, ModuleNotFoundError, ValueError):
        return []
    if spec is None or spec.submodule_search_locations is None:
        return []
    dirs = []
    for package_root in spec.submodule_search_locations:
        lib_dir = Path(package_root) / "lib"
        if lib_dir.is_dir():
            dirs.append(lib_dir)
    return dirs


def _installed_product_library_paths():
    paths = []
    for lib_dir in _installed_product_lib_dirs():
        manifest_path = lib_dir.parent / "native-libraries.json"
        try:
            names = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError) as exc:
            raise ImportError(
                f"Cannot read installed Termin product native manifest: {manifest_path}: {exc}"
            ) from exc
        if not isinstance(names, list) or not all(
            isinstance(name, str) and name and Path(name).name == name for name in names
        ):
            raise ImportError(f"Invalid installed Termin product native manifest: {manifest_path}")
        for name in names:
            path = lib_dir / name
            if not path.is_file():
                raise ImportError(f"Installed Termin product library is missing: {path}")
            paths.append(path)
    return paths


def _register_windows_dll_dirs(local_dirs):
    for directory in local_dirs:
        _register_windows_dll_dir(directory)
    sdk = find_sdk()
    if sdk is None:
        return
    for sub in ("bin", "lib"):
        directory = sdk / sub
        if directory.is_dir():
            _register_windows_dll_dir(directory)


def _register_windows_dll_dir(directory):
    """Register one normalized Windows DLL search path for module lifetime."""
    key = os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(directory))))
    if key in _windows_dll_directory_handles:
        return
    try:
        handle = os.add_dll_directory(key)
    except OSError as exc:
        _log.error("Failed to register Windows DLL directory '%s': %s", key, exc)
        raise ImportError(f"Failed to register required DLL directory: {key}") from exc
    _windows_dll_directory_handles[key] = handle


def close_windows_dll_directories():
    """Remove registered DLL directories during an explicit embedding shutdown.

    Normal package use deliberately keeps the handles alive until interpreter
    teardown, because closing them earlier makes later native imports fragile.
    Hosts that unload Termin before process exit may call this after all Termin
    extension modules have been released.
    """
    handles = list(_windows_dll_directory_handles.items())
    for key, handle in reversed(handles):
        try:
            handle.close()
        except OSError as exc:
            _log.error("Failed to remove Windows DLL directory '%s': %s", key, exc)
        finally:
            del _windows_dll_directory_handles[key]


def _find_library(name, lib_dirs):
    for lib_dir in lib_dirs:
        # Prefer the ELF SONAME spelling used by DT_NEEDED. GitHub artifact
        # transport does not preserve symlinks and can turn libfoo.so and
        # libfoo.so.0 into distinct regular files. Preloading the unversioned
        # copy would then give the process two independent instances of every
        # library-global registry once an extension loads libfoo.so.0.
        versioned_so = sorted(lib_dir.glob(f"lib{name}.so.*"))
        if versioned_so:
            return versioned_so[0]
        candidates = [
            lib_dir / f"lib{name}.so",
            lib_dir / f"lib{name}.dylib",
        ]
        found = next((p for p in candidates if p.exists()), None)
        if found is not None:
            return found
        versioned_dylib = sorted(lib_dir.glob(f"lib{name}.*.dylib"))
        if versioned_dylib:
            return versioned_dylib[0]
    return None


def _abi_runtime_library_name(name):
    if name != "nanobind":
        return name
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        return "nanobind-ft"
    return "nanobind"


def preload_sdk_libs(*lib_names):
    """Preload termin SDK shared libraries into the global symbol namespace.

    Args:
        *lib_names: library base names without the "lib" prefix or extension,
            e.g. "termin_base", "termin_display".

    On Linux/macOS each named library is opened via ctypes.CDLL with
    RTLD_GLOBAL, so that subsequent dlopen of a nanobind binding module
    (which has the same DT_NEEDED entries) reuses the already-loaded
    mappings regardless of its own RPATH.

    On Windows this function registers the SDK lib and bin directories via
    os.add_dll_directory. On Windows the loader searches those directories
    directly, so explicit CDLL preloading is unnecessary.
    """
    # Every Termin extension links the shared nanobind runtime. Package-local
    # wheels used to let the extension RPATH discover it implicitly; a
    # centralized product library root must preload it before dlopen reaches
    # the extension itself.
    requested_libs = ("nanobind", *lib_names)
    local_lib_dirs = [*_installed_product_lib_dirs(), *_caller_lib_dirs()]

    if sys.platform == "win32":
        _register_windows_dll_dirs(local_lib_dirs)
        return

    sdk = find_sdk()
    sdk_lib_dir = sdk / "lib" if sdk is not None else None
    lib_dirs = list(local_lib_dirs)
    if sdk_lib_dir is not None and sdk_lib_dir.is_dir():
        lib_dirs.append(sdk_lib_dir)

    for product_library in _installed_product_library_paths():
        key = f"product:{product_library.name}"
        if key in _preloaded:
            continue
        ctypes.CDLL(str(product_library), mode=ctypes.RTLD_GLOBAL)
        _preloaded.add(key)

    for name in requested_libs:
        runtime_name = _abi_runtime_library_name(name)
        if runtime_name in _preloaded:
            continue
        found = _find_library(runtime_name, lib_dirs)
        if found is None:
            searched = ", ".join(str(p) for p in lib_dirs) or "<none>"
            raise ImportError(
                f"Cannot find lib{runtime_name}. Searched: {searched}. "
                f"Install a package with bundled native libraries, rebuild the "
                f"SDK, or check TERMIN_SDK points to a valid installation."
            )
        ctypes.CDLL(str(found), mode=ctypes.RTLD_GLOBAL)
        _preloaded.add(runtime_name)
