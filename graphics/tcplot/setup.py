#!/usr/bin/env python3
import os

from setuptools import setup

from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    upstream_packages = {
        "termin-base": "libtermin_base",
        "termin-mesh": "libtermin_mesh",
        "termin-graphics-core": "libtermin_graphics2",
        "termin_nanobind": "libnanobind",
    }
    source_dir = _DIR


setup(
    name="termin-plot",
    version=BuildExt.compute_local_version(),
    license="Apache-2.0",
    description="Toolkit-neutral plotting engines and retained chart primitives",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.plot"],
    package_dir={"termin.plot": "python/tcplot"},
    install_requires=[
        "termin-base",
        "termin-mesh",
        "termin-graphics-core",
        "termin-nanobind",
        "numpy",
    ],
    package_data={
        "termin.plot": [
            "*.dll",
            "lib/*.dll",
            "lib/*.so*",
            "lib/*.lib",
        ],
    },
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
