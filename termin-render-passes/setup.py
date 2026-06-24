#!/usr/bin/env python3

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

import os

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-render-passes",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Concrete Termin render pass bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.render_passes", "termin_render_pass_specs"],
    package_dir={
        "termin.render_passes": "python/termin/render_passes",
        "termin_render_pass_specs": "python/termin_render_pass_specs",
    },
    install_requires=[
        "tcbase",
        "termin-nanobind",
        "termin-render",
        "termin-components-render",
        "termin-components-ui",
        "termin-inspect",
        "tgfx",
        "numpy",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
