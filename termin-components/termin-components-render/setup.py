#!/usr/bin/env python3

from setuptools import setup, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_components_render_native"]
    source_dir = _DIR


setup(
    name="termin-components-render",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Rendering components Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.render_components"],
    package_dir={"termin.render_components": "python/termin/render_components"},
    install_requires=["termin-nanobind"],
    ext_modules=[
        Extension("termin.render_components._components_render_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
