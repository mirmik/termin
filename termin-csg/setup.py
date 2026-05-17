#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_csg_native"]
    source_dir = _DIR


setup(
    name="termin-csg",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Constructive solid geometry helpers for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.csg"],
    package_dir={"termin.csg": "python/termin/csg"},
    install_requires=["termin-nanobind", "tmesh"],
    ext_modules=[
        Extension("termin.csg._csg_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
