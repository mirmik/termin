#!/usr/bin/env python3

from setuptools import setup, find_namespace_packages
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
from termin_build.setup_helpers import native_extensions_for_source
import os

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    # Main termin's own C++ native modules, built by termin/cpp/python_bindings.cmake:
    #   _native          — monolithic render/editor/scene/skeleton/inspect kernel
    #   _voxels_native   — VoxelGrid + voxelization (termin.voxels)
    #
    # These are NOT yet extracted into standalone pip subprojects. cmake_ext
    # copies their pre-built .so files from TERMIN_BINDINGS_DIR/build/.../bin
    # into the wheel. The actual CMake build is driven by termin/build.sh and
    # build-sdk-bindings.sh, not by pip.
    source_dir = _DIR


if __name__ == "__main__":
    setup(
        name="termin-app",
        # find_namespace_packages picks up directories without __init__.py too
        # (e.g. transitional namespace dirs, or leftover subdirs that contain
        # only .py submodules). find_packages would drop them silently.
        # find_namespace_packages picks up directories without __init__.py too.
        # Exclude subpackages that are already shipped as separate pip packages
        # (termin-display, termin-render, termin-scene, etc.) to avoid
        # overwriting their __init__.py files.
        packages=find_namespace_packages(
            include=["termin", "termin.*"],
            exclude=[
                "tests", "tests.*", "examples", "examples.*",
                # Exclude subpackages shipped by separate pip packages.
                # Only list namespaces that are actually installed by those packages.
                "termin.collision", "termin.collision.*",       # termin-collision
                "termin.colliders", "termin.colliders.*",       # termin-collision
                "termin.render_framework", "termin.render_framework.*",  # termin-render
                "termin.render", "termin.render.*",             # termin-render
                "termin.render_passes", "termin.render_passes.*",  # termin-render-passes
                "termin.display", "termin.display.*",           # termin-display
                "termin.viewport", "termin.viewport.*",         # termin-display
                "termin.geombase", "termin.geombase.*",         # tcbase
                "termin.materials", "termin.materials.*",       # termin-materials
                "termin.scene", "termin.scene.*",               # termin-scene
                "termin.input", "termin.input.*",               # termin-input
                "termin.inspect", "termin.inspect.*",           # termin-inspect
                "termin.mesh", "termin.mesh.*",                 # termin-components-mesh
                "termin.engine", "termin.engine.*",             # termin-engine
                "termin.skeleton", "termin.skeleton.*",         # termin-skeleton
                "termin.animation", "termin.animation.*",       # termin-animation
                "termin.physics", "termin.physics.*",           # termin-physics
                "termin.navmesh", "termin.navmesh.*",           # termin-navmesh
                "termin.lighting", "termin.lighting.*",         # termin-lighting
                "termin.render_components", "termin.render_components.*",  # termin-components-render
                "termin.kinematic", "termin.kinematic.*",       # termin-components-kinematic
                "termin.fem", "termin.fem.*",                   # termin-qopt
                "termin.linalg", "termin.linalg.*",             # termin-qopt
                "termin.robot", "termin.robot.*",               # termin-qopt
                "termin.ga201", "termin.ga201.*",               # termin-pga
                "termin.geomalgo", "termin.geomalgo.*",         # termin-pga
            ],
        ),
        python_requires='>3.10.0',
        version=BuildExt.compute_local_version("0.0.0"),
        license="MIT",
        description="3D editor for computer games and physical simulation",
        author="mirmik",
        author_email="mirmikns@yandex.ru",
        url="https://github.com/mirmik/termin",
        long_description=open(os.path.join(
            _DIR, "README.md"), "r", encoding="utf8").read(),
        long_description_content_type="text/markdown",
        keywords=["testing", "cad"],
        classifiers=[],
        package_data={
            "termin": [
                # Header files for external C++ module compilation
                "include/**/*.h",
                "include/**/*.hpp",
                # Standard library (shaders, materials, icons, ui)
                "resources/**/*",
                # Data files used by main termin Python stack
                "**/*.ui",
                "**/*.uiscript",
                "**/*.glsl",
                "**/*.shader",
                "**/*.material",
                "**/*.meta",
                "**/*.png",
                "**/*.txt",
            ]
        },
        include_package_data=True,
        install_requires=[
            "tcbase",
            "termin-assets",
            "termin-materials",
            "termin-render-passes",
            "termin-nanobind",
            "numpy",
            "PyOpenGL>=3.1",
            "glfw>=2.5.0",
            "Pillow>=9.0",
            "scipy",
        ],
        ext_modules=native_extensions_for_source(_DIR),
        cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
        zip_safe=False,
    )
