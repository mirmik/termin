#!/usr/bin/env python3

from setuptools import find_namespace_packages, setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    upstream_packages = {"termin-base": "libtermin_base", "termin_nanobind": "libnanobind"}
    bundle_includes = True
    source_dir = _DIR


setup(
    name="termin-mesh",
    version=BuildExt.compute_local_version("0.1.0"),
    license="Apache-2.0",
    description="Mesh library with Python bindings",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=[
        *find_namespace_packages(
            where="python",
            include=["termin", "termin.mesh", "termin.mesh.*"],
        ),
    ],
    package_dir={
        "": "python",
    },
    install_requires=[
        "termin-base",
        "termin-nanobind",
        "numpy",
    ],
    package_data={
        "termin.mesh": [
            "include/**/*.h",
            "include/**/*.hpp",
            "lib/*.so*",
            "*.dll",
            "lib/*.dll",
            "lib/*.lib",
            "lib/cmake/termin_mesh/*.cmake",
        ],
    },
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
