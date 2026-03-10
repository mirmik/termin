#!/usr/bin/env python3

from pathlib import Path
import shutil
import subprocess
import sys
import os

from setuptools import Extension, setup
from setuptools.command.build import build as _build
from setuptools.command.build_ext import build_ext


ROOT = Path(__file__).resolve().parent


def _split_prefix_path(raw):
    if not raw:
        return []
    normalized = raw.replace(";", os.pathsep)
    return [part for part in normalized.split(os.pathsep) if part]


class CMakeBuild(_build):
    def run(self):
        self.run_command("build_ext")
        super().run()


class CMakeBuildExt(build_ext):
    def _find_built_module(self, build_temp: Path) -> Path:
        patterns = [
            "_termin_modules_native.*.so",
            "_termin_modules_native.*.pyd",
            "_termin_modules_native.so",
            "_termin_modules_native.pyd",
        ]
        for pattern in patterns:
            matches = list(build_temp.glob(pattern))
            if matches:
                return matches[0]
        raise RuntimeError("CMake build did not produce _termin_modules_native")

    def _ensure_cmake_build(self):
        if getattr(self, "_cmake_ready", False):
            return

        build_temp = Path(self.build_temp)
        build_temp.mkdir(parents=True, exist_ok=True)

        cfg = "Debug" if self.debug else "Release"
        cmake_args = [
            str(ROOT),
            f"-DCMAKE_BUILD_TYPE={cfg}",
            f"-DPython_EXECUTABLE={sys.executable}",
        ]

        prefix_paths = _split_prefix_path(os.environ.get("CMAKE_PREFIX_PATH"))
        if prefix_paths:
            cmake_args.append(f"-DCMAKE_PREFIX_PATH={';'.join(prefix_paths)}")

        subprocess.check_call(["cmake", *cmake_args], cwd=build_temp)
        subprocess.check_call(
            ["cmake", "--build", ".", "--config", cfg, "--parallel"],
            cwd=build_temp,
        )

        self._built_module = self._find_built_module(build_temp)
        self._cmake_ready = True

    def build_extension(self, ext):
        self._ensure_cmake_build()

        ext_path = Path(self.get_ext_fullpath(ext.name))
        ext_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._built_module, ext_path)


setup(
    name="termin-modules",
    version="0.1.0",
    license="MIT",
    description="Runtime module loader for termin projects",
    author="mirmik",
    author_email="mirmikns@yandex.ru",
    python_requires=">=3.8",
    packages=["termin_modules"],
    package_dir={"termin_modules": "python/termin_modules"},
    ext_modules=[Extension("termin_modules._termin_modules_native", sources=[])],
    cmdclass={"build": CMakeBuild, "build_ext": CMakeBuildExt},
    zip_safe=False,
)
