#!/usr/bin/env python3

# termin-navmesh owns the C navmesh registry plus the Recast-backed C++
# components and _navmesh_native Python extension. Some high-level Python
# helper modules are still transitional and may import editor/render utilities.

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
    python_requires=">=3.14",
    packages=["termin.navmesh", "termin_navmesh_component_specs"],
    package_dir={
        "termin.navmesh": "python/termin/navmesh",
        "termin_navmesh_component_specs": "python/termin_navmesh_component_specs",
    },
    install_requires=[
        "tcbase",
        "tgfx",
        "termin-assets",
        "termin-components-mesh",
        "termin-inspect",
        "termin-input",
        "termin-materials",
        "termin-nanobind",
        "termin-render",
        "termin-scene",
        "termin-voxels",
    ],
    ext_modules=native_extensions_for_source(_DIR),
    cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
    zip_safe=False,
)
