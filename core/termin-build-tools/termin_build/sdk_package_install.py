"""Editable and target pip package installation with lock diagnostics."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

from .package_manifest import PackageEntry
from .sdk_build_support import (
    _clear_python_package_build_caches,
    _resolve_sdk_prefix,
    _run,
)
from .sdk_product_inputs import _sdk_packages
from .sdk_python_layout import _is_windows, _python_executable
from .sdk_runtime_metadata import _clear_target_python_package_metadata

LEGACY_SOURCE_NATIVE_ARTIFACTS = {
    "editor/termin-app": ("termin/_native",),
}


def _python_bin() -> str:
    env_python = os.environ.get("PYTHON_BIN")
    if env_python:
        return env_python
    return _python_executable()


def _clear_legacy_source_native_artifacts(repo_root: Path) -> None:
    removed = []
    suffixes = ("so", "pyd", "dylib")
    for package_path, module_stems in LEGACY_SOURCE_NATIVE_ARTIFACTS.items():
        package_dir = repo_root / package_path
        for module_stem in module_stems:
            module_path = package_dir / module_stem
            patterns = [f"{module_path.name}.{suffix}" for suffix in suffixes] + [
                f"{module_path.name}.*.{suffix}" for suffix in suffixes
            ]
            for pattern in patterns:
                for artifact in module_path.parent.glob(pattern):
                    if not artifact.is_file():
                        continue
                    artifact.unlink()
                    removed.append(artifact.relative_to(repo_root).as_posix())
    if removed:
        print("Removed legacy source native artifacts: " + ", ".join(sorted(removed)))


def _add_build_tools_pythonpath(env: dict[str, str], repo_root: Path) -> None:
    build_tools = str(repo_root / "core" / "termin-build-tools")
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = build_tools + (os.pathsep + current if current else "")


def _bindings_dir_if_available(repo_root: Path, build_dir: Path) -> Path | None:
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
    return None


def _pip_temp_env(repo_root: Path, env: dict[str, str]) -> Path | None:
    if not _is_windows():
        return None
    pip_temp_root = repo_root / "build" / "pip-temp"
    pip_temp_dir = pip_temp_root / uuid.uuid4().hex
    pip_temp_dir.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(pip_temp_dir)
    env["TMP"] = str(pip_temp_dir)
    return pip_temp_dir


def _run_windows_tasklist(args: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["tasklist", *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def _windows_module_users(module_name: str) -> list[str]:
    return _run_windows_tasklist(["/m", module_name])


def _windows_python_processes() -> list[str]:
    lines: list[str] = []
    for image_name in ("python.exe", "pythonw.exe", "py.exe", "pytest.exe"):
        process_lines = _run_windows_tasklist(["/fi", f"imagename eq {image_name}"])
        if process_lines:
            lines.extend(process_lines)
    return lines


def _native_artifacts_for_lock_diagnostics(repo_root: Path, package: PackageEntry) -> list[Path]:
    package_root = repo_root / package.path
    if not package_root.is_dir():
        return []
    artifacts: list[Path] = []
    for pattern in ("*.pyd", "*.dll"):
        artifacts.extend(path for path in package_root.rglob(pattern) if path.is_file())
    return sorted(artifacts)[:50]


def _print_install_failure_summary(
    package: PackageEntry,
    package_index: int,
    package_count: int,
    repo_root: Path,
    editable: bool,
) -> None:
    print(
        f"ERROR: pip install failed for {package.distribution} "
        f"({package_index}/{package_count}); Python package sync stopped.",
        file=sys.stderr,
    )
    print(
        "ERROR: packages after this point were not installed; rerun the install after fixing the cause.",
        file=sys.stderr,
    )

    if not editable or not _is_windows():
        return

    artifacts = _native_artifacts_for_lock_diagnostics(repo_root, package)
    print(
        "Windows editable install note: native .pyd/.dll files cannot be replaced while "
        "another process has them loaded.",
        file=sys.stderr,
    )
    if artifacts:
        print("Checked native artifacts for loaded-module owners:", file=sys.stderr)
        found_owner = False
        for artifact in artifacts:
            print(f"  - {artifact}", file=sys.stderr)
            for line in _windows_module_users(artifact.name):
                found_owner = True
                print(f"      {line}", file=sys.stderr)
        if not found_owner:
            print("  No loaded-module owner was reported by tasklist /m.", file=sys.stderr)
    else:
        print(f"No native artifacts found under {repo_root / package.path} yet.", file=sys.stderr)

    python_processes = _windows_python_processes()
    if python_processes:
        print("Running Python/Termin processes that may hold native modules:", file=sys.stderr)
        for line in python_processes:
            print(f"  {line}", file=sys.stderr)

    print(
        "Close pytest, Python REPLs, and stale environment processes, "
        "then rerun install-pip-packages.ps1 --editable --force.",
        file=sys.stderr,
    )


def install_pip_packages(
    repo_root: Path,
    sdk_prefix: Path,
    build_dir: Path,
    target_dir: Path | None,
    editable: bool,
    force: bool,
) -> int:
    if target_dir is not None and editable:
        print("ERROR: --editable is incompatible with --target", file=sys.stderr)
        return 1

    try:
        termin_sdk = _resolve_sdk_prefix(repo_root, sdk_prefix)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    bindings_dir = _bindings_dir_if_available(repo_root, build_dir)
    env = os.environ.copy()
    env["TERMIN_SDK"] = str(termin_sdk)
    if bindings_dir is not None:
        env["TERMIN_BINDINGS_DIR"] = str(bindings_dir)
    if "TERMIN_PIP_BUNDLE_LIBS" not in env:
        env["TERMIN_PIP_BUNDLE_LIBS"] = "0" if target_dir is not None or editable else "1"
    if "TERMIN_PIP_COPY_TO_SOURCE" not in env:
        env["TERMIN_PIP_COPY_TO_SOURCE"] = "1" if editable else "0"
    _add_build_tools_pythonpath(env, repo_root)

    pip_temp_dir = _pip_temp_env(repo_root, env)
    pip_cmd = [_python_bin(), "-m", "pip"]

    print(f"Using TERMIN_SDK={termin_sdk}")
    if bindings_dir is not None:
        print(f"Using TERMIN_BINDINGS_DIR={bindings_dir}")
    print(f"TERMIN_PIP_BUNDLE_LIBS={env['TERMIN_PIP_BUNDLE_LIBS']}")
    print(f"TERMIN_PIP_COPY_TO_SOURCE={env['TERMIN_PIP_COPY_TO_SOURCE']}")
    print("Using pip: " + " ".join(pip_cmd))
    if pip_temp_dir is not None:
        print(f"Using pip temp: {pip_temp_dir}")

    if force:
        print("--force: clearing per-package pip build caches before install")
        _clear_python_package_build_caches(repo_root)

    force_flags = []
    if force:
        force_flags = ["--force-reinstall", "--no-cache-dir"]

    packages = _sdk_packages(repo_root)
    if editable:
        _clear_legacy_source_native_artifacts(repo_root)

    if target_dir is not None:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_dir = target_dir.resolve()
        _clear_target_python_package_metadata(target_dir, packages)
        print(f"Install mode: --target {target_dir} (single pip invocation, no-deps)")
        print("")
        print("========================================")
        print(f"  Installing {len(packages)} packages into {target_dir}")
        print("========================================")
        print("")
        pip_args = [
            *pip_cmd,
            "install",
            "--no-build-isolation",
            "--no-deps",
            "--upgrade",
            "--target",
            str(target_dir),
            *force_flags,
            *(str(repo_root / package.path) for package in packages),
        ]
        return _run(pip_args, cwd=repo_root, env=env)

    print("Install mode: current pip environment (sequential pip install)")
    nodeps_flag = ["--no-deps"] if editable or force else []
    package_count = len(packages)
    for package_index, package in enumerate(packages, start=1):
        package_editable = editable and package.editable
        editable_flag = ["-e"] if package_editable else []
        if package_editable:
            mode = " (editable)"
        elif editable:
            mode = " (regular; package has no editable sources)"
        else:
            mode = ""
        print("\n========================================")
        print(f"  Installing {package.path}{mode}")
        print("========================================")
        print("")
        result = _run(
            [
                *pip_cmd,
                "install",
                "--no-build-isolation",
                *force_flags,
                *nodeps_flag,
                *editable_flag,
                str(repo_root / package.path),
            ],
            cwd=repo_root,
            env=env,
        )
        if result != 0:
            _print_install_failure_summary(
                package=package,
                package_index=package_index,
                package_count=package_count,
                repo_root=repo_root,
                editable=package_editable,
            )
            return result

    print("")
    print("========================================")
    print("  All pip packages installed!")
    print("========================================")
    return 0
