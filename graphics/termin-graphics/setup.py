#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    upstream_packages = {"termin-base": "libtermin_base", "termin-mesh": "libtermin_mesh", "termin_nanobind": "libnanobind"}
    bundle_includes = True
    source_dir = _DIR


setup(
    name="termin-graphics",
    version=BuildExt.compute_local_version("0.1.0"),
    license="Apache-2.0",
    description="Graphics backend library with Python bindings",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.graphics"],
    package_dir={"termin.graphics": "python/termin/graphics"},
    install_requires=["termin-base", "termin-mesh", "termin-nanobind", "numpy"],
    package_data={
        "termin.graphics": [
            "lib/*.so*",
            "*.dll",
            "lib/*.dll",
            "lib/*.lib",
        ],
    },
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
