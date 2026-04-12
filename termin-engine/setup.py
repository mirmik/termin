#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_engine_native"]
    source_dir = _DIR


setup(
    name="termin-engine",
    version="0.1.0",
    license="MIT",
    description="Termin engine core Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.engine"],
    package_dir={"termin.engine": "python/termin/engine"},
    install_requires=["termin-nanobind"],
    ext_modules=[
        Extension("termin.engine._engine_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
