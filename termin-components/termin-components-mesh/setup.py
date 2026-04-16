#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_components_mesh_native"]
    source_dir = _DIR


setup(
    name="termin-components-mesh",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Mesh components Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.mesh"],
    package_dir={"termin.mesh": "python/termin/mesh"},
    install_requires=["termin-nanobind", "tgfx"],
    ext_modules=[
        Extension("termin.mesh._components_mesh_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
