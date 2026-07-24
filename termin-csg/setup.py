#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-csg",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Constructive solid geometry helpers for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.csg"],
    package_dir={"termin.csg": "python/termin/csg"},
    install_requires=[
        "termin-nanobind",
        "numpy",
        "tcbase",
        "tcgui",
        "termin-display",
        "tgfx",
        "tmesh",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
