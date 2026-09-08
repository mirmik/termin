"""Termin SDK build orchestration helpers."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .package_manifest import repo_root_from
from .python_abi import PythonAbiError, PythonAbiIdentity
from .python_toolchain import PythonToolchainError
from .sdk_artifact_publication import (
    _native_runtime_dependencies as _native_runtime_dependencies,
    write_artifacts as write_artifacts,
)
from .sdk_build_support import (
    SDK_BUILD_REQUIREMENTS_RELATIVE as SDK_BUILD_REQUIREMENTS_RELATIVE,
    _clear_python_package_build_caches as _clear_python_package_build_caches,
    _resolve_bindings_dir as _resolve_bindings_dir,
    _run,
    _stage_script,
    prepare_pinned_python_build_environment as prepare_pinned_python_build_environment,
    prepare_python_build_environment as prepare_python_build_environment,
)
from .sdk_doctor import (
    DoctorProfile as DoctorProfile,
    ensure_submodules,
    load_doctor_profiles,
    missing_submodules,
    profile_submodules,
)
from .sdk_python_layout import (
    _is_windows,
    _python_executable,
    _python_version_and_paths,
    publish_cmake_python_install as publish_cmake_python_install,
    resolve_sdk_python_layout,
)
from .sdk_capabilities import write_android_capabilities
from .sdk_composition import (
    compose_installed_sdk,
)
from .sdk_package_install import install_pip_packages as install_pip_packages
from .sdk_product_inputs import (
    CORE_BUILD_ID_ENV as CORE_BUILD_ID_ENV,
    CORE_SDK_ENV as CORE_SDK_ENV,
    _SDK_PROFILE_CONTEXT,
    _active_sdk_profile,
    _installed_core_input as _installed_core_input,
)
from .sdk_profiles import (
    SdkProfile,
    SdkProfileError,
    load_installed_sdk_product,
    load_sdk_profiles as load_sdk_profiles,
    write_profiled_sdk_product,
)
from .sdk_python_install import (
    install_python_packages as install_python_packages,
    prepare_build_python_runtime as prepare_build_python_runtime,
)
from .slang_toolchain import SlangToolchainError, prepare_slang_toolchain
from .sdk_wheel_pipeline import (
    _publish_runtime_wheelhouse,
    _verify_library_wheel_subset_install,
    build_wheelhouse as build_wheelhouse,
    prepare_locked_runtime_wheels as prepare_locked_runtime_wheels,
)


def _tool_error(tool: str) -> str | None:
    if shutil.which(tool) is None:
        return f"required tool not found in PATH: {tool}"
    return None


def _pip_error() -> str | None:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        check=False,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.strip()
        suffix = f": {detail}" if detail else ""
        return f"pip is not available for {sys.executable}{suffix}"
    return None


def _copy_backend_error() -> str | None:
    if _is_windows():
        return None
    if shutil.which("rsync") is None:
        return "required copy backend not found in PATH: rsync"
    return None


def _sdk_writable_error(sdk_prefix: Path) -> str | None:
    if sdk_prefix.exists():
        if not sdk_prefix.is_dir():
            return f"SDK prefix exists but is not a directory: {sdk_prefix}"
        if not os.access(sdk_prefix, os.W_OK):
            return f"SDK prefix is not writable: {sdk_prefix}"
        return None

    current = sdk_prefix
    while not current.exists() and current.parent != current:
        current = current.parent
    if not current.exists():
        return f"no existing parent directory for SDK prefix: {sdk_prefix}"
    if not os.access(current, os.W_OK):
        return f"SDK prefix parent is not writable: {current}"
    return None


def _nanobind_error() -> str | None:
    try:
        import nanobind  # noqa: F401
    except Exception as e:
        return f"nanobind is not importable for {sys.executable}: {e}"
    return None


def _pip_cache_warning() -> str | None:
    pip_cache = Path.home() / ".cache" / "pip"
    if pip_cache.exists() and not os.access(pip_cache, os.W_OK):
        return f"pip cache is not writable and pip will disable cache: {pip_cache}"
    parent = pip_cache.parent
    if parent.exists() and not os.access(parent, os.W_OK):
        return f"pip cache parent is not writable and pip may disable cache: {parent}"
    return None


# Runtime package metadata and final verification have independent lifecycles,
# but remain re-exported here for callers of the historical sdk module.
from .sdk_runtime_metadata import (
    RUNTIME_LOCK_RELATIVE as RUNTIME_LOCK_RELATIVE,
)
from .sdk_verification import (
    verify_nanobind_extensions,
    verify_no_duplicate_libraries as verify_no_duplicate_libraries,
    verify_python_runtime_manifest as verify_python_runtime_manifest,
    verify_python_wheelhouse as verify_python_wheelhouse,
    verify_sdk,
    verify_sdk_artifacts as verify_sdk_artifacts,
    verify_sdk_python_launcher as verify_sdk_python_launcher,
)


def _build_dir(
    repo_root: Path,
    build_type: str,
    profile: SdkProfile | None = None,
) -> Path:
    profile = profile or _active_sdk_profile(repo_root)
    env_build_dir = os.environ.get("BUILD_DIR")
    suffix = f"-{profile.build_directory_suffix}" if profile.build_directory_suffix else ""
    default_name = f"{build_type}{suffix}"
    return Path(env_build_dir) if env_build_dir else repo_root / "build" / default_name


def _sdk_prefix(repo_root: Path) -> Path:
    profile = _active_sdk_profile(repo_root)
    return Path(os.environ.get("SDK_PREFIX", str(repo_root / profile.sdk_prefix)))


def _bundled_site_packages_hint(sdk_prefix: Path) -> Path:
    if _is_windows():
        return sdk_prefix / "python" / "Lib" / "site-packages"
    return sdk_prefix / "lib" / "python3.*" / "site-packages"


def _run_sdk_build_impl(
    repo_root: Path,
    build_type: str,
    stage_args: list[str],
    build_csharp: bool,
    dry_run: bool,
    profile: SdkProfile,
) -> int:
    default_sdk = repo_root / profile.sdk_prefix
    sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(default_sdk)))
    build_dir = _build_dir(repo_root, build_type, profile)
    build_env = os.environ.copy()
    build_env["SDK_PREFIX"] = str(sdk_prefix)
    build_env["BUILD_DIR"] = str(build_dir)
    if dry_run:
        print("+ ensure pinned free-threaded Python toolchain")
        build_python = Path(_python_executable())
    else:
        try:
            build_python = prepare_pinned_python_build_environment(repo_root)
        except (PythonAbiError, PythonToolchainError, OSError, RuntimeError) as error:
            print(
                f"ERROR: failed to prepare pinned Python toolchain: {error}",
                file=sys.stderr,
            )
            return 1
    build_env["PYTHON_BIN"] = str(build_python)
    build_env["PYTHON_EXECUTABLE"] = str(build_python)
    if dry_run:
        print("+ prepare pinned Slang host toolchain")
    else:
        try:
            slangc = prepare_slang_toolchain(repo_root, build_python)
        except (OSError, SlangToolchainError) as error:
            print(
                f"ERROR: failed to prepare pinned Slang toolchain: {error}",
                file=sys.stderr,
            )
            return 1
        build_env["TERMIN_SLANGC"] = str(slangc)

    print("")
    print("========================================")
    print("  Stage 1/4: C/C++ libraries + Python bindings")
    print("========================================")
    print("")
    command = _stage_script(repo_root, "build-sdk-bindings") + [f"--profile={profile.name}"] + stage_args
    if dry_run:
        print("+ " + " ".join(command))
    else:
        result = _run(command, cwd=repo_root, env=build_env)
        if result != 0:
            return result

    print("")
    print("========================================")
    print("  Stage 2/4: C# bindings")
    print("========================================")
    print("")
    if build_csharp and profile.csharp_profile is not None:
        command = _stage_script(repo_root, "build-sdk-csharp") + [f"--profile={profile.csharp_profile}"] + stage_args
        if dry_run:
            print("+ " + " ".join(command))
        else:
            result = _run(command, cwd=repo_root, env=build_env)
            if result != 0:
                return result
    else:
        print("Skipping C# bindings (use --csharp on Linux).")

    print("")
    print("========================================")
    print("  Stage 3/4: Populate bundled Python site-packages")
    print("========================================")
    print("")
    if dry_run:
        print("+ write installed SDK product verification manifest")
        print(f"+ install bundled Python packages into {_bundled_site_packages_hint(sdk_prefix)}")
    else:
        try:
            write_profiled_sdk_product(repo_root, sdk_prefix, profile)
        except (OSError, RuntimeError, SdkProfileError) as error:
            print(f"ERROR: failed to write SDK product manifest: {error}", file=sys.stderr)
            return 1
        result = install_python_packages(
            repo_root,
            sdk_prefix,
            build_dir,
            python_executable=build_python,
        )
        if result != 0:
            return result

    legacy_sdk_python = sdk_prefix / "lib" / "python"
    if not dry_run and legacy_sdk_python.is_dir():
        print(f"Removing legacy SDK Python staging tree: {legacy_sdk_python}")
        shutil.rmtree(legacy_sdk_python)

    # Stage 1 records native extensions from the CMake install staging tree.
    # Stage 3 installs their wheels into the bundled runtime and removes that
    # legacy tree, so publish a final manifest whose paths and hashes describe
    # the actual SDK layout consumed by launchers and wheelhouse validation.
    if not dry_run:
        runtime_python_abi = PythonAbiIdentity.from_runtime_probe(
            _python_version_and_paths(str(build_python)),
            context="SDK target Python",
        )
        result = write_artifacts(
            repo_root,
            build_dir,
            sdk_prefix,
            python_abi=runtime_python_abi,
        )
        if result != 0:
            return result

    print("")
    print("========================================")
    print("  Stage 4/4: Publish SDK Python wheelhouse")
    print("========================================")
    print("")
    if dry_run:
        print("+ publish Stage 3 wheel artifacts into SDK wheelhouse")
    else:
        result = _publish_runtime_wheelhouse(repo_root, sdk_prefix)
        if result != 0:
            return result
        result = _verify_library_wheel_subset_install(
            repo_root,
            sdk_prefix / "wheels",
            build_python,
        )
        if result != 0:
            return result

    print("")
    print("========================================")
    print("  Verifying SDK")
    print("========================================")
    print("")
    if dry_run:
        print("+ verify SDK duplicate libraries and stale artifacts")
    else:
        result = verify_sdk(sdk_prefix, build_dir)
        if result != 0:
            return result

    print("")
    print("========================================")
    print("  All done!")
    print("========================================")
    return 0


def run_sdk_build(
    repo_root: Path,
    build_type: str,
    stage_args: list[str],
    build_csharp: bool,
    dry_run: bool,
    profile_name: str | None = None,
) -> int:
    profiles = load_sdk_profiles(repo_root)
    profile = profiles.profile(profile_name or profiles.default_profile)
    token = _SDK_PROFILE_CONTEXT.set(profile.name)
    try:
        return _run_sdk_build_impl(
            repo_root=repo_root,
            build_type=build_type,
            stage_args=stage_args,
            build_csharp=build_csharp,
            dry_run=dry_run,
            profile=profile,
        )
    finally:
        _SDK_PROFILE_CONTEXT.reset(token)


def doctor(
    repo_root: Path,
    profile_name: str,
    vulkan: str,
    init_submodules: bool,
    require_nanobind: bool,
    sdk_prefix: Path,
    sdl: str = "OFF",
) -> int:
    recipe = load_doctor_profiles(repo_root)
    profile = recipe.profile(profile_name)
    errors = []
    warnings = []

    if profile.needs_git:
        error = _tool_error("git")
        if error:
            errors.append(error)
    if profile.needs_cmake:
        error = _tool_error("cmake")
        if error:
            errors.append(error)
    if profile.needs_nanobind or require_nanobind:
        error = _nanobind_error()
        if error:
            errors.append(error)
    if profile.needs_pip:
        error = _pip_error()
        if error:
            errors.append(error)
    if profile.needs_copy_backend:
        error = _copy_backend_error()
        if error:
            errors.append(error)
    if profile.needs_sdk_writable:
        error = _sdk_writable_error(sdk_prefix)
        if error:
            errors.append(error)

    warning = _pip_cache_warning()
    if warning:
        warnings.append(warning)

    required_submodules = profile_submodules(profile, vulkan, sdl)
    missing = missing_submodules(
        repo_root,
        required_submodules,
        expected_files=recipe.expected_submodule_files,
    )
    if missing and init_submodules:
        result = ensure_submodules(
            repo_root,
            required_submodules,
            expected_files=recipe.expected_submodule_files,
        )
        if result != 0:
            return result
        missing = missing_submodules(
            repo_root,
            required_submodules,
            expected_files=recipe.expected_submodule_files,
        )
    if missing:
        errors.append("required submodules are missing: " + ", ".join(missing))

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Termin build doctor OK ({profile.name})")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root. Defaults to auto-discovery from cwd.",
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor_parser = subparsers.add_parser("doctor", help="Run build preflight checks.")
    doctor_parser.add_argument(
        "--profile",
        default="sdk-bindings",
    )
    doctor_parser.add_argument(
        "--vulkan",
        choices=("ON", "OFF"),
        default="ON",
    )
    doctor_parser.add_argument(
        "--sdl",
        choices=("ON", "OFF"),
        default="OFF",
    )
    doctor_parser.add_argument(
        "--init-submodules",
        action="store_true",
        help="Initialize missing required git submodules.",
    )
    doctor_parser.add_argument(
        "--require-nanobind",
        action="store_true",
        help="Require nanobind even if the selected profile does not.",
    )
    doctor_parser.add_argument(
        "--sdk-prefix",
        type=Path,
        default=None,
        help="SDK install prefix to validate. Defaults to SDK_PREFIX or ./sdk.",
    )

    ensure_parser = subparsers.add_parser(
        "ensure-submodules",
        help="Initialize the requested submodules if they are missing.",
    )
    ensure_parser.add_argument("paths", nargs="+")

    artifacts_parser = subparsers.add_parser(
        "write-artifacts",
        help="Write sdk/termin-artifacts.json from build outputs and package manifest.",
    )
    artifacts_parser.add_argument("--build-dir", type=Path, required=True)
    artifacts_parser.add_argument("--sdk-prefix", type=Path, required=True)
    artifacts_parser.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        help="CMake install tree to search for installed native artifacts.",
    )

    android_capabilities_parser = subparsers.add_parser(
        "write-android-capabilities",
        help="Record truthful per-ABI and aggregate Android SDK capabilities.",
    )
    android_capabilities_parser.add_argument("--sdk-root", type=Path, required=True)
    android_capabilities_parser.add_argument("--android-sdk-root", type=Path, required=True)
    android_capabilities_parser.add_argument("--abi", required=True)
    android_capabilities_parser.add_argument("--build-dir", type=Path, required=True)

    install_python_parser = subparsers.add_parser(
        "install-python",
        help="Populate the bundled SDK Python site-packages.",
    )
    install_python_parser.add_argument("--build-type", default="Release")

    prepare_python_parser = subparsers.add_parser(
        "prepare-build-python-runtime",
        help="Prepare bundled Python runtime files before native CMake configure.",
    )
    prepare_python_parser.add_argument(
        "--sdk-prefix",
        type=Path,
        default=None,
        help="SDK install prefix. Defaults to SDK_PREFIX or ./sdk.",
    )

    subparsers.add_parser(
        "prepare-python-toolchain",
        help="Materialize the pinned free-threaded Python build environment.",
    )

    resolve_python_parser = subparsers.add_parser(
        "resolve-python-layout",
        help="Validate the SDK Python ABI and print its site-packages path.",
    )
    resolve_python_parser.add_argument("--sdk-prefix", type=Path, required=True)
    resolve_python_parser.add_argument(
        "--require-native-bindings",
        action="store_true",
        help="Require the termin.base native extension in the resolved layout.",
    )

    publish_python_parser = subparsers.add_parser(
        "publish-cmake-python",
        help="Normalize the staged CMake Python install into SDK site-packages.",
    )
    publish_python_parser.add_argument("--install-dir", type=Path, required=True)
    publish_python_parser.add_argument("--sdk-prefix", type=Path, required=True)
    publish_python_parser.add_argument(
        "--modules-only",
        action="store_true",
        help="publish extension modules without requiring a bundled Python runtime",
    )

    install_packages_parser = subparsers.add_parser(
        "install-packages",
        help="Install Termin Python packages into the current Python or --target.",
    )
    install_packages_parser.add_argument("--build-type", default="Release")
    install_packages_parser.add_argument("--editable", "-e", action="store_true")
    install_packages_parser.add_argument("--force", "-f", action="store_true")
    install_packages_parser.add_argument("--target", type=Path, default=None)

    wheels_parser = subparsers.add_parser(
        "wheels",
        help="Build SDK-backed Python wheels.",
    )
    wheels_parser.add_argument("--build-type", default="Release")

    verify_parser = subparsers.add_parser(
        "verify-sdk",
        help="Run SDK duplicate/stale artifact checks.",
    )
    verify_parser.add_argument("--build-type", default="Release")

    compose_parser = subparsers.add_parser(
        "compose-sdk",
        help="Compose a standalone SDK and one or more thin SDK layers.",
    )
    compose_parser.add_argument("--base-sdk", type=Path, required=True)
    compose_parser.add_argument("--layer-sdk", type=Path, action="append", required=True)
    compose_parser.add_argument("--output", type=Path, required=True)

    import_gate_parser = subparsers.add_parser(
        "verify-python-import-graph",
        help="Import the installed SDK graph and require the GIL to remain disabled.",
    )
    import_gate_parser.add_argument(
        "--sdk-prefix",
        type=Path,
        default=None,
        help="SDK install prefix. Defaults to SDK_PREFIX or ./sdk.",
    )

    build_parser = subparsers.add_parser(
        "build",
        help="Build the full SDK through the existing stage scripts.",
    )
    build_parser.add_argument("--debug", "-d", action="store_true")
    build_parser.add_argument(
        "--csharp",
        action="store_true",
        help="Build C# bindings on Linux (enabled by default on Windows).",
    )
    build_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the SDK build stages without executing them.",
    )
    build_parser.add_argument(
        "--profile",
        default=None,
        help="Repository-declared SDK product profile (default: manifest default).",
    )

    args, unknown_args = parser.parse_known_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from(Path.cwd())

    if args.command == "doctor":
        sdk_prefix = args.sdk_prefix
        if sdk_prefix is None:
            sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        return doctor(
            repo_root=repo_root,
            profile_name=args.profile,
            vulkan=args.vulkan,
            sdl=args.sdl,
            init_submodules=args.init_submodules,
            require_nanobind=args.require_nanobind,
            sdk_prefix=sdk_prefix,
        )
    if args.command == "ensure-submodules":
        recipe = load_doctor_profiles(repo_root)
        return ensure_submodules(
            repo_root,
            args.paths,
            expected_files=recipe.expected_submodule_files,
        )
    if args.command == "write-artifacts":
        return write_artifacts(
            repo_root=repo_root,
            build_dir=args.build_dir,
            sdk_prefix=args.sdk_prefix,
            install_dir=args.install_dir,
        )
    if args.command == "write-android-capabilities":
        return write_android_capabilities(
            sdk_root=args.sdk_root.resolve(),
            android_sdk_root=args.android_sdk_root.resolve(),
            abi=args.abi,
            build_dir=args.build_dir.resolve(),
        )
    if args.command == "install-python":
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = _sdk_prefix(repo_root)
        try:
            python_executable = prepare_pinned_python_build_environment(repo_root)
            write_profiled_sdk_product(
                repo_root,
                sdk_prefix,
                _active_sdk_profile(repo_root),
            )
        except (
            PythonAbiError,
            PythonToolchainError,
            OSError,
            RuntimeError,
            SdkProfileError,
        ) as error:
            print(
                f"ERROR: failed to prepare SDK Python installation: {error}",
                file=sys.stderr,
            )
            return 1
        result = install_python_packages(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
            python_executable=python_executable,
        )
        return result if result != 0 else _publish_runtime_wheelhouse(repo_root, sdk_prefix)
    if args.command == "prepare-build-python-runtime":
        sdk_prefix = args.sdk_prefix
        if sdk_prefix is None:
            sdk_prefix = Path(os.environ.get("SDK_PREFIX", str(repo_root / "sdk")))
        return prepare_build_python_runtime(sdk_prefix)
    if args.command == "prepare-python-toolchain":
        try:
            python_executable = prepare_pinned_python_build_environment(repo_root)
        except (
            PythonAbiError,
            PythonToolchainError,
            OSError,
            RuntimeError,
        ) as error:
            print(
                f"ERROR: failed to prepare pinned Python toolchain: {error}",
                file=sys.stderr,
            )
            return 1
        print(python_executable.resolve())
        return 0
    if args.command == "resolve-python-layout":
        try:
            site_packages = resolve_sdk_python_layout(
                args.sdk_prefix,
                require_native_bindings=args.require_native_bindings,
            )
        except RuntimeError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(site_packages.resolve())
        return 0
    if args.command == "publish-cmake-python":
        try:
            publish_cmake_python_install(
                install_dir=args.install_dir,
                sdk_prefix=args.sdk_prefix,
                modules_only=args.modules_only,
            )
        except RuntimeError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        return 0
    if args.command == "install-packages":
        if unknown_args:
            print(
                f"ERROR: unknown install-packages option: {unknown_args[0]}",
                file=sys.stderr,
            )
            return 1
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = _sdk_prefix(repo_root)
        return install_pip_packages(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
            target_dir=args.target,
            editable=args.editable,
            force=args.force,
        )
    if args.command == "wheels":
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = _sdk_prefix(repo_root)
        wheel_args = list(unknown_args)
        try:
            python_executable = prepare_pinned_python_build_environment(repo_root)
        except (
            PythonAbiError,
            PythonToolchainError,
            OSError,
            RuntimeError,
        ) as error:
            print(
                f"ERROR: failed to prepare pinned Python toolchain: {error}",
                file=sys.stderr,
            )
            return 1
        return build_wheelhouse(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            build_dir=build_dir,
            stage_args=wheel_args,
            python_executable=python_executable,
        )
    if args.command == "verify-sdk":
        build_dir = _build_dir(repo_root, args.build_type)
        sdk_prefix = _sdk_prefix(repo_root)
        return verify_sdk(sdk_prefix=sdk_prefix, build_dir=build_dir)
    if args.command == "compose-sdk":
        try:
            output = compose_installed_sdk(
                base_root=args.base_sdk,
                layer_roots=tuple(args.layer_sdk),
                output_root=args.output,
            )
        except (OSError, RuntimeError) as error:
            print(f"ERROR: cannot compose installed SDK: {error}", file=sys.stderr)
            return 1
        print(f"Composed SDK: {output.parent}")
        return 0
    if args.command == "verify-python-import-graph":
        sdk_prefix = (args.sdk_prefix or _sdk_prefix(repo_root)).resolve()
        product = load_installed_sdk_product(sdk_prefix)
        return verify_nanobind_extensions(
            sdk_prefix,
            product_import_roots=product.native_import_roots,
        )
    if args.command == "build":
        obsolete_wheel_flags = {"--no-wheels", "--wheels"} & set(unknown_args)
        if obsolete_wheel_flags:
            obsolete = sorted(obsolete_wheel_flags)[0]
            print(
                f"ERROR: {obsolete} was removed; full SDK builds always publish the canonical wheel artifact set",
                file=sys.stderr,
            )
            return 2
        build_type = "Debug" if args.debug else "Release"
        stage_args = list(unknown_args)
        if args.debug and "--debug" not in stage_args and "-d" not in stage_args:
            stage_args.insert(0, "--debug")
        return run_sdk_build(
            repo_root=repo_root,
            build_type=build_type,
            stage_args=stage_args,
            build_csharp=_is_windows() or args.csharp,
            dry_run=args.dry_run,
            profile_name=args.profile,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
