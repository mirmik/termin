#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_physics_native"]
    source_dir = _DIR


setup(
    name="termin-physics",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Rigid-body physics Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.physics"],
    package_dir={"termin.physics": "python/termin/physics"},
    install_requires=["termin-nanobind"],
    ext_modules=[
        Extension("termin.physics._physics_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
