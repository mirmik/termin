from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_taskfile_is_the_cross_platform_public_command_interface() -> None:
    taskfile = (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8")

    for task_name in (
        "build",
        "test",
        "smoke",
        "build:android",
        "build:web",
        "docs:build",
        "docs:serve",
    ):
        assert f"  {task_name}:\n" in taskfile

    assert "./scripts/build/sdk.sh" in taskfile
    assert "./scripts/build/sdk.ps1" in taskfile
    assert "./scripts/test/all.sh" in taskfile
    assert "./scripts/test/all.ps1" in taskfile
    assert "\\" not in taskfile


def test_root_has_no_platform_launcher_scripts() -> None:
    root_launchers = [
        path.name
        for path in REPO_ROOT.iterdir()
        if path.is_file() and path.suffix in {".sh", ".ps1"}
    ]

    assert root_launchers == []


def test_internal_cross_platform_launchers_are_paired() -> None:
    expected_pairs = (
        ("build", "sdk"),
        ("build", "bindings"),
        ("build", "cpp"),
        ("test", "all"),
        ("test", "cpp"),
        ("test", "python"),
        ("test", "setup-python-env"),
    )

    for directory, stem in expected_pairs:
        assert (REPO_ROOT / "scripts" / directory / f"{stem}.sh").is_file()
        assert (REPO_ROOT / "scripts" / directory / f"{stem}.ps1").is_file()


def test_native_test_graph_has_no_cached_derived_toggles() -> None:
    """Keep repeated configure independent from the previous product mode."""
    allowed_test_options = {
        "TERMIN_BUILD_TESTS",
        "TERMIN_BUILD_TGFX2_TESTS",
        "TERMIN_BUILD_WINDOW_TESTS",
        # C# tests use a separate dotnet build and are not part of CTest.
        "TERMIN_CSHARP_BUILD_TESTS",
    }
    option_pattern = re.compile(r"option\(\s*([A-Za-z0-9_]*TEST[A-Za-z0-9_]*)")
    discovered: dict[str, list[str]] = {}

    for cmake_path in sorted(REPO_ROOT.rglob("CMakeLists.txt")):
        relative_path = cmake_path.relative_to(REPO_ROOT)
        if relative_path.parts[0] in {"build", "sdk", "termin-thirdparty"}:
            continue
        for option_name in option_pattern.findall(cmake_path.read_text(encoding="utf-8")):
            discovered.setdefault(option_name, []).append(relative_path.as_posix())

    unexpected = {
        option_name: paths
        for option_name, paths in discovered.items()
        if option_name not in allowed_test_options
    }
    assert unexpected == {}


def test_web_toolchain_uses_a_shared_versioned_cache() -> None:
    setup = (REPO_ROOT / "scripts/build/setup-web-toolchain.sh").read_text(
        encoding="utf-8"
    )
    web_build = (REPO_ROOT / "scripts/build/web.sh").read_text(encoding="utf-8")

    assert "XDG_CACHE_HOME" in setup
    assert "termin/toolchains/emscripten/$version/emsdk" in setup
    assert "TERMIN_EMSDK_DIR" in setup
    assert 'flock 9' in setup
    assert 'setup-web-toolchain.sh\" --print-path' in web_build
    assert '[[ ! -x "$emcmake" || ! -x "$emcc" ]]' in web_build
