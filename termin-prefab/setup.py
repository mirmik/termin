#!/usr/bin/env python3

import os

from setuptools import find_namespace_packages, setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source


_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-prefab",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="Prefab runtime and asset integration for Termin",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.10",
    packages=find_namespace_packages(where="python", include=["termin.prefab", "termin.prefab.*"]),
    package_dir={"": "python"},
    install_requires=[
        "termin-assets",
        "termin-inspect",
        "termin-nanobind",
        "termin-scene",
        "tcbase",
        "numpy",
    ],
    entry_points={
        "termin.asset_import_plugins": [
            "prefab = termin.prefab.asset_plugin:create_import_plugin",
        ],
        "termin.asset_runtime_plugins": [
            "prefab = termin.prefab.asset_plugin:create_runtime_plugin",
        ],
    },
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
