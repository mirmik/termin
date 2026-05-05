#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt, _find_sdk

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


def _sdk_has_module(pkg_dotted_path, module_name):
    """Return True if a pre-built binding module exists in the SDK."""
    sdk = _find_sdk()
    if sdk is None:
        return False
    pkg_fs_path = pkg_dotted_path.replace(".", "/")
    search_dir = sdk / "lib" / "python" / pkg_fs_path
    if not search_dir.is_dir():
        return False
    for pat in [f"{module_name}.*.so", f"{module_name}.*.pyd", f"{module_name}.pyd"]:
        if list(search_dir.glob(pat)):
            return True
    return False


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_display_native", "_viewport_native", "_platform_native"]
    source_dir = _DIR


ext_modules = [
    Extension("termin.display._display_native", sources=[]),
    Extension("termin.viewport._viewport_native", sources=[]),
]

if _sdk_has_module("termin.display", "_platform_native"):
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
