#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_colliders_native", "_collision_native", "_components_collision_native"]
    source_dir = _DIR


setup(
    name="termin-collision",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Collision and collider Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.colliders", "termin.collision"],
    package_dir={
        "termin.colliders": "python/termin/colliders",
        "termin.collision": "python/termin/collision",
    },
    install_requires=["termin-nanobind"],
    ext_modules=[
        Extension("termin.colliders._colliders_native", sources=[]),
        Extension("termin.colliders._components_collision_native", sources=[]),
        Extension("termin.collision._collision_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
