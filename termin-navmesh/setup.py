#!/usr/bin/env python3

# termin-navmesh is a transitional pip facade.
#
# The C++ _navmesh_native binding currently lives inside main termin's build
# (termin/cpp/python_bindings.cmake, guarded by TERMIN_HAS_RECAST). This pip
# package does NOT build C++; it copies the pre-built _navmesh_native.so
# from $TERMIN_SDK into the package directory via TerminCMakeBuildExt
# (thin SDK-copy mode).
#
# Pure-Python algorithmic submodules (pathfinding, triangulation,
# region_growing, builder_component, …) are bundled alongside the binding.
# They depend on higher-level termin modules (visualization.core, etc.) and
# may not be usable in environments without main termin installed.

from setuptools import setup
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source

import os
_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    source_dir = _DIR


setup(
    name="termin-navmesh",
    version=BuildExt.compute_local_version("0.1.0"),
    license="MIT",
    description="NavMesh Python bindings (thin; requires termin SDK at runtime)",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin.navmesh"],
    package_dir={"termin.navmesh": "python/termin/navmesh"},
    install_requires=[
        "termin-assets",
        "termin-nanobind",
        "termin-voxels",
        "termin-components-voxels",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    entry_points={
        "termin.asset_import_plugins": [
            "navmesh = termin.navmesh.asset_plugin:create_import_plugin",
        ],
        "termin.asset_runtime_plugins": [
            "navmesh = termin.navmesh.asset_plugin:create_runtime_plugin",
        ],
    },
    zip_safe=False,
)
