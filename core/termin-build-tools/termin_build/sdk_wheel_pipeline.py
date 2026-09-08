"""SDK wheel build, validation, composition, and publication pipeline."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from .artifact_manifest import ArtifactManifest, ArtifactManifestError, SDK_MANIFEST_NAME
from .local_wheel_artifacts import (
    LocalWheelArtifactError,
    build_local_wheel_artifact_set,
    compose_local_wheel_artifact_set,
    publish_local_wheel_artifact_set,
)
from .python_abi import PythonAbiIdentity
from .sdk_build_support import (
    _clear_python_package_build_caches,
    _ensure_sdk_python_build_environment,
    _resolve_bindings_dir,
    _resolve_sdk_prefix,
    _run,
    _runtime_wheel_dirs,
)
from .sdk_product_inputs import (
    _active_sdk_profile,
    _composed_sdk_wheel_count,
    _installed_core_input,
    _source_built_sdk_packages,
)
from .sdk_runtime_metadata import _load_runtime_lock
from .sdk_python_layout import _python_version_and_paths
from .wheelhouse import (
    WheelhouseError,
    supported_wheel_tags,
    validate_locked_wheelhouse,
)


def _prepare_external_runtime_wheels(
    repo_root: Path,
    wheel_dir: Path,
    build_python: Path,
) -> int:
    profile = _active_sdk_profile(repo_root)
    lock_path = repo_root / profile.runtime_lock
    try:
        runtime_lock = _load_runtime_lock(repo_root, profile.runtime_lock)
        python_abi = PythonAbiIdentity.from_runtime_probe(
            _python_version_and_paths(str(build_python)),
            context="SDK Python build environment",
        )
        target_tags = supported_wheel_tags(build_python)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    wheel_dir.mkdir(parents=True, exist_ok=True)
    if os.environ.get("TERMIN_PYTHON_RUNTIME_OFFLINE") == "1":
        print(f"Using offline SDK runtime wheelhouse: {wheel_dir}")
        try:
            validate_locked_wheelhouse(
                wheel_dir,
                runtime_lock,
                python_abi=python_abi,
                supported_tags=target_tags,
            )
        except WheelhouseError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        return 0
    print(f"Preparing pinned SDK runtime wheels: {wheel_dir}")
    wheel_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="external-wheels.",
        dir=wheel_dir.parent,
    ) as temporary_root:
        prepared = Path(temporary_root) / "wheels"
        prepared.mkdir()
        result = _run(
            [
                str(build_python),
                "-m",
                "pip",
                "wheel",
                "--no-build-isolation",
                "--no-deps",
                "--wheel-dir",
                str(prepared),
                "-r",
                str(lock_path),
            ],
            cwd=repo_root,
            env=os.environ.copy(),
        )
        if result != 0:
            return result
        try:
            validate_locked_wheelhouse(
                prepared,
                runtime_lock,
                python_abi=python_abi,
                supported_tags=target_tags,
            )
        except WheelhouseError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        shutil.rmtree(wheel_dir)
        prepared.replace(wheel_dir)
    print(f"Validated {len(runtime_lock)} exact runtime wheels for {python_abi.wheel_abi_tag}")
    return 0


def prepare_locked_runtime_wheels(
    repo_root: Path,
    build_python: Path,
    *,
    wheel_dir: Path,
) -> Path:
    """Prepare an ABI-specific wheelhouse from the exact runtime lock."""
    result = _prepare_external_runtime_wheels(repo_root, wheel_dir, build_python)
    if result != 0:
        raise RuntimeError(f"failed to prepare locked runtime wheels for {build_python}")
    return wheel_dir


def _parse_wheelhouse_args(
    sdk_prefix: Path,
    build_dir: Path,
    stage_args: list[str],
) -> tuple[Path, Path]:
    wheel_dir_env = os.environ.get("WHEEL_DIR")
    wheel_dir = Path(wheel_dir_env) if wheel_dir_env else sdk_prefix / "wheels"
    effective_build_dir = build_dir

    index = 0
    while index < len(stage_args):
        arg = stage_args[index]
        if arg in ("--debug", "-d"):
            if "BUILD_DIR" not in os.environ:
                effective_build_dir = build_dir.parent / "Debug"
        elif arg == "--wheel-dir":
            index += 1
            if index >= len(stage_args):
                raise RuntimeError("--wheel-dir requires a directory")
            wheel_dir = Path(stage_args[index])
        elif arg.startswith("--wheel-dir="):
            wheel_dir = Path(arg.split("=", 1)[1])
        index += 1

    return wheel_dir, effective_build_dir


def build_wheelhouse(
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
    stage_args: list[str],
    *,
    python_executable: Path | None = None,
) -> int:
    try:
        wheel_dir, effective_build_dir = _parse_wheelhouse_args(
            sdk_prefix,
            build_dir,
            stage_args,
        )
        termin_sdk = _resolve_sdk_prefix(repo_root, sdk_prefix)
        bindings_dir = _resolve_bindings_dir(repo_root, effective_build_dir)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"Using TERMIN_SDK={termin_sdk}")
    print(f"Using TERMIN_BINDINGS_DIR={bindings_dir}")
    print(f"Wheelhouse: {wheel_dir}")
    try:
        build_python = _ensure_sdk_python_build_environment(
            repo_root,
            base_python=python_executable,
        )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    result = _build_local_package_wheels(
        repo_root=repo_root,
        termin_sdk=termin_sdk,
        bindings_dir=bindings_dir,
        wheel_dir=wheel_dir,
        build_python=build_python,
    )
    if result != 0:
        return result
    result = _verify_library_wheel_subset_install(repo_root, wheel_dir, build_python)
    if result != 0:
        return result

    print("")
    print("========================================")
    print(f"  SDK wheelhouse ready: {wheel_dir}")
    print("========================================")
    return 0


def _verify_library_wheel_subset_install(
    repo_root: Path,
    wheel_dir: Path,
    build_python: Path,
) -> int:
    wheel_patterns = _active_sdk_profile(repo_root).wheel_subset
    wheels = []
    for pattern in wheel_patterns:
        matching = sorted(wheel_dir.glob(pattern))
        if len(matching) != 1:
            print(
                f"ERROR: representative library subset expected one {pattern}, found {len(matching)}",
                file=sys.stderr,
            )
            return 1
        wheels.append(matching[0])
    with tempfile.TemporaryDirectory(prefix="termin-wheel-subset-") as temp_dir:
        result = _run(
            [
                str(build_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--no-compile",
                "--target",
                temp_dir,
                *(str(wheel) for wheel in wheels),
            ],
            cwd=wheel_dir,
            env=os.environ.copy(),
        )
        if result != 0:
            print("ERROR: representative library wheel subset install failed", file=sys.stderr)
            return result
    print("Representative library wheel subset install OK")
    return 0


def _build_local_package_wheels(
    repo_root: Path,
    termin_sdk: Path,
    bindings_dir: Path,
    wheel_dir: Path,
    build_python: Path,
) -> int:
    python_abi = PythonAbiIdentity.from_runtime_probe(
        _python_version_and_paths(str(build_python)),
        context="SDK wheel build Python",
    )
    packages = _source_built_sdk_packages(
        repo_root,
        expected_python_abi=python_abi,
    )
    result = build_local_wheel_artifact_set(
        repo_root=repo_root,
        sdk_prefix=termin_sdk,
        bindings_dir=bindings_dir,
        wheel_dir=wheel_dir.resolve(),
        build_python=build_python,
        packages=packages,
        run=_run,
        clear_build_caches=_clear_python_package_build_caches,
    )
    if result != 0:
        return result
    core_input = _installed_core_input(
        repo_root,
        expected_python_abi=python_abi,
    )
    if core_input is None or _active_sdk_profile(repo_root).artifact_kind == "layer":
        return 0
    try:
        compose_local_wheel_artifact_set(
            wheel_dir,
            ((core_input.root / "wheels", core_input.root, len(core_input.distributions)),),
            wheel_dir,
            sdk_prefix=termin_sdk,
            expected_primary_wheel_count=len(packages),
        )
    except (LocalWheelArtifactError, OSError) as error:
        print(
            f"ERROR: cannot compose Core and domain wheel artifacts: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


def _publish_runtime_wheelhouse(repo_root: Path, sdk_prefix: Path) -> int:
    _, local_wheels = _runtime_wheel_dirs(repo_root)
    wheel_dir = sdk_prefix / "wheels"
    try:
        artifact_manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        publish_local_wheel_artifact_set(
            local_wheels,
            wheel_dir,
            sdk_prefix=sdk_prefix,
            expected_wheel_count=_composed_sdk_wheel_count(
                repo_root,
                expected_python_abi=artifact_manifest.python_abi,
            ),
        )
    except (ArtifactManifestError, LocalWheelArtifactError, OSError, RuntimeError) as error:
        print(f"ERROR: failed to publish SDK wheelhouse: {error}", file=sys.stderr)
        return 1
    print(f"Published canonical SDK wheelhouse: {wheel_dir}")
    return 0
