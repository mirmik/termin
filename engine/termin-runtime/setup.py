#!/usr/bin/env python3

import os

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-runtime",
    version=BuildExt.compute_local_version(),
    license="Apache-2.0",
    description="Optional Python adapters for the native Termin runtime",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.runtime"],
    package_dir={"termin.runtime": "python/termin/runtime"},
    install_requires=[
        "termin-nanobind",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
