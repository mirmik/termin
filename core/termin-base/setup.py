#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    upstream_packages = {"termin_nanobind": "libnanobind"}
    bundle_includes = True
    source_dir = _DIR


setup(
    name="termin-base",
    version=BuildExt.compute_local_version(),
    license="Apache-2.0",
    description="Base types shared between termin libraries",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.base", "termin.geombase", "termin.artifacts"],
    package_dir={
        "termin.base": "python/termin/base",
        "termin.geombase": "python/termin/geombase",
        "termin.artifacts": "python/termin/artifacts",
    },
    package_data={
        "termin.base": [
            "include/*.h",
            "include/*.hpp",
            "include/**/*.h",
            "include/**/*.hpp",
            "lib/*.so*",
            "*.dll",
            "lib/*.dll",
            "lib/*.lib",
            "lib/cmake/termin_base/*.cmake",
        ],
    },
    install_requires=["termin-nanobind"],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
