#!/usr/bin/env python3

from setuptools import setup, find_packages, Extension
from termin_build.cmake_ext import TerminCMakeBuild, TerminCMakeBuildExt
import os

_DIR = os.path.dirname(os.path.realpath(__file__))


class BuildExt(TerminCMakeBuildExt):
    # Main termin's own C++ monolith: termin._native (render/editor/scene
    # kernel, built by termin/cpp/python_bindings.cmake). Thin-mode cmake_ext
    # copies this pre-built .so from $TERMIN_SDK/lib/python/termin/_native.*.so
    # into the wheel. CMake build itself is driven by termin/build.sh and
    # build-sdk-bindings.sh — not by pip.
    module_names = ["_native"]
    source_dir = _DIR


if __name__ == "__main__":
    setup(
        name="termin",
        packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
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
                # Standard library (shaders, materials, etc.)
                "resources/**/*",
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
        ],
        cmdclass={"build": TerminCMakeBuild, "build_ext": BuildExt},
        zip_safe=False,
    )
