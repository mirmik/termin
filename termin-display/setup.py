#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-display",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Display, viewport, and SDL platform Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.display", "termin.viewport"],
    package_dir={
        "termin.display": "python/termin/display",
        "termin.viewport": "python/termin/viewport",
    },
    install_requires=[
        "termin-nanobind",
        "termin-scene",
        "tgfx",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
