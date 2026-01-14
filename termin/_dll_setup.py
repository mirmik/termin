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


def _preload_native_modules():
    """
    Preload native modules that register kind handlers.

    These must be loaded BEFORE _native module to ensure kind handlers
    are registered when components are deserialized.

    Import using importlib to avoid triggering package __init__.py files
    which may have circular dependencies.
    """
    import importlib.util
    import os

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # List of native modules to preload (relative paths from termin/)
    modules_to_preload = [
        ("skeleton._skeleton_native", os.path.join(base_dir, "skeleton")),
        ("visualization.animation._animation_native", os.path.join(base_dir, "visualization", "animation")),
    ]

    import sys

    for module_name, module_dir in modules_to_preload:
        full_name = f"termin.{module_name}"

        # Skip if already loaded
        if full_name in sys.modules:
            continue

        # Find the .pyd file
        try:
            for fname in os.listdir(module_dir):
                if fname.startswith("_") and fname.endswith(".pyd"):
                    short_name = module_name.split(".")[-1]
                    if fname.startswith(short_name):
                        pyd_path = os.path.join(module_dir, fname)
                        spec = importlib.util.spec_from_file_location(full_name, pyd_path)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[full_name] = module
                            spec.loader.exec_module(module)
                            # Preloaded successfully
                        break
        except Exception as e:
            pass  # Failed to preload, will be loaded later


_preload_native_modules()
