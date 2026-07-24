#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

import os

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-bootstrap",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Explicit startup bootstrap helpers for Termin runtime/player/editor",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.bootstrap"],
    package_dir={"termin.bootstrap": "python/termin/bootstrap"},
    install_requires=[
        "termin-nanobind",
        "tcbase",
        "termin-inspect",
        "termin-scene",
        "termin-render",
        "termin-collision",
        "termin-input",
        "termin-display",
        "tmesh",
        "tgfx",
        "termin-materials",
        "termin-skeleton",
        "termin-animation",
        "termin-voxels",
        "termin-navmesh",
        "termin-default-assets",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
