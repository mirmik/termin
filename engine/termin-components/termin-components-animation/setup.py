#!/usr/bin/env python3

import os

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-components-animation",
    version=BuildExt.compute_local_version(),
    license="Apache-2.0",
    description="Termin Entity adapter for the portable animation runtime",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.14",
    packages=["termin.animation_components", "termin_animation_component_specs"],
    package_dir={
        "termin.animation_components": "python/termin/animation_components",
        "termin_animation_component_specs": "python/termin_animation_component_specs",
    },
    install_requires=[
        "termin-base",
        "termin-animation",
        "termin-components-skeleton",
        "termin-inspect",
        "termin-nanobind",
        "termin-scene",
        "termin-skeleton",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
