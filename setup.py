#!/usr/bin/env python3

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
from distutils.util import get_platform
from pathlib import Path
import shutil
import subprocess
import sys
import os


class CMakeBuildExt(build_ext):
    """
    Build pybind11 extensions via CMake (cpp/CMakeLists.txt).
    CMake builds all native modules in one go, then installs them into build_lib/termin/*.
    """

    def run(self):
        try:
            subprocess.check_output(["cmake", "--version"])
        except OSError as exc:
            raise RuntimeError("CMake is required to build native extensions") from exc

        source_dir = Path(directory) / "cpp"
        build_temp = Path(self.build_temp)
        build_temp.mkdir(parents=True, exist_ok=True)

        build_lib = Path(self.build_lib)
        install_prefix = (build_lib / "termin").resolve()
        install_prefix.mkdir(parents=True, exist_ok=True)

        cfg = "Debug" if self.debug else "Release"
        cmake_args = [
            str(source_dir),
            f"-DCMAKE_BUILD_TYPE={cfg}",
            f"-DCMAKE_INSTALL_PREFIX={install_prefix}",
            f"-DPython_EXECUTABLE={sys.executable}",
        ]

        subprocess.check_call(["cmake", *cmake_args], cwd=build_temp)
        subprocess.check_call(["cmake", "--build", ".", "--config", cfg], cwd=build_temp)
        subprocess.check_call(["cmake", "--install", ".", "--config", cfg], cwd=build_temp)

        # Nothing else to do; CMake produced the .so/.pyd into build_lib already.
        # Mark build as done so setuptools continues.
        for ext in self.extensions:
            self._built_objects = getattr(self, "_built_objects", [])  # satisfy setuptools expectations

        # Copy all native modules into source tree for editable/pytest runs
        module_mappings = [
            ("tests", "_cpp_tests"),
            ("geombase", "_geom_native"),
            ("colliders", "_colliders_native"),
            ("physics", "_physics_native"),
            ("voxels", "_voxels_native"),
            ("collision", "_collision_native"),
        ]
        for subdir, module_name in module_mappings:
            dst_dir = Path(directory) / "termin" / subdir
            dst_dir.mkdir(parents=True, exist_ok=True)
            src_dir = install_prefix / subdir
            for so in src_dir.glob(f"{module_name}.*"):
                shutil.copy2(so, dst_dir / so.name)

directory = os.path.dirname(os.path.realpath(__file__))


if __name__ == "__main__":
    setup(
        name="termin",
        packages=["termin"],
        python_requires='>3.10.0',
        version="0.0.0",
        license="MIT",
        description="Projective geometry library",
        author="mirmik",
        author_email="mirmikns@yandex.ru",
        url="https://github.com/mirmik/termin",
        long_description=open(os.path.join(
            directory, "README.md"), "r", encoding="utf8").read(),
        long_description_content_type="text/markdown",
        keywords=["testing", "cad"],
        classifiers=[],
        package_data={
            "termin": [
                "ga201/*",
                "physics/*",
                "colliders/*",
                "collision/*",
                "fem/*",
                "kinematic/*",
                "geombase/*",
                "utils/*",
                "geomalgo/*",
                "linalg/*",
                "robot/*",
                "loaders/*",
                "visualization/*",
                "visualization/**/*",
                "mesh/*",
                "assets/*",
                "core/*",
                "editor/*",
                "tests/__init__.py",
            ]
        },
        include_package_data=True,
        install_requires=[
            "numpy",
            "PyOpenGL>=3.1",
            "glfw>=2.5.0",
            "Pillow>=9.0",
            "pyassimp",
            "scipy",
            "PyQt6>=6.4",
        ],
        extras_require={
        },
        ext_modules=[
            Extension("termin.geombase._geom_native", sources=[]),
            Extension("termin.colliders._colliders_native", sources=[]),
            Extension("termin.physics._physics_native", sources=[]),
            Extension("termin.voxels._voxels_native", sources=[]),
            Extension("termin.collision._collision_native", sources=[]),
            Extension("termin.tests._cpp_tests", sources=[]),
        ],
        cmdclass={"build_ext": CMakeBuildExt},
        zip_safe=False,
    )
