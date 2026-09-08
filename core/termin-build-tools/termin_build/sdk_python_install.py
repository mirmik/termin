"""Bundled and layer Python runtime installation for SDK products."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .application_payload import install_application_payloads
from .local_wheel_artifacts import LocalWheelArtifactError, validate_local_wheel_artifact_set
from .python_abi import PythonAbiError, PythonAbiIdentity
from .sdk_bundled_python import (
    _copy_python_development_headers,
    _ensure_linux_python_shared_library,
    _remove_incompatible_bundled_python_runtimes,
    _remove_linux_python_config_artifacts,
    ensure_bundled_python_cli,
    ensure_bundled_python_runtime,
)
from .sdk_build_support import (
    _ensure_sdk_python_build_environment,
    _resolve_bindings_dir,
    _resolve_sdk_prefix,
    _run,
    _runtime_wheel_dirs,
)
from .sdk_native_artifacts import find_native_artifact as _find_native_artifact
from .sdk_product_inputs import (
    _active_sdk_profile,
    _composed_sdk_wheel_count,
    _installed_core_input,
    _sdk_application_payloads,
    _sdk_packages,
)
from .sdk_python_layout import (
    _find_bundled_python_dir,
    _is_windows,
    _python_executable,
    _python_version_and_paths,
)
from .sdk_runtime_metadata import _load_runtime_lock, write_python_runtime_manifest
from .sdk_wheel_pipeline import (
    _build_local_package_wheels,
    _prepare_external_runtime_wheels,
)
from .wheelhouse import supported_wheel_tags, validate_locked_wheelhouse

_SUPPORTED_SDK_BUILD_PYTHON_ABIS = frozenset({"cp314", "cp314t"})


def install_python_packages(
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
    *,
    python_executable: Path | None = None,
) -> int:
    py_exec = str(python_executable) if python_executable else _python_executable()
    info = _python_version_and_paths(py_exec)
    target_python_abi = PythonAbiIdentity.from_runtime_probe(
        info,
        context="SDK target Python",
    )
    profile = _active_sdk_profile(repo_root)
    if profile.artifact_kind == "layer":
        version = str(info["version"])
        abi_suffix = "t" if bool(info.get("free_threaded", False)) else ""
        bundled_site_packages = sdk_prefix / "lib" / f"python{version}{abi_suffix}" / "site-packages"
        print(f"Layer Python site-packages: {bundled_site_packages}")
    else:
        bundled_site_packages = None

    if bundled_site_packages is not None:
        return _install_python_layer_packages(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
            build_python=Path(py_exec),
            site_packages=bundled_site_packages,
            target_python_abi=target_python_abi,
        )

    _remove_incompatible_bundled_python_runtimes(sdk_prefix, info)
    try:
        bundled_py_dir = _find_bundled_python_dir(
            sdk_prefix,
            expected_version=str(info["version"]),
            expected_free_threaded=bool(info.get("free_threaded", False)),
        )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if bundled_py_dir is None:
        print("Bundled Python stdlib not found; creating it from the selected target Python.")
    else:
        print("Synchronizing bundled Python stdlib from the selected target Python.")
    try:
        bundled_py_dir = ensure_bundled_python_runtime(
            sdk_prefix,
            python_executable=Path(py_exec),
        )
    except RuntimeError as error:
        print(f"ERROR: failed to synchronize bundled Python stdlib: {error}", file=sys.stderr)
        return 1
    if bundled_py_dir is None:
        print(
            f"ERROR: failed to create bundled Python stdlib under {sdk_prefix / 'lib'}/python3.*",
            file=sys.stderr,
        )
        return 1
    _remove_linux_python_config_artifacts(bundled_py_dir)
    _ensure_linux_python_shared_library(sdk_prefix, info)
    _copy_python_development_headers(sdk_prefix, info)
    ensure_bundled_python_cli(
        sdk_prefix,
        python_executable=Path(py_exec),
    )

    bundled_site_packages = bundled_py_dir / "site-packages"
    print(f"Bundled Python stdlib:        {bundled_py_dir}")
    print(f"Bundled Python site-packages: {bundled_site_packages}")

    try:
        termin_sdk = _resolve_sdk_prefix(repo_root, sdk_prefix)
        bindings_dir = _resolve_bindings_dir(repo_root, build_dir)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        build_python = _ensure_sdk_python_build_environment(
            repo_root,
            base_python=Path(py_exec),
        )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    external_wheels, local_wheels = _runtime_wheel_dirs(repo_root)
    result = _prepare_external_runtime_wheels(repo_root, external_wheels, build_python)
    if result != 0:
        return result
    result = _build_local_package_wheels(
        repo_root=repo_root,
        termin_sdk=termin_sdk,
        bindings_dir=bindings_dir,
        wheel_dir=local_wheels,
        build_python=build_python,
    )
    if result != 0:
        return result
    result = _install_prepared_runtime_wheels(
        repo_root=repo_root,
        site_packages=bundled_site_packages,
        external_wheels=external_wheels,
        local_wheels=local_wheels,
        build_python=build_python,
        sdk_prefix=sdk_prefix,
    )
    if result != 0:
        return result
    try:
        install_application_payloads(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            site_packages=bundled_site_packages,
            resolve_native_artifact=lambda target: _find_native_artifact(
                build_dir,
                target,
                python_abi=target_python_abi,
            ),
            runtime_python_abi=target_python_abi,
            payloads=_sdk_application_payloads(repo_root),
        )
    except RuntimeError as error:
        print(f"ERROR: failed to install application Python payload: {error}", file=sys.stderr)
        return 1
    try:
        profile = _active_sdk_profile(repo_root)
        core_input = _installed_core_input(
            repo_root,
            expected_python_abi=target_python_abi,
        )
        write_python_runtime_manifest(
            repo_root,
            sdk_prefix,
            bundled_site_packages,
            runtime_python_abi=target_python_abi,
            packages=_sdk_packages(repo_root),
            additional_local_distributions=(core_input.distributions if core_input is not None else ()),
            runtime_lock_relative=profile.runtime_lock,
        )
    except RuntimeError as error:
        print(f"ERROR: failed to write SDK Python runtime manifest: {error}", file=sys.stderr)
        return 1
    return 0


def _install_python_layer_packages(
    *,
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
    build_python: Path,
    site_packages: Path,
    target_python_abi: PythonAbiIdentity,
) -> int:
    try:
        termin_sdk = _resolve_sdk_prefix(repo_root, sdk_prefix)
        bindings_dir = _resolve_bindings_dir(repo_root, build_dir)
        isolated_build_python = _ensure_sdk_python_build_environment(
            repo_root,
            base_python=build_python,
        )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    external_wheels, local_wheels = _runtime_wheel_dirs(repo_root)
    result = _prepare_external_runtime_wheels(
        repo_root,
        external_wheels,
        isolated_build_python,
    )
    if result != 0:
        return result
    result = _build_local_package_wheels(
        repo_root=repo_root,
        termin_sdk=termin_sdk,
        bindings_dir=bindings_dir,
        wheel_dir=local_wheels,
        build_python=isolated_build_python,
    )
    if result != 0:
        return result

    try:
        expected_count = _composed_sdk_wheel_count(
            repo_root,
            expected_python_abi=target_python_abi,
        )
        validate_local_wheel_artifact_set(
            local_wheels,
            sdk_prefix=sdk_prefix,
            expected_wheel_count=expected_count,
        )
        if site_packages.exists():
            shutil.rmtree(site_packages)
        site_packages.mkdir(parents=True)
    except (LocalWheelArtifactError, OSError, RuntimeError) as error:
        print(f"ERROR: cannot install SDK Python layer: {error}", file=sys.stderr)
        return 1

    wheels = sorted(local_wheels.glob("*.whl"))
    result = _run(
        [
            str(isolated_build_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--no-cache-dir",
            "--find-links",
            str(external_wheels),
            "--target",
            str(site_packages),
            "-r",
            str(repo_root / _active_sdk_profile(repo_root).runtime_lock),
            *(str(wheel) for wheel in wheels),
        ],
        cwd=repo_root,
        env=os.environ.copy(),
    )
    if result != 0:
        return result

    try:
        install_application_payloads(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            site_packages=site_packages,
            resolve_native_artifact=lambda target: _find_native_artifact(
                build_dir,
                target,
                python_abi=target_python_abi,
            ),
            runtime_python_abi=target_python_abi,
            payloads=_sdk_application_payloads(repo_root),
        )
        write_python_runtime_manifest(
            repo_root,
            sdk_prefix,
            site_packages,
            runtime_python_abi=target_python_abi,
            packages=_sdk_packages(repo_root),
            additional_local_distributions=(),
            runtime_lock_relative=_active_sdk_profile(repo_root).runtime_lock,
            allow_empty_runtime_lock=True,
        )
    except RuntimeError as error:
        print(f"ERROR: failed to write SDK Python layer manifest: {error}", file=sys.stderr)
        return 1
    return 0


def prepare_build_python_runtime(sdk_prefix: Path) -> int:
    py_exec = _python_executable()
    try:
        info = _python_version_and_paths(py_exec)
        python_abi = PythonAbiIdentity.from_runtime_probe(
            info,
            context="SDK build Python",
        )
        if python_abi.version != "3.14" or python_abi.wheel_abi_tag not in _SUPPORTED_SDK_BUILD_PYTHON_ABIS:
            supported = ", ".join(sorted(_SUPPORTED_SDK_BUILD_PYTHON_ABIS))
            raise PythonAbiError(
                "SDK build Python must use Python 3.14 with one of the "
                f"supported ABIs ({supported}); got Python {python_abi.version} "
                f"with ABI {python_abi.wheel_abi_tag}"
            )
    except (OSError, RuntimeError) as error:
        print(f"ERROR: failed to validate SDK build Python: {error}", file=sys.stderr)
        return 1

    if _is_windows():
        try:
            bundled_py_dir = ensure_bundled_python_runtime(
                sdk_prefix,
                python_executable=Path(py_exec),
                runtime_info=info,
            )
        except (OSError, RuntimeError) as error:
            print(
                f"ERROR: failed to prepare Windows Python runtime: {error}",
                file=sys.stderr,
            )
            return 1
        print(f"Prepared bundled Windows Python runtime for SDK build consumers: {bundled_py_dir}")
        return 0

    _remove_incompatible_bundled_python_runtimes(sdk_prefix, info)
    try:
        bundled_py_dir = _find_bundled_python_dir(
            sdk_prefix,
            expected_version=str(info["version"]),
            expected_free_threaded=bool(info.get("free_threaded", False)),
        )
        if (
            bundled_py_dir is None
            or not (bundled_py_dir / "os.py").is_file()
            or not (bundled_py_dir / "ensurepip").is_dir()
        ):
            bundled_py_dir = ensure_bundled_python_runtime(
                sdk_prefix,
                python_executable=Path(py_exec),
                runtime_info=info,
            )
        else:
            _remove_linux_python_config_artifacts(bundled_py_dir)
            _ensure_linux_python_shared_library(sdk_prefix, info)
            _copy_python_development_headers(sdk_prefix, info)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Prepared bundled Python runtime for native build: {bundled_py_dir}")
    return 0


def _install_prepared_runtime_wheels(
    repo_root: Path,
    site_packages: Path,
    external_wheels: Path,
    local_wheels: Path,
    build_python: Path,
    sdk_prefix: Path,
) -> int:
    try:
        profile = _active_sdk_profile(repo_root)
        runtime_lock = _load_runtime_lock(repo_root, profile.runtime_lock)
        python_abi = PythonAbiIdentity.from_runtime_probe(
            _python_version_and_paths(str(build_python)),
            context="SDK Python build environment",
        )
        validate_locked_wheelhouse(
            external_wheels,
            runtime_lock,
            python_abi=python_abi,
            supported_tags=supported_wheel_tags(build_python),
        )
        expected_local_count = _composed_sdk_wheel_count(
            repo_root,
            expected_python_abi=python_abi,
        )
        validate_local_wheel_artifact_set(
            local_wheels,
            sdk_prefix=sdk_prefix,
            expected_wheel_count=expected_local_count,
        )
    except (LocalWheelArtifactError, RuntimeError) as error:
        print(f"ERROR: cannot install SDK Python runtime: {error}", file=sys.stderr)
        return 1
    wheels = sorted(local_wheels.glob("*.whl"))
    try:
        if site_packages.exists():
            shutil.rmtree(site_packages)
        site_packages.mkdir(parents=True)
    except OSError as error:
        print(
            f"ERROR: cannot replace SDK Python site-packages {site_packages}: {error}",
            file=sys.stderr,
        )
        if _is_windows():
            print(
                "Close pytest and Python processes that may hold SDK .pyd/.dll files, then retry.",
                file=sys.stderr,
            )
        return 1

    lock_path = repo_root / profile.runtime_lock
    print("Installing SDK Python site-packages offline from prepared wheels")
    return _run(
        [
            str(build_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--no-cache-dir",
            "--find-links",
            str(external_wheels),
            "--target",
            str(site_packages),
            "-r",
            str(lock_path),
            *(str(wheel) for wheel in wheels),
        ],
        cwd=repo_root,
        env=os.environ.copy(),
    )
