from __future__ import annotations

import json
from pathlib import Path

import pytest

from termin_build.sdk_profiles import load_sdk_profiles, write_installed_sdk_product
from termin_build.sdk_test_context import (
    TestSdkContextError as SdkContextError,
    load_configured_test_python_bindings,
    load_configured_test_sdk_profile,
    load_installed_test_sdk_profile,
    main,
    resolve_test_sdk_context,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    manifest = tmp_path / "build-system" / "sdk-profiles.json"
    manifest.parent.mkdir()
    manifest.write_bytes((REPO_ROOT / "build-system" / "sdk-profiles.json").read_bytes())
    return tmp_path


def install(repo: Path, sdk: Path, profile: str) -> None:
    write_installed_sdk_product(sdk, load_sdk_profiles(repo).profile(profile))


@pytest.mark.parametrize("profile", ("full", "graphics", "core"))
def test_product_metadata_selects_canonical_context(repo: Path, profile: str) -> None:
    suffix = "" if profile == "full" else f"-{profile}"
    sdk = repo / f"sdk{suffix}"
    install(repo, sdk, profile)
    context = resolve_test_sdk_context(repo, profile=profile, build_type="Debug", installed=True)
    assert context == {
        "profile": profile,
        "sdk-prefix": str(sdk),
        "build-dir": str(repo / "build" / f"Debug{suffix}"),
        "environment-root": str(repo / "build" / "python-envs" / f"test{suffix}"),
    }
    assert load_installed_test_sdk_profile(sdk) == profile


def test_custom_directory_identity_comes_from_metadata(repo: Path) -> None:
    sdk = repo / "arbitrary-installed-name"
    build = repo / "arbitrary-build-name"
    install(repo, sdk, "graphics")
    build.mkdir()
    (build / "CMakeCache.txt").write_text("TERMIN_SDK_PROFILE:STRING=graphics\n")
    environment = repo / "custom-test-tools"
    context = resolve_test_sdk_context(
        repo, sdk_prefix=sdk, build_dir=build, environment_root=environment, installed=True
    )
    assert context["profile"] == "graphics"
    assert context["sdk-prefix"] == str(sdk)
    assert context["build-dir"] == str(build)
    assert context["environment-root"] == str(environment)


def test_cpp_context_does_not_require_installed_sdk(repo: Path) -> None:
    assert resolve_test_sdk_context(repo, profile="core")["profile"] == "core"
    with pytest.raises(SdkContextError, match="cannot read installed SDK"):
        resolve_test_sdk_context(repo, profile="core", installed=True)


def test_configured_context_selects_product_without_sdk(repo: Path) -> None:
    build = repo / "configured"
    build.mkdir()
    (build / "CMakeCache.txt").write_text("TERMIN_SDK_PROFILE:STRING=core\n")
    assert resolve_test_sdk_context(repo, build_dir=build)["profile"] == "core"


def test_explicit_contexts_must_agree(repo: Path) -> None:
    sdk = repo / "sdk-custom"
    install(repo, sdk, "graphics")
    with pytest.raises(SdkContextError, match="conflicts"):
        resolve_test_sdk_context(repo, profile="core", sdk_prefix=sdk)
    other_sdk = repo / "other-sdk"
    install(repo, other_sdk, "graphics")
    with pytest.raises(SdkContextError, match="different SDK directories"):
        resolve_test_sdk_context(repo, sdk_prefix=sdk, termin_sdk=other_sdk)
    build = repo / "configured"
    build.mkdir()
    (build / "CMakeCache.txt").write_text("TERMIN_SDK_PROFILE:STRING=full\n")
    with pytest.raises(SdkContextError, match="conflicts"):
        resolve_test_sdk_context(repo, sdk_prefix=sdk, build_dir=build)


@pytest.mark.parametrize("contents", (
    "",
    "TERMIN_SDK_PROFILE:STRING=unknown\n",
    "TERMIN_SDK_PROFILE:STRING=full\nTERMIN_SDK_PROFILE:STRING=core\n",
    "TERMIN_SDK_PROFILE:BOOL=ON\n",
))
def test_configured_identity_is_strict(tmp_path: Path, contents: str) -> None:
    (tmp_path / "CMakeCache.txt").write_text(contents)
    with pytest.raises(SdkContextError):
        load_configured_test_sdk_profile(tmp_path)


@pytest.mark.parametrize("enabled", (True, False))
def test_python_bindings_capability_comes_from_configured_graph(tmp_path: Path, enabled: bool) -> None:
    cache = tmp_path / "CMakeCache.txt"
    value = "ON" if enabled else "OFF"
    cache.write_text(f"TERMIN_BUILD_PYTHON:BOOL={value}\n")
    assert load_configured_test_python_bindings(tmp_path) is enabled
    cache.write_text("TERMIN_BUILD_PYTHON:BOOL=OFF\n")
    assert load_configured_test_python_bindings(tmp_path) is False
    cache.write_text("TERMIN_BUILD_PYTHON:BOOL=ON\n")
    assert load_configured_test_python_bindings(tmp_path) is True


@pytest.mark.parametrize("value,enabled", (
    ("ON", True), ("TRUE", True), ("YES", True), ("Y", True), ("1", True),
    ("OFF", False), ("FALSE", False), ("NO", False), ("N", False), ("0", False),
    ("on", True), ("True", True), ("no", False), ("False", False),
))
def test_python_bindings_capability_accepts_cmake_bool_spellings(tmp_path: Path, value: str, enabled: bool) -> None:
    (tmp_path / "CMakeCache.txt").write_text(f"TERMIN_BUILD_PYTHON:BOOL={value}\n")
    assert load_configured_test_python_bindings(tmp_path) is enabled


@pytest.mark.parametrize("contents", (
    "",
    "TERMIN_BUILD_PYTHON:STRING=ON\n",
    "TERMIN_BUILD_PYTHON:BOOL=unknown\n",
    "TERMIN_BUILD_PYTHON:BOOL=ON\nTERMIN_BUILD_PYTHON:BOOL=OFF\n",
    "TERMIN_BUILD_PYTHON:BOOL\n",
))
def test_python_bindings_capability_requires_strict_cache_metadata(tmp_path: Path, contents: str) -> None:
    (tmp_path / "CMakeCache.txt").write_text(contents)
    with pytest.raises(SdkContextError, match="TERMIN_BUILD_PYTHON"):
        load_configured_test_python_bindings(tmp_path)


def test_python_bindings_capability_requires_configured_cache(tmp_path: Path) -> None:
    with pytest.raises(SdkContextError, match="cannot read configured SDK context"):
        load_configured_test_python_bindings(tmp_path)


def test_existing_explicit_directories_require_metadata(repo: Path) -> None:
    unconfigured = repo / "sdk-core"
    unconfigured.mkdir()
    with pytest.raises(SdkContextError, match="cannot read installed SDK"):
        resolve_test_sdk_context(repo, sdk_prefix=unconfigured)
    with pytest.raises(SdkContextError, match="cannot read configured SDK"):
        resolve_test_sdk_context(repo, build_dir=unconfigured)


def test_installed_metadata_rejects_invalid_schema_and_unknown_product(repo: Path) -> None:
    sdk = repo / "sdk"
    install(repo, sdk, "full")
    manifest = sdk / "sdk-product.json"
    payload = json.loads(manifest.read_text())
    payload["profile_id"] = "unrecognized"
    manifest.write_text(json.dumps(payload))
    with pytest.raises(SdkContextError, match="unsupported test SDK profile"):
        load_installed_test_sdk_profile(sdk)
    manifest.write_text("{bad-json}")
    with pytest.raises(SdkContextError, match="cannot read installed SDK"):
        load_installed_test_sdk_profile(sdk)


def test_cli_preserves_environment_overrides(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    sdk = repo / "custom-sdk"
    install(repo, sdk, "core")
    monkeypatch.setenv("SDK_PREFIX", str(sdk))
    monkeypatch.delenv("TERMIN_SDK", raising=False)
    monkeypatch.delenv("BUILD_DIR", raising=False)
    monkeypatch.setenv("TERMIN_TEST_ENV", str(repo / "test-tools"))
    assert main(["--repo-root", str(repo), "--installed"]) == 0
    assert json.loads(capsys.readouterr().out)["environment-root"] == str(repo / "test-tools")
    assert main(["--repo-root", str(repo), "--profile", "full"]) == 1
    assert "conflicts" in capsys.readouterr().err
