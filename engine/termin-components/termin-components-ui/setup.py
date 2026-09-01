#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

import os

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-components-ui",
    version=BuildExt.compute_local_version(),
    license="Apache-2.0",
    description="Widget UI scene components for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.ui_components", "termin_ui_component_specs"],
    package_dir={
        "termin.ui_components": "python/termin/ui_components",
        "termin_ui_component_specs": "python/termin_ui_component_specs",
    },
    install_requires=[
        "termin-base",
        "termin-gui-native",
        "termin-input",
        "termin-inspect",
        "termin-nanobind",
        "termin-scene",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
