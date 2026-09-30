from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest


class LauncherProject:
    def __init__(self, root: Path, generator: str) -> None:
        self.root = root
        self.build_dir = root / "build"
        self.generator = generator
        self.ccache_log = root / "ccache.log"
        self.custom_log = root / "custom.log"
        self.ccache = self.make_launcher("ccache", self.ccache_log)
        self.custom = self.make_launcher("custom", self.custom_log)
        module = (
            Path(__file__).resolve().parents[3]
            / "cmake"
            / "TerminCompilerLauncher.cmake"
        )
        (root / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.19)\n"
            "project(compiler_launcher_regression LANGUAGES C CXX)\n"
            "option(TERMIN_USE_CCACHE \"Use ccache\" ON)\n"
            "option(TEST_MSVC_POLICY \"Exercise MSVC launcher policy\" OFF)\n"
            "set(MSVC ${TEST_MSVC_POLICY})\n"
            f'include("{module.as_posix()}")\n'
            "add_library(sample STATIC sample.c sample.cpp)\n",
            encoding="utf-8",
        )
        (root / "sample.c").write_text("int c_sample(void) { return 1; }\n")
        (root / "sample.cpp").write_text("int cxx_sample() { return 2; }\n")

    def make_launcher(self, name: str, log: Path) -> Path:
        script = self.root / f"{name}.py"
        script.write_text(
            "import pathlib, subprocess, sys\n"
            f"with pathlib.Path({str(log)!r}).open('a') as output:\n"
            "    output.write(repr(sys.argv[1:]) + '\\n')\n"
            "raise SystemExit(subprocess.call(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        launcher = self.root / (f"{name}.cmd" if os.name == "nt" else name)
        if os.name == "nt":
            launcher.write_text(f'@"{sys.executable}" "{script}" %*\n')
        else:
            launcher.write_text(
                f"#!/bin/sh\nexec {shlex.quote(sys.executable)} "
                f'{shlex.quote(str(script))} "$@"\n'
            )
            launcher.chmod(0o755)
        return launcher

    def run(self, *args: str) -> None:
        environment = os.environ.copy()
        # These tests own their launchers, regardless of the outer build setup.
        environment.pop("CMAKE_C_COMPILER_LAUNCHER", None)
        environment.pop("CMAKE_CXX_COMPILER_LAUNCHER", None)
        result = subprocess.run(
            ["cmake", *args],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        assert result.returncode == 0, result.stdout

    def configure(self, enabled: bool, *args: str) -> None:
        self.run(
            "-S", str(self.root), "-B", str(self.build_dir),
            "-G", self.generator,
            f"-DTERMIN_CCACHE_PROGRAM:FILEPATH={self.ccache.as_posix()}",
            f"-DTERMIN_USE_CCACHE:BOOL={'ON' if enabled else 'OFF'}",
            *args,
        )

    def build(self) -> None:
        self.run("--build", str(self.build_dir), "--clean-first")

    def cache(self) -> dict[str, str]:
        values = {}
        for line in (self.build_dir / "CMakeCache.txt").read_text().splitlines():
            if line and not line.startswith(("#", "//")):
                key, value = line.split("=", 1)
                values[key.split(":", 1)[0]] = value
        return values

    def invocations(self, log: Path) -> list[str]:
        return log.read_text().splitlines() if log.exists() else []


@pytest.fixture
def project(tmp_path: Path) -> LauncherProject:
    if not shutil.which("cmake"):
        pytest.skip("CMake is required for compiler launcher regression tests")
    if shutil.which("ninja"):
        generator = "Ninja"
    elif os.name != "nt" and shutil.which("make"):
        generator = "Unix Makefiles"
    else:
        pytest.skip("Ninja or Unix Makefiles is required for launcher tests")
    return LauncherProject(tmp_path, generator)


@pytest.mark.parametrize("legacy_cache", [False, True])
@pytest.mark.parametrize("disabled_by", ["option", "msvc"])
def test_ccache_reconfiguration_really_disables_and_reenables_compilation(
    project: LauncherProject, legacy_cache: bool, disabled_by: str
) -> None:
    project.configure(True)
    project.build()
    first_calls = project.invocations(project.ccache_log)
    assert len(first_calls) == 2
    assert any("sample.c'" in call or 'sample.c"' in call for call in first_calls)
    assert any("sample.cpp'" in call or 'sample.cpp"' in call for call in first_calls)

    options = ["-U_TERMIN_*_CCACHE_LAUNCHER"] if legacy_cache else []
    if disabled_by == "msvc":
        options.append("-DTEST_MSVC_POLICY=ON")
    project.configure(disabled_by == "msvc", *options)
    for language in ("C", "CXX"):
        assert project.cache()[f"CMAKE_{language}_COMPILER_LAUNCHER"] == ""
    project.build()
    assert project.invocations(project.ccache_log) == first_calls

    project.configure(True, "-DTEST_MSVC_POLICY=OFF")
    project.build()
    assert len(project.invocations(project.ccache_log)) == 4


@pytest.mark.parametrize("disabled_by", ["option", "msvc"])
def test_explicit_launcher_survives_replacing_owned_ccache(
    project: LauncherProject, disabled_by: str
) -> None:
    project.configure(True)
    options = [f"-DCMAKE_C_COMPILER_LAUNCHER:STRING={project.custom.as_posix()}"]
    if disabled_by == "msvc":
        options.append("-DTEST_MSVC_POLICY=ON")
    project.configure(disabled_by == "msvc", *options)
    assert project.cache()["CMAKE_C_COMPILER_LAUNCHER"] == project.custom.as_posix()
    assert project.cache()["CMAKE_CXX_COMPILER_LAUNCHER"] == ""
    project.build()
    assert len(project.invocations(project.custom_log)) == 1
    assert project.invocations(project.ccache_log) == []

    project.configure(True, "-DTEST_MSVC_POLICY=OFF")
    project.build()
    assert len(project.invocations(project.custom_log)) == 2
    assert len(project.invocations(project.ccache_log)) == 1
