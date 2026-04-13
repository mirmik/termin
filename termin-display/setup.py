#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_display_native", "_viewport_native", "_platform_native"]
    source_dir = _DIR


setup(
    name="termin-display",
    version="0.1.0",
    license="MIT",
    description="Display, viewport, and SDL platform Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.display", "termin.viewport"],
    package_dir={
        "termin.display": "python/termin/display",
        "termin.viewport": "python/termin/viewport",
    },
    install_requires=[
        "termin-nanobind",
    ],
    ext_modules=[
        Extension("termin.display._display_native", sources=[]),
        Extension("termin.display._platform_native", sources=[]),
        Extension("termin.viewport._viewport_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
