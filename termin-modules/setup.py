#!/usr/bin/env python3

from setuptools import Extension, setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt


import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_termin_modules_native"]
    bundle_libs = False
    source_dir = _DIR


setup(
    name="termin-modules",
    version="0.1.0",
    license="MIT",
    description="Runtime module loader for termin projects",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin_modules"],
    package_dir={"termin_modules": "python/termin_modules"},
    ext_modules=[Extension("termin_modules._termin_modules_native", sources=[])],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
