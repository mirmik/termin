#!/usr/bin/env python3

import os

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    upstream_packages = {"termin-base": "libtermin_base", "termin_nanobind": "libnanobind"}
    source_dir = _DIR


setup(
    name="termin-nodegraph",
    version=BuildExt.compute_local_version("0.1.0"),
    license="Apache-2.0",
    description="Abstract node graph engine and native UI projection",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.nodegraph"],
    package_dir={"": "python"},
    install_requires=[
        "termin-base",
        "termin-nanobind",
        "termin-gui-native",
        "termin-visual-scene",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
