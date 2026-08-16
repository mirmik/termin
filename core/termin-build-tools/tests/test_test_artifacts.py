from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from termin_build.artifact_resolution import (
    ArtifactResolutionError,
    resolve_sdk_shader_compiler,
    resolve_shader_compiler,
)


def _write_cache(build_dir: Path, *, multi_config: bool) -> None:
    build_dir.mkdir(parents=True)
    configuration_types = (
        "CMAKE_CONFIGURATION_TYPES:STRING=Debug;Release\n" if multi_config else "CMAKE_BUILD_TYPE:STRING=Release\n"
    )
    (build_dir / "CMakeCache.txt").write_text(
        configuration_types,
        encoding="utf-8",
    )


def test_resolve_shader_compiler_from_linux_single_config_graph(
    tmp_path: Path,
) -> None:
    build_dir = tmp_path / "custom-build"
    _write_cache(build_dir, multi_config=False)
    compiler = build_dir / "bin" / "termin_shaderc"
    compiler.parent.mkdir()
    compiler.touch()

    assert resolve_shader_compiler(build_dir, "Release", "linux") == compiler


def test_resolve_shader_compiler_from_windows_multi_config_graph(
    tmp_path: Path,
) -> None:
    build_dir = tmp_path / "custom-build"
    _write_cache(build_dir, multi_config=True)
    compiler = build_dir / "bin" / "Debug" / "termin_shaderc.exe"
    compiler.parent.mkdir(parents=True)
    compiler.touch()

    assert resolve_shader_compiler(build_dir, "Debug", "windows") == compiler


def test_resolver_does_not_fall_back_to_unrelated_layout(
    tmp_path: Path,
) -> None:
    build_dir = tmp_path / "current"
    _write_cache(build_dir, multi_config=True)
    stale_compiler = build_dir / "bin" / "termin_shaderc.exe"
    stale_compiler.parent.mkdir()
    stale_compiler.touch()

    with pytest.raises(
        ArtifactResolutionError,
        match=r"bin[/\\]Release[/\\]termin_shaderc\.exe",
    ):
        resolve_shader_compiler(build_dir, "Release", "windows")


def _write_sdk_capabilities(sdk_root: Path, tool_path: str) -> None:
    sdk_root.mkdir(parents=True)
    (sdk_root / "termin-sdk-capabilities.json").write_text(
        json.dumps(
            {
                "version": 1,
                "sdk_version": "",
                "platforms": {},
                "tools": {"termin_shaderc": tool_path},
            }
        ),
        encoding="utf-8",
    )


def test_resolve_shader_compiler_from_installed_sdk(tmp_path: Path) -> None:
    sdk_root = tmp_path / "sdk"
    _write_sdk_capabilities(sdk_root, "bin/termin_shaderc")
    compiler = sdk_root / "bin" / "termin_shaderc"
    compiler.parent.mkdir()
    compiler.touch()

    assert resolve_sdk_shader_compiler(sdk_root, "linux") == compiler


def test_sdk_shader_compiler_must_be_declared_inside_sdk(tmp_path: Path) -> None:
    sdk_root = tmp_path / "sdk"
    _write_sdk_capabilities(sdk_root, "../termin_shaderc")
    (tmp_path / "termin_shaderc").touch()

    with pytest.raises(ArtifactResolutionError, match="escapes the SDK root"):
        resolve_sdk_shader_compiler(sdk_root, "linux")


def test_sdk_shader_compiler_rejects_platform_mismatch(tmp_path: Path) -> None:
    sdk_root = tmp_path / "sdk"
    _write_sdk_capabilities(sdk_root, "bin/termin_shaderc")
    compiler = sdk_root / "bin" / "termin_shaderc"
    compiler.parent.mkdir()
    compiler.touch()

    with pytest.raises(ArtifactResolutionError, match="wrong executable name"):
        resolve_sdk_shader_compiler(sdk_root, "windows")


def test_test_runners_have_no_legacy_release_tests_fallback() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    runner_paths = (
        repo_root / "scripts/test/all.sh",
        repo_root / "scripts/test/all.ps1",
        repo_root / "scripts/test/python.sh",
        repo_root / "scripts/test/python.ps1",
    )

    for runner_path in runner_paths:
        source = runner_path.read_text(encoding="utf-8")
        assert "Release-tests" not in source

    ci_workflow = (repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Release-tests" not in ci_workflow
    assert ci_workflow.count("build/Release/ctest-execution-manifest.json") == 2


def test_python_runners_resolve_shader_compiler_from_sdk() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    for suffix in ("sh", "ps1"):
        central = (repo_root / "scripts/test" / f"all.{suffix}").read_text(encoding="utf-8")
        python = (repo_root / "scripts/test" / f"python.{suffix}").read_text(encoding="utf-8")

        assert "sdk-shader-compiler" in python
        assert "TERMIN_SHADERC remains an explicit override" in python
        assert "sdk-shader-compiler" not in central
        assert "TERMIN_SHADERC=" not in central


def test_downloaded_sdk_layout_is_resolved_by_its_bundled_python() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    action = (repo_root / ".github/actions/resolve-sdk-python/action.yml").read_text(encoding="utf-8")
    package_python_action = (repo_root / ".github/actions/prepare-sdk-package-python/action.yml").read_text(
        encoding="utf-8"
    )
    workflow = (repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert '"$GITHUB_WORKSPACE/sdk/bin/termin_python" -I' in action
    assert "PYTHONPATH=" not in action
    permission_then_resolve = """      - name: Restore SDK executable permissions
        run: chmod +x sdk/bin/*

      - name: Resolve SDK Python layout
        uses: ./.github/actions/resolve-sdk-python"""
    assert workflow.count(permission_then_resolve) == 3
    assert "prepare-python-toolchain" in package_python_action
    assert "build/python-runtime/build-env/bin/python" in package_python_action
    assert "PYTHON_BIN=$package_python" in package_python_action
    assert workflow.count("uses: ./.github/actions/prepare-sdk-package-python") == 3
    assert "PYTHON_BIN: ${{ github.workspace }}/sdk/bin/termin_python" in workflow
    assert "cd editor/termin-app" not in workflow
    assert "editor/termin-app/install" not in workflow
    python_runner = (repo_root / "scripts/test/python.sh").read_text(encoding="utf-8")
    assert 'export TERMIN_PYTHON_OVERLAY="$OVERLAY_MANIFEST"' in python_runner
    cpp_lint = (repo_root / "scripts/test/lint-cpp.sh").read_text(encoding="utf-8")
    assert '-DPython_EXECUTABLE="$PYTHON_FOR_CMAKE"' in cpp_lint
    assert "python -m pip install setuptools==83.0.0 wheel==0.47.0" not in workflow


def test_central_runners_propagate_window_capability_to_python_planner() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    for suffix in ("sh", "ps1"):
        central = (repo_root / "scripts/test" / f"all.{suffix}").read_text(encoding="utf-8")
        python = (repo_root / "scripts/test" / f"python.{suffix}").read_text(encoding="utf-8")

        assert "TERMIN_TEST_CAPABILITIES" in central
        assert "--no-sdl" in central
        assert "TERMIN_TEST_CAPABILITIES" in python
        assert "--capability" in python


def test_cpp_runners_build_shader_compiler_for_native_tests() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    root_cmake = (repo_root / "CMakeLists.txt").read_text(encoding="utf-8")

    # Native shader CTests use the compiler from their active CMake graph.
    # The aggregate dependency prevents them from consuming a stale executable;
    # Python tests independently use the installed SDK tool.
    assert "add_dependencies(termin_native_tests termin_shaderc)" in root_cmake
    assert "add_dependencies(termin_native_tests_with_window termin_shaderc)" in root_cmake


def test_cpp_runners_build_exact_planner_selected_aggregate() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    linux_runner = (repo_root / "scripts/test/cpp.sh").read_text(encoding="utf-8")
    windows_runner = (repo_root / "scripts/test/cpp.ps1").read_text(encoding="utf-8")

    assert "--build-aggregate" in linux_runner
    assert '--target "$CTEST_BUILD_AGGREGATE"' in linux_runner
    assert "--build-aggregate" in windows_runner
    assert "-Target @($CtestBuildAggregate)" in windows_runner


def test_cpp_runners_isolate_ctest_temporary_and_shader_cache_roots() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    linux_runner = (repo_root / "scripts/test/cpp.sh").read_text(encoding="utf-8")
    windows_runner = (repo_root / "scripts/test/cpp.ps1").read_text(encoding="utf-8")

    assert 'CTEST_RUNTIME_ROOT="$BUILD_DIR/ctest-runtime"' in linux_runner
    assert 'export TMPDIR="$CTEST_TEMP_ROOT"' in linux_runner
    assert 'export TERMIN_SDK_SHADER_CACHE_ROOT="$CTEST_SHADER_CACHE_ROOT"' in linux_runner
    assert '$CtestRuntimeRoot = Join-Path $BuildDir "ctest-runtime"' in windows_runner
    assert '$env:TEMP = $CtestTempRoot' in windows_runner
    assert '$env:TERMIN_SDK_SHADER_CACHE_ROOT = $CtestShaderCacheRoot' in windows_runner


def test_native_test_aggregates_follow_configured_backend_capabilities(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source_dir = tmp_path / "source"
    build_dir = tmp_path / "build"
    source_dir.mkdir()
    (source_dir / "test.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    metadata = (repo_root / "cmake/TerminTestMetadata.cmake").as_posix()
    (source_dir / "CMakeLists.txt").write_text(
        f"""cmake_minimum_required(VERSION 3.19)
project(test_metadata LANGUAGES CXX)
enable_testing()
set(TGFX2_ENABLE_VULKAN OFF)
include(\"{metadata}\")

foreach(target IN ITEMS host_test vulkan_test window_test)
    add_executable(${{target}} test.cpp)
    add_test(NAME ${{target}} COMMAND ${{target}})
endforeach()
termin_add_test_labels(vulkan_test \"termin:capability:vulkan\")
termin_add_test_labels(window_test \"termin:capability:window\")
termin_label_tests_in_directory(\"test-module\")

get_property(headless GLOBAL PROPERTY TERMIN_NATIVE_TEST_TARGETS)
get_property(with_window GLOBAL PROPERTY TERMIN_NATIVE_TEST_TARGETS_WITH_WINDOW)
list(SORT headless)
list(SORT with_window)
file(WRITE \"${{CMAKE_BINARY_DIR}}/aggregates.txt\"
    \"headless=${{headless}}\\nwith_window=${{with_window}}\\n\")
""",
        encoding="utf-8",
    )

    subprocess.run(
        ["cmake", "-S", str(source_dir), "-B", str(build_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (build_dir / "aggregates.txt").read_text(encoding="utf-8") == (
        "headless=host_test\n"
        "with_window=host_test;window_test\n"
    )


def test_windows_cmake_helper_builds_multiple_targets_as_one_solution_graph() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    helper = (repo_root / "scripts" / "Invoke-CMakeBuild.ps1").read_text(encoding="utf-8")

    assert "$Target.Count -gt 1" in helper
    assert "\"/t:$($Target -join ';')\"" in helper
    assert "Get-TerminVisualStudioSolution" in helper
    assert "& $msbuildPath @msbuildArgs" in helper
