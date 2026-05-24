#!/usr/bin/env python3

from setuptools import setup, Extension
from pathlib import Path
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt, _find_sdk

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


def _has_prebuilt_module(pkg_dotted_path, module_name):
    """Return True if an optional pre-built binding module exists."""
    pkg_fs_path = pkg_dotted_path.replace(".", "/")
    roots = []
    bindings_dir = os.environ.get("TERMIN_BINDINGS_DIR")
    if bindings_dir:
        roots.append(Path(bindings_dir))

    source_dir = Path(_DIR)
    for parent in (source_dir, *source_dir.parents):
        roots.append(parent / "build" / "Release" / "bin")
        roots.append(parent / "build" / "Debug" / "bin")

    sdk = _find_sdk()
    if sdk is not None:
        roots.append(sdk / "lib" / "python")

    for pat in [f"{module_name}.*.so", f"{module_name}.*.pyd", f"{module_name}.pyd"]:
        for root in roots:
            if list(root.glob(pat)) or list((root / pkg_fs_path).glob(pat)):
                return True
    return False


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_display_native", "_viewport_native", "_platform_native"]
    source_dir = _DIR


ext_modules = [
    Extension("termin.display._display_native", sources=[]),
    Extension("termin.viewport._viewport_native", sources=[]),
]

if _has_prebuilt_module("termin.display", "_platform_native"):
    ext_modules.append(
        Extension("termin.display._platform_native", sources=[])
    )


setup(
    name="termin-display",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Display, viewport, and SDL platform Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.display", "termin.viewport"],
    package_dir={
        "termin.display": "python/termin/display",
        "termin.viewport": "python/termin/viewport",
    },
    install_requires=[
        "termin-nanobind",
    ],
    ext_modules=ext_modules,
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
