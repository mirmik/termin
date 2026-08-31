#!/usr/bin/env python3

import os

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-components-skeleton",
    version=BuildExt.compute_local_version("0.1.0"),
    license="Apache-2.0",
    description="Termin Entity adapter for the portable skeleton runtime",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.skeleton_components", "termin_skeleton_component_specs"],
    package_dir={
        "termin.skeleton_components": "python/termin/skeleton_components",
        "termin_skeleton_component_specs": "python/termin_skeleton_component_specs",
    },
    install_requires=[
        "tcbase",
        "termin-inspect",
        "termin-nanobind",
        "termin-render",
        "termin-scene",
        "termin-skeleton",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
