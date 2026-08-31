from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build import sdk
from termin_build.python_abi import PythonAbiError

from termin_build.package_manifest import (
    CANONICAL_REQUIRES_PYTHON,
    load_manifest,
    package_requires_python,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_all_sdk_packages_require_python_314() -> None:
    for package in load_manifest(REPO_ROOT):
        package_dir = REPO_ROOT / package.path
        assert (
            package_requires_python(package_dir)
            == CANONICAL_REQUIRES_PYTHON
        ), package.path


def test_toolchain_lock_is_the_only_runtime_identity() -> None:
    lock = json.loads(
        (REPO_ROOT / "build-system/python-toolchain-lock.json").read_text(
            encoding="utf-8"
        )
    )
    assert lock["version"] == "3.14.6"
    assert lock["default_variant"] == "cp314t"
    assert set(lock["variants"]) == {"cp314", "cp314t"}
    assert lock["variants"]["cp314t"]["python_abi"] == {
        "version": "3.14",
        "free_threaded": True,
        "py_gil_disabled": True,
    }
    assert lock["variants"]["cp314"]["python_abi"] == {
        "version": "3.14",
        "free_threaded": False,
        "py_gil_disabled": False,
    }

    cmake_contract = (
        REPO_ROOT / "cmake/TerminPython.cmake"
    ).read_text(encoding="utf-8")
    assert "include_guard(DIRECTORY)" in cmake_contract
    assert 'TERMIN_CANONICAL_PYTHON_VERSION "3.14"' in cmake_contract
    assert "Py_GIL_DISABLED" in cmake_contract
    assert "^(cpython-|cp)314t" in cmake_contract
    assert "sysconfig.get_path" in cmake_contract
    assert 'set(Python_INCLUDE_DIR "${TERMIN_PYTHON_INCLUDE_DIR}"' in (
        cmake_contract
    )
    assert 'set(Python_LIBRARY "${TERMIN_PYTHON_LIBRARY}"' in cmake_contract
    assert "Py_GIL_DISABLED=1" in cmake_contract
    assert "Py_NO_LINK_LIB" in cmake_contract
    assert "unset(NB_SUFFIX CACHE)" in cmake_contract

    installed_nanobind_contract = (
        REPO_ROOT / "core/termin-nanobind-sdk/cmake/nanobindConfig.cmake.in"
    ).read_text(encoding="utf-8")
    assert '".${_termin_nanobind_expected_python_soabi}"' in (
        installed_nanobind_contract
    )
    assert "unset(NB_SUFFIX CACHE)" in installed_nanobind_contract


def test_production_configuration_has_no_legacy_python_runtime() -> None:
    roots = [
        REPO_ROOT / ".github/workflows",
        REPO_ROOT / "cmake",
        REPO_ROOT / "CMakeLists.txt",
        REPO_ROOT / "scripts/build/bindings.sh",
        REPO_ROOT / "scripts/build/bindings.ps1",
        REPO_ROOT / "editor/termin-app",
        REPO_ROOT / "core/termin-nanobind-sdk",
    ]
    legacy_markers = (
        "python3.10",
        "Python 3.10",
        "libpython3.10",
        "cp310",
        "TERMIN_REQUIRE_FREE_THREADED_PYTHON",
        "TERMIN_EXPECTED_PYTHON_ABI_VERSION",
    )
    offenders: list[str] = []
    for root in roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or "tests" in path.parts:
                continue
            if path.suffix not in {
                "",
                ".cmake",
                ".cpp",
                ".h",
                ".md",
                ".ps1",
                ".py",
                ".sh",
                ".txt",
                ".yml",
            } and path.name != "CMakeLists.txt":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(marker in text for marker in legacy_markers):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_test_builds_cannot_overwrite_the_installed_sdk() -> None:
    render_cmake = (REPO_ROOT / "engine/termin-render/CMakeLists.txt").read_text(
        encoding="utf-8"
    )
    assert "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/" not in render_cmake


def test_explicit_release_python_is_abi_checked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sdk,
        "_python_version_and_paths",
        lambda _python: {
            "version": "3.14",
            "soabi": "cpython-314t-x86_64-linux-gnu",
            "free_threaded": True,
            "py_gil_disabled": True,
        },
    )
    expected = tmp_path / "environment" / "bin" / "python"
    monkeypatch.setattr(
        sdk,
        "_ensure_sdk_python_build_environment",
        lambda *_args, **_kwargs: expected,
    )

    assert sdk.prepare_python_build_environment(
        tmp_path,
        base_python=Path("/opt/python/cp314-cp314t/bin/python"),
        variant="cp314t",
        environment_root=tmp_path / "environment",
    ) == expected

    with pytest.raises(PythonAbiError, match="has ABI cp314t"):
        sdk.prepare_python_build_environment(
            tmp_path,
            base_python=Path("/opt/python/cp314-cp314t/bin/python"),
            variant="cp314",
            environment_root=tmp_path / "wrong-environment",
        )
