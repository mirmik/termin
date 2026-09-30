"""Strict SDK product context shared by the repository test runners."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .sdk_profiles import SdkProfileError, load_installed_sdk_product, load_sdk_profiles

TEST_SDK_PROFILES = frozenset({"full", "graphics", "core"})


class TestSdkContextError(ValueError):
    """A test runner selected an invalid or conflicting SDK product context."""


def _test_profile(profile: str, context: str) -> str:
    if profile not in TEST_SDK_PROFILES:
        raise TestSdkContextError(f"{context}: unsupported test SDK profile {profile!r}")
    return profile


def load_installed_test_sdk_profile(sdk_prefix: Path) -> str:
    try:
        product = load_installed_sdk_product(Path(sdk_prefix))
    except SdkProfileError as error:
        raise TestSdkContextError(str(error)) from error
    return _test_profile(product.profile_id, str(sdk_prefix))


def load_configured_test_sdk_profile(build_dir: Path) -> str:
    cache = Path(build_dir) / "CMakeCache.txt"
    try:
        lines = cache.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise TestSdkContextError(f"cannot read configured SDK context {cache}: {error}") from error
    values = []
    for line in lines:
        if line.startswith("TERMIN_SDK_PROFILE:"):
            key, separator, value = line.partition("=")
            if separator and key in {"TERMIN_SDK_PROFILE:STRING", "TERMIN_SDK_PROFILE:INTERNAL"}:
                values.append(value)
            else:
                raise TestSdkContextError(f"{cache}: malformed TERMIN_SDK_PROFILE declaration")
    if len(values) != 1:
        raise TestSdkContextError(f"{cache}: requires exactly one TERMIN_SDK_PROFILE declaration")
    return _test_profile(values[0], str(cache))


def resolve_test_sdk_context(
    repo_root: Path,
    *,
    profile: str | None = None,
    sdk_prefix: Path | None = None,
    termin_sdk: Path | None = None,
    build_dir: Path | None = None,
    build_type: str = "Release",
    installed: bool = False,
    environment_root: Path | None = None,
) -> dict[str, str]:
    repo_root = repo_root.resolve()
    profiles = load_sdk_profiles(repo_root)
    explicit_sdk = sdk_prefix or termin_sdk
    if sdk_prefix is not None and termin_sdk is not None and sdk_prefix.resolve() != termin_sdk.resolve():
        raise TestSdkContextError("SDK_PREFIX and TERMIN_SDK select different SDK directories")
    identities: list[tuple[str, str]] = []
    if profile is not None:
        identities.append(("requested profile", _test_profile(profile, "requested profile")))
    if explicit_sdk is not None and (installed or explicit_sdk.exists()):
        identities.append(("installed SDK", load_installed_test_sdk_profile(explicit_sdk)))
    if build_dir is not None and build_dir.exists():
        identities.append(("configured build", load_configured_test_sdk_profile(build_dir)))
    selected = _test_profile(
        identities[0][1] if identities else profiles.default_profile, "selected profile"
    )
    for context, identity in identities:
        if identity != selected:
            raise TestSdkContextError(f"{context} profile {identity!r} conflicts with selected profile {selected!r}")
    recipe = profiles.profile(selected)
    resolved_sdk = (explicit_sdk or repo_root / recipe.sdk_prefix).resolve()
    if installed:
        identity = load_installed_test_sdk_profile(resolved_sdk)
        if identity != selected:
            raise TestSdkContextError(f"installed SDK profile {identity!r} conflicts with selected profile {selected!r}")
    suffix = f"-{recipe.build_directory_suffix}" if recipe.build_directory_suffix else ""
    resolved_build = (build_dir or repo_root / "build" / f"{build_type}{suffix}").resolve()
    resolved_environment = (environment_root or repo_root / "build" / "python-envs" / f"test{suffix}").resolve()
    return {
        "profile": selected,
        "sdk-prefix": str(resolved_sdk),
        "build-dir": str(resolved_build),
        "environment-root": str(resolved_environment),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--build-type", default="Release", choices=("Release", "Debug"))
    parser.add_argument("--profile", choices=sorted(TEST_SDK_PROFILES))
    parser.add_argument("--sdk-prefix", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--field", choices=("profile", "sdk-prefix", "build-dir", "environment-root"))
    args = parser.parse_args(argv)
    try:
        context = resolve_test_sdk_context(
            args.repo_root,
            profile=args.profile,
            sdk_prefix=args.sdk_prefix or (Path(os.environ["SDK_PREFIX"]) if os.environ.get("SDK_PREFIX") else None),
            termin_sdk=Path(os.environ["TERMIN_SDK"]) if os.environ.get("TERMIN_SDK") else None,
            build_dir=args.build_dir or (Path(os.environ["BUILD_DIR"]) if os.environ.get("BUILD_DIR") else None),
            build_type=args.build_type,
            installed=args.installed,
            environment_root=Path(os.environ["TERMIN_TEST_ENV"]) if os.environ.get("TERMIN_TEST_ENV") else None,
        )
    except (TestSdkContextError, SdkProfileError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(context[args.field] if args.field else json.dumps(context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
