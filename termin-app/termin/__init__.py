"""Top-level Termin namespace bootstrap."""

from __future__ import annotations

from importlib.abc import MetaPathFinder
from pkgutil import extend_path
import sys


__path__ = extend_path(__path__, __name__)

_NATIVE_PRELOAD_DONE = False


def _preload_native_dependencies() -> None:
    global _NATIVE_PRELOAD_DONE
    if _NATIVE_PRELOAD_DONE:
        return

    from termin_nanobind.runtime import preload_sdk_libs

    preload_sdk_libs("termin_graphics", "termin_graphics2")
    _NATIVE_PRELOAD_DONE = True


class _TerminNativePreloadFinder(MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == "termin._native":
            _preload_native_dependencies()
        return None


def _install_native_preload_finder() -> None:
    sys.meta_path.insert(0, _TerminNativePreloadFinder())


_install_native_preload_finder()
