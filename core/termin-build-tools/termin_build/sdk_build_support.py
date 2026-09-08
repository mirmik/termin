"""Process, path, cache, and isolated-build helpers for SDK assembly."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .python_abi import PythonAbiError, PythonAbiIdentity
from .python_toolchain import ensure_python_toolchain
from .sdk_product_inputs import _sdk_packages
from .sdk_python_layout import _is_windows, _python_executable, _python_version_and_paths

SDK_BUILD_REQUIREMENTS_RELATIVE = Path("build-system/python-sdk-build-requirements.txt")


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    return result.returncode


def _powershell_executable() -> str:
    for candidate in ("pwsh", "powershell"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("PowerShell executable not found in PATH")


def _stage_script(repo_root: Path, basename: str) -> list[str]:
    script_name = basename.removeprefix("build-sdk-")
    suffix = ".ps1" if _is_windows() else ".sh"
    script = repo_root / "scripts" / "build" / f"{script_name}{suffix}"
    if _is_windows():
        return [
            _powershell_executable(),
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ]
    if basename == "build-sdk-csharp":
        return ["bash", str(script)]
    return [str(script)]


def _runtime_wheel_dirs(repo_root: Path) -> tuple[Path, Path]:
    root = Path(
        os.environ.get(
            "TERMIN_PYTHON_RUNTIME_BUILD_DIR",
            str(repo_root / "build" / "python-runtime"),
        )
    )
    return root / "external-wheels", root / "termin-wheels"


def _sdk_build_environment_root(repo_root: Path) -> Path:
    return Path(
        os.environ.get(
            "TERMIN_PYTHON_BUILD_ENV",
            str(repo_root / "build" / "python-runtime" / "build-env"),
        )
    )


def _build_environment_python(environment_root: Path) -> Path:
    if _is_windows():
        return environment_root / "Scripts" / "python.exe"
    return environment_root / "bin" / "python"


def _python_pip_error(python_executable: Path) -> str | None:
    try:
        result = subprocess.run(
            [str(python_executable), "-I", "-m", "pip", "--version"],
            check=False,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        return str(error)
    if result.returncode == 0:
        return None
    detail = result.stderr.strip()
    return detail or f"pip probe exited with code {result.returncode}"


def _ensure_sdk_python_build_environment(
    repo_root: Path,
    *,
    base_python: Path | None = None,
    environment_root: Path | None = None,
) -> Path:
    requirements = repo_root / SDK_BUILD_REQUIREMENTS_RELATIVE
    if not requirements.is_file():
        raise RuntimeError(f"SDK Python build requirements are missing: {requirements}")
    environment_root = environment_root or _sdk_build_environment_root(repo_root)
    build_python = _build_environment_python(environment_root)
    stamp = environment_root / "python-sdk-build-requirements.txt"
    selected_base = base_python or Path(_python_executable())
    selected_info = _python_version_and_paths(str(selected_base))
    selected_base_root: Path | None = None
    selected_base_prefix = selected_info.get("base_prefix")
    if isinstance(selected_base_prefix, str) and selected_base_prefix:
        selected_base_root = Path(selected_base_prefix).resolve()
    canonical_base = selected_info.get("base_executable")
    if isinstance(canonical_base, str) and canonical_base:
        canonical_base_path = Path(canonical_base)
        if canonical_base_path.is_file():
            selected_base = canonical_base_path
    expected_abi = PythonAbiIdentity.from_runtime_probe(
        selected_info,
        context="SDK Python build environment base",
    )
    if build_python.is_file():
        actual_base: Path | None = None
        actual_base_root: Path | None = None
        try:
            existing_info = _python_version_and_paths(str(build_python))
            actual_abi = PythonAbiIdentity.from_runtime_probe(
                existing_info,
                context="existing SDK Python build environment",
            )
            base_value = existing_info.get("base_executable")
            if isinstance(base_value, str) and base_value:
                actual_base = Path(base_value).resolve()
            base_prefix_value = existing_info.get("base_prefix")
            if isinstance(base_prefix_value, str) and base_prefix_value:
                actual_base_root = Path(base_prefix_value).resolve()
        except (PythonAbiError, OSError, RuntimeError):
            actual_abi = None
        selected_base = selected_base.resolve()
        if selected_base_root is not None and actual_base_root is not None:
            base_mismatch = actual_base_root != selected_base_root
        else:
            base_mismatch = actual_base is not None and actual_base != selected_base
        if actual_abi != expected_abi or base_mismatch:
            rendered = actual_abi.canonical_json() if actual_abi is not None else "unreadable"
            if base_mismatch:
                rendered += f", base={actual_base}"
            print(
                "Recreating SDK Python build environment for ABI "
                f"{expected_abi.canonical_json()}, base={selected_base} "
                f"(existing: {rendered})"
            )
            shutil.rmtree(environment_root)
    if not build_python.is_file():
        result = _run(
            [str(selected_base), "-m", "venv", str(environment_root)],
            cwd=repo_root,
            env=os.environ.copy(),
        )
        if result != 0:
            raise RuntimeError(f"failed to create SDK Python build environment: {environment_root}")
    pip_error = _python_pip_error(build_python)
    if pip_error is not None:
        print(f"Bootstrapping missing pip in SDK Python build environment ({pip_error})")
        result = _run(
            [
                str(build_python),
                "-I",
                "-m",
                "ensurepip",
                "--upgrade",
                "--default-pip",
            ],
            cwd=repo_root,
            env=os.environ.copy(),
        )
        if result != 0:
            raise RuntimeError("failed to bootstrap pip in SDK Python build environment")
        pip_error = _python_pip_error(build_python)
        if pip_error is not None:
            raise RuntimeError(f"pip is still unavailable in SDK Python build environment after ensurepip: {pip_error}")
    current = stamp.is_file() and stamp.read_bytes() == requirements.read_bytes()
    if not current:
        result = _run(
            [
                str(build_python),
                "-I",
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--no-deps",
                "-r",
                str(requirements),
            ],
            cwd=repo_root,
            env=os.environ.copy(),
        )
        if result != 0:
            raise RuntimeError("failed to install pinned SDK Python build tools")
        shutil.copy2(requirements, stamp)
    print(f"Using isolated SDK Python build environment: {environment_root}")
    return build_python


def prepare_pinned_python_build_environment(
    repo_root: Path,
    *,
    variant: str | None = None,
    environment_root: Path | None = None,
) -> Path:
    toolchain = ensure_python_toolchain(repo_root, variant=variant)
    return _ensure_sdk_python_build_environment(
        repo_root,
        base_python=toolchain.python_executable,
        environment_root=environment_root,
    )


def prepare_python_build_environment(
    repo_root: Path,
    *,
    base_python: Path,
    variant: str,
    environment_root: Path,
) -> Path:
    """Prepare a build frontend from an explicitly selected, ABI-checked Python.

    The normal SDK/product path uses the repository's pinned CPython toolchain.
    Release containers are a separate trusted toolchain boundary: official
    manylinux images publish their interpreters at immutable, ABI-named paths.
    They may opt in here, but an ambient or merely version-compatible Python is
    never accepted.
    """
    info = _python_version_and_paths(str(base_python))
    identity = PythonAbiIdentity.from_runtime_probe(
        info,
        context=f"explicit {variant} Python build environment base",
    )
    if identity.wheel_abi_tag != variant:
        raise PythonAbiError(
            f"explicit Python for {variant} has ABI "
            f"{identity.wheel_abi_tag}: {base_python}"
        )
    return _ensure_sdk_python_build_environment(
        repo_root,
        base_python=base_python,
        environment_root=environment_root,
    )


def _sdk_valid(path: Path) -> bool:
    return (path / "lib").is_dir()


def _resolve_sdk_prefix(repo_root: Path, sdk_prefix: Path) -> Path:
    # An explicit orchestration output wins over the SDK selected by the
    # launcher which happens to host the build frontend. Domain builds run the
    # frontend from Core but publish and resolve artifacts in their own prefix.
    if _sdk_valid(sdk_prefix):
        return sdk_prefix
    env_sdk = os.environ.get("TERMIN_SDK")
    if env_sdk:
        resolved = Path(env_sdk)
        if not _sdk_valid(resolved):
            raise RuntimeError(f"TERMIN_SDK={resolved} is set but does not contain lib/")
        return resolved
    if _is_windows():
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            local_sdk = Path(local_app_data) / "termin-sdk"
            if _sdk_valid(local_sdk):
                return local_sdk
    else:
        opt_sdk = Path("/opt/termin")
        if _sdk_valid(opt_sdk):
            return opt_sdk
    raise RuntimeError(f"termin SDK not found. Tried TERMIN_SDK, {sdk_prefix}")


def _resolve_bindings_dir(repo_root: Path, build_dir: Path) -> Path:
    env_bindings = os.environ.get("TERMIN_BINDINGS_DIR")
    candidates = []
    if env_bindings:
        candidates.append(Path(env_bindings))
    candidates.extend(
        (
            build_dir / "bin",
            repo_root / "build" / "Release" / "bin",
            repo_root / "build" / "Debug" / "bin",
        )
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError("Termin Python bindings directory not found. Set TERMIN_BINDINGS_DIR or build bindings first.")


def _clear_python_package_build_caches(repo_root: Path) -> None:
    for package in _sdk_packages(repo_root):
        package_dir = repo_root / package.path
        build_dir = package_dir / "build"
        if build_dir.is_dir():
            for child in build_dir.iterdir():
                if child.is_dir() and (
                    child.name == "lib" or child.name.startswith("lib.") or child.name.startswith("bdist.")
                ):
                    shutil.rmtree(child, ignore_errors=True)
        for egg_info in package_dir.rglob("*.egg-info"):
            if egg_info.is_dir():
                shutil.rmtree(egg_info, ignore_errors=True)
