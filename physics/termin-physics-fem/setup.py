#!/usr/bin/env python3

import os

from setuptools import find_namespace_packages, setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-physics-fem",
    version=BuildExt.compute_local_version("0.1.0"),
    license="Apache-2.0",
    description="Experimental FEM scene physics components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=find_namespace_packages(
        where="python",
        include=["termin.physics_fem", "termin.physics_fem.*"],
    ),
    package_dir={"": "python"},
    install_requires=[
        "numpy",
        "tcbase",
        "termin-inspect",
        "termin-nanobind",
        "termin-qopt",
        "termin-robotics",
        "termin-scene",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
