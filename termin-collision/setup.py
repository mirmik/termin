#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_colliders_native", "_collision_native"]
    upstream_packages = {
        "tcbase": "libtermin_base",
        "termin_nanobind": "libnanobind",
        "termin.inspect": "libtermin_inspect",
        "termin.scene": "libtermin_scene",
    }
    bundle_includes = True
    source_dir = _DIR


setup(
    name="termin-collision",
    version="0.1.0",
    license="MIT",
    description="Collision and collider system with Python bindings",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.colliders", "termin.collision"],
    package_dir={
        "termin.colliders": "python/termin/colliders",
        "termin.collision": "python/termin/collision",
    },
    install_requires=["tcbase", "termin-inspect", "termin-scene", "termin-nanobind"],
    package_data={
        "termin.colliders": [
            "include/**/*.h",
            "include/**/*.hpp",
            "lib/*.so*",
            "lib/cmake/**/*",
            "*.dll",
            "lib/*.dll",
            "lib/*.lib",
        ],
    },
    ext_modules=[
        Extension("termin.colliders._colliders_native", sources=[]),
        Extension("termin.collision._collision_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
