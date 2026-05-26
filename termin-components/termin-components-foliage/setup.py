#!/usr/bin/env python3

import os

from setuptools import Extension, setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt


_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    module_names = ["_foliage_native"]
    source_dir = _DIR


setup(
    name="termin-components-foliage",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Foliage component asset contracts for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=["termin.foliage"],
    package_dir={"termin.foliage": "python/termin/foliage"},
    install_requires=["termin-assets", "termin-nanobind", "termin-scene", "tmesh", "tgfx"],
    ext_modules=[
        Extension("termin.foliage._foliage_native", sources=[]),
    ],
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    entry_points={
        "termin.asset_import_plugins": [
            "foliage_data = termin.foliage.asset_plugin:create_import_plugin",
        ],
        "termin.asset_runtime_plugins": [
            "foliage_data = termin.foliage.asset_plugin:create_runtime_plugin",
        ],
    },
    zip_safe=False,
)
