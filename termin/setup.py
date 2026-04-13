#!/usr/bin/env python3

from setuptools import setup, find_namespace_packages, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
import os

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    # Main termin's own C++ native modules, built by termin/cpp/python_bindings.cmake:
    #   _native          — monolithic render/editor/scene/skeleton/inspect kernel
    #   _voxels_native   — VoxelGrid + voxelization (termin.voxels)
    #
    # These are NOT yet extracted into standalone pip subprojects. Thin-mode
    # cmake_ext copies their pre-built .so files from
    # $TERMIN_SDK/lib/python/termin/ into the wheel. The actual CMake build is
    # driven by termin/build.sh and build-sdk-bindings.sh, not by pip.
    module_names = ["_native", "_voxels_native"]
    source_dir = _DIR


if __name__ == "__main__":
    setup(
        name="termin",
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
                # Shipped by termin-base
                "termin.geombase", "termin.geombase.*",
                # Shipped by termin-collision
                "termin.collision", "termin.collision.*",
                "termin.colliders", "termin.colliders.*",
                # Shipped by termin-render
                "termin.render_framework", "termin.render_framework.*",
                "termin.render", "termin.render.*",
                # Shipped by termin-display
                "termin.display", "termin.display.*",
                "termin.viewport", "termin.viewport.*",
                # Shipped by termin-scene
                "termin.scene", "termin.scene.*",
                # Shipped by termin-entity
                "termin.entity", "termin.entity.*",
                # Shipped by termin-input
                "termin.input", "termin.input.*",
                # Shipped by termin-inspect
                "termin.inspect", "termin.inspect.*",
                # Shipped by termin-mesh (as tmesh)
                "termin.mesh", "termin.mesh.*",
                # Shipped by termin-engine
                "termin.engine", "termin.engine.*",
                # Shipped by termin-skeleton
                "termin.skeleton", "termin.skeleton.*",
                # Shipped by termin-animation
                "termin.animation", "termin.animation.*",
                # Shipped by termin-physics
                "termin.physics", "termin.physics.*",
                # Shipped by termin-navmesh
                "termin.navmesh", "termin.navmesh.*",
                # Shipped by termin-lighting
                "termin.lighting", "termin.lighting.*",
                # Shipped by termin-components-render
                "termin.render_components", "termin.render_components.*",
                # Shipped by termin-components-mesh
                "termin.mesh_components", "termin.mesh_components.*",
                # Shipped by termin-components-kinematic
                "termin.kinematic", "termin.kinematic.*",
            ],
        ),
        python_requires='>3.10.0',
        version="0.0.0",
        license="MIT",
        description="Projective geometry library",
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
            "termin-nanobind",
            "numpy",
            "PyOpenGL>=3.1",
            "glfw>=2.5.0",
            "Pillow>=9.0",
            "pyassimp",
            "scipy",
            "PyQt6>=6.4",
        ],
        ext_modules=[
            Extension("termin._native", sources=[]),
            Extension("termin.voxels._voxels_native", sources=[]),
        ],
        cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
        zip_safe=False,
    )
