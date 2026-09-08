import re
from pathlib import Path

import pytest
from setuptools import Distribution
from setuptools.config.pyprojecttoml import apply_configuration

from termin_build import (
    artifact_manifest,
    sdk,
    sdk_product_inputs,
    sdk_runtime_metadata,
)
from termin_build.package_manifest import PackageEntry
from termin_build.setup_helpers import native_extensions_for_source


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_installed_core_environment_is_ignored_for_repository_owned_profile(
    tmp_path,
    monkeypatch,
):
    external_core = tmp_path / "external-core"
    monkeypatch.setenv(sdk_product_inputs.CORE_SDK_ENV, str(external_core))
    monkeypatch.setenv(sdk_product_inputs.CORE_BUILD_ID_ENV, "stale-build-id")

    def unexpected_load(*args, **kwargs):
        pytest.fail("repository-owned profiles must not load an installed Core SDK")

    monkeypatch.setattr(sdk_product_inputs, "load_installed_sdk_input", unexpected_load)

    result = sdk_product_inputs._installed_core_input(
        tmp_path,
        expected_python_abi=artifact_manifest.PythonAbiIdentity.current(),
        packages=(
            PackageEntry(
                path="core/termin-base",
                distribution="termin-base",
                features=(),
                native_extensions=(),
            ),
        ),
    )

    assert result is None


def test_installed_core_environment_is_used_for_external_core_profile(
    tmp_path,
    monkeypatch,
):
    external_core = tmp_path / "external-core"
    expected_input = object()
    monkeypatch.setenv(sdk_product_inputs.CORE_SDK_ENV, str(external_core))
    monkeypatch.setattr(
        sdk_product_inputs,
        "load_installed_sdk_input",
        lambda root, **kwargs: expected_input,
    )

    result = sdk_product_inputs._installed_core_input(
        tmp_path,
        expected_python_abi=artifact_manifest.PythonAbiIdentity.current(),
        packages=(
            PackageEntry(
                path="termin-base",
                distribution="termin-base",
                features=(),
                native_extensions=(),
                source="installed-core",
            ),
        ),
    )

    assert result is expected_input


def test_build_tools_package_config_excludes_generated_build_tree():
    repo_root = sdk.repo_root_from(Path(__file__))
    distribution = Distribution()

    apply_configuration(distribution, repo_root / "core" / "termin-build-tools" / "pyproject.toml")

    assert distribution.packages == ["termin_build"]


def test_native_extensions_for_source_reads_manifest():
    repo_root = sdk.repo_root_from(Path(__file__))
    extensions = native_extensions_for_source(repo_root / "core/termin-base")

    assert [extension.name for extension in extensions] == [
        "termin.base._base_native",
        "termin.base._geom_native",
    ]


def test_repository_profiles_own_distinct_runtime_locks():
    repo_root = sdk.repo_root_from(Path(__file__))
    profiles = sdk.load_sdk_profiles(repo_root)
    full_requirement_names = set(
        sdk_runtime_metadata._load_runtime_lock(repo_root, profiles.profile("full").runtime_lock)
    )
    core_requirement_names = set(
        sdk_runtime_metadata._load_runtime_lock(repo_root, profiles.profile("core").runtime_lock)
    )

    assert "scipy" not in full_requirement_names
    assert "pyopengl" not in full_requirement_names
    assert full_requirement_names == {
        "colorama",
        "exceptiongroup",
        "glfw",
        "iniconfig",
        "numpy",
        "packaging",
        "pluggy",
        "pygments",
        "pytest",
        "pyyaml",
        "tomli",
        "typing-extensions",
        "watchdog",
    }
    assert core_requirement_names == full_requirement_names


def test_repo_installs_umbrella_termin_cmake_package():
    repo_root = sdk.repo_root_from(Path(__file__))
    root_cmake = (repo_root / "CMakeLists.txt").read_text(encoding="utf-8")
    package_config = (repo_root / "cmake" / "terminConfig.cmake.in").read_text(encoding="utf-8")

    assert "cmake/terminConfig.cmake.in" in root_cmake
    assert "DESTINATION lib/cmake/termin" in root_cmake
    assert "find_dependency(termin_base CONFIG REQUIRED)" in package_config
    assert "add_library(termin::termin INTERFACE IMPORTED)" in package_config
    assert "INTERFACE_LINK_LIBRARIES tcbase::termin_base" in package_config


def test_native_test_configuration_does_not_mutate_render_product_target():
    repo_root = sdk.repo_root_from(Path(__file__))
    render_cmake = (repo_root / "engine/termin-render/CMakeLists.txt").read_text(encoding="utf-8")
    test_guard = re.search(
        r"if\(\s*TERMIN_BUILD_TESTS\b[^)]*\)",
        render_cmake,
    )
    assert test_guard is not None
    test_configuration = render_cmake[test_guard.start() :]
    product_target_mutation = re.compile(
        r"(?:target_(?:compile_definitions|compile_options|include_directories|"
        r"link_libraries|precompile_headers|sources)|set_target_properties)"
        r"\(\s*termin_render(?:\s|\))"
    )

    assert product_target_mutation.search(test_configuration) is None


def test_openxr_package_declares_all_public_target_dependencies():
    repo_root = sdk.repo_root_from(Path(__file__))
    package_config = (repo_root / "platform/termin-openxr/cmake/termin_openxrConfig.cmake.in").read_text(
        encoding="utf-8"
    )

    expected_dependencies = {
        "termin_base",
        "termin_scene",
        "termin_mesh",
        "termin_components_mesh",
        "termin_inspect",
        "termin_components_render",
        "termin_graphics",
        "termin_render",
        "termin_render_passes",
        "termin_engine",
        "termin_runtime",
        "termin_collision",
        "termin_input",
    }
    for dependency in expected_dependencies:
        assert f"find_dependency({dependency} CONFIG REQUIRED)" in package_config
