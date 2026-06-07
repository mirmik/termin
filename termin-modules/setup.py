#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    upstream_packages = {"tcbase": "libtermin_base", "termin_nanobind": "libnanobind"}
    source_dir = _DIR


setup(
    name="termin-modules",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Runtime module loader for termin projects",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin_modules"],
    package_dir={"termin_modules": "python/termin_modules"},
    install_requires=["tcbase", "termin-nanobind"],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
