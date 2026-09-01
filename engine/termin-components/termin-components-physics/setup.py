#!/usr/bin/env python3

import os

from setuptools import find_namespace_packages, setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-components-physics",
    version=BuildExt.compute_local_version("0.1.0"),
    license="Apache-2.0",
    description="Physics scene components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=[
        *find_namespace_packages(
            where="python",
            include=["termin.physics_components", "termin.physics_components.*"],
        ),
        "termin_physics_component_specs",
    ],
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "termin-base",
        "termin-nanobind",
        "termin-collision",
        "termin-inspect",
        "termin-physics",
        "termin-scene",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
