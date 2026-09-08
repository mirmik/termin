"""SDK profile-selected repository and installed-product inputs."""

from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path
from typing import Sequence

from .application_payload import load_application_payloads
from .package_manifest import PackageEntry, load_manifest
from .python_abi import PythonAbiIdentity
from .sdk_composition import InstalledSdkInput, load_installed_sdk_input
from .sdk_profiles import (
    SdkProfile,
    load_sdk_profiles,
    select_application_payloads,
    select_python_packages,
)

CORE_SDK_ENV = "TERMIN_CORE_SDK"
CORE_BUILD_ID_ENV = "TERMIN_CORE_BUILD_ID"

_SDK_PROFILE_CONTEXT: ContextVar[str | None] = ContextVar(
    "termin_sdk_profile",
    default=None,
)


def _active_sdk_profile_name(repo_root: Path) -> str:
    contextual = _SDK_PROFILE_CONTEXT.get()
    if contextual is not None:
        return contextual
    profiles = load_sdk_profiles(repo_root)
    return os.environ.get("TERMIN_SDK_PROFILE", profiles.default_profile)


def _active_sdk_profile(repo_root: Path) -> SdkProfile:
    profiles = load_sdk_profiles(repo_root)
    return profiles.profile(_active_sdk_profile_name(repo_root))


def _sdk_packages(repo_root: Path) -> list[PackageEntry]:
    profile = _active_sdk_profile(repo_root)
    return select_python_packages(
        profile,
        load_manifest(repo_root),
        repo_root=repo_root,
    )


def _installed_core_input(
    repo_root: Path,
    *,
    expected_python_abi: PythonAbiIdentity,
    packages: Sequence[PackageEntry] | None = None,
) -> InstalledSdkInput | None:
    selected_packages = packages if packages is not None else _sdk_packages(repo_root)
    if not any(package.source == "installed-core" for package in selected_packages):
        return None

    root = os.environ.get(CORE_SDK_ENV)
    expected_build_id = os.environ.get(CORE_BUILD_ID_ENV) or None
    if root is None:
        if expected_build_id is not None:
            raise RuntimeError(f"{CORE_BUILD_ID_ENV} cannot be used without {CORE_SDK_ENV}")
        return None
    return load_installed_sdk_input(
        Path(root),
        expected_product="core",
        expected_build_id=expected_build_id,
        expected_python_abi=expected_python_abi,
    )


def _source_built_sdk_packages(repo_root: Path, *, expected_python_abi: PythonAbiIdentity) -> list[PackageEntry]:
    packages = _sdk_packages(repo_root)
    core_input = _installed_core_input(
        repo_root,
        expected_python_abi=expected_python_abi,
        packages=packages,
    )
    if core_input is None:
        if not any(package.source == "installed-core" for package in packages):
            return packages
        raise RuntimeError(f"{CORE_SDK_ENV} is required: installed Core packages are external inputs")
    core_distributions = {distribution.lower().replace("_", "-") for distribution in core_input.distributions}
    required_core_distributions = {
        package.distribution.lower().replace("_", "-") for package in packages if package.source == "installed-core"
    }
    missing = sorted(required_core_distributions - core_distributions)
    if missing:
        raise RuntimeError("installed Core SDK is missing required Python distributions: " + ", ".join(missing))
    return [package for package in packages if package.source == "repository"]


def _composed_sdk_wheel_count(repo_root: Path, *, expected_python_abi: PythonAbiIdentity) -> int:
    profile = _active_sdk_profile(repo_root)
    core_input = _installed_core_input(
        repo_root,
        expected_python_abi=expected_python_abi,
    )
    repository_count = len(
        _source_built_sdk_packages(
            repo_root,
            expected_python_abi=expected_python_abi,
        )
    )
    if profile.artifact_kind == "layer":
        return repository_count
    return repository_count + (len(core_input.distributions) if core_input is not None else 0)


def _sdk_application_payloads(repo_root: Path):
    profile = _active_sdk_profile(repo_root)
    return select_application_payloads(profile, load_application_payloads(repo_root))
