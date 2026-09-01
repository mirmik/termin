#!/usr/bin/env python3

import os

from setuptools import setup

from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-plot-gui-native",
    version=BuildExt.compute_local_version(),
    license="Apache-2.0",
    description="Native Termin UI widgets backed by tcplot",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.plot.gui_native"],
    package_dir={"termin.plot.gui_native": "python/tcplot_gui_native"},
    install_requires=[
        "numpy",
        "termin-plot",
        "termin-gui-native",
        "termin-nanobind",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
