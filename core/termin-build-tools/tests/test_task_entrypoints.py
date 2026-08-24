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
        "package:graphics:python",
        "docs:build",
        "docs:serve",
    ):
        assert f"  {task_name}:\n" in taskfile

    assert "./scripts/build/sdk.sh" in taskfile
    assert "./scripts/build/sdk.ps1" in taskfile
    assert "./scripts/build/graphics-python.sh" in taskfile
    assert "./scripts/test/all.sh" in taskfile
    assert "./scripts/test/all.ps1" in taskfile
    assert "\\" not in taskfile

    bindings = (REPO_ROOT / "scripts" / "build" / "bindings.sh").read_text(
        encoding="utf-8"
    )
    assert "TERMIN_USE_BUNDLED_SDL2" in bindings


def test_windows_sdk_wrapper_resolves_profiled_output_from_canonical_manifest() -> None:
    windows_script = (REPO_ROOT / "scripts" / "build" / "sdk.ps1").read_text(
        encoding="utf-8"
    )

    assert '"build-system\\sdk-profiles.json"' in windows_script
    assert "Where-Object { $_.id -eq $sdkProfile }" in windows_script
    assert "Join-Path $ScriptDir $profile.sdk_prefix" in windows_script
    assert 'Join-Path $ScriptDir "sdk"' not in windows_script


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


def test_sdl_capability_has_no_stale_derived_cache_toggle() -> None:
    for relative in (
        "graphics/termin-window/CMakeLists.txt",
        "engine/termin-display/CMakeLists.txt",
        "editor/termin-app/cpp/CMakeLists.txt",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "option(USE_SYSTEM_SDL2" not in source

    sdl_module = (REPO_ROOT / "cmake" / "TerminSDL2.cmake").read_text(
        encoding="utf-8"
    )
    assert "if(NOT TERMIN_ENABLE_SDL)" in sdl_module

    gui_native = (
        REPO_ROOT / "graphics" / "termin-gui-native" / "CMakeLists.txt"
    ).read_text(encoding="utf-8")
    assert "set(TERMIN_GUI_NATIVE_BUILD_WINDOW_INTEGRATION ${TERMIN_ENABLE_SDL})" in gui_native
    assert "option(TERMIN_GUI_NATIVE_BUILD_WINDOW_INTEGRATION" not in gui_native


def test_graphics_backend_cache_follows_repository_switches() -> None:
    """Do not retain tgfx2 backends from an earlier configure."""
    graphics_composition = (
        REPO_ROOT / "graphics" / "CMakeLists.txt"
    ).read_text(encoding="utf-8")

    for backend in ("OPENGL", "WEBGL2", "VULKAN"):
        assert re.search(
            rf"set\(TGFX2_ENABLE_{backend}\s+"
            rf'"\$\{{TERMIN_ENABLE_{backend}\}}"\s+CACHE\s+BOOL\s+'
            rf'"[^"]+"\s+FORCE\)',
            graphics_composition,
        )


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
