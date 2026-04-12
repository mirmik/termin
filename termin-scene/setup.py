#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_scene_native"]
    source_dir = _DIR


setup(
    name="termin-scene",
    version="0.1.0",
    license="MIT",
    description="Scene/entity system Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.scene"],
    package_dir={"termin.scene": "python/termin/scene"},
    install_requires=["termin-nanobind"],
    ext_modules=[
        Extension("termin.scene._scene_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
