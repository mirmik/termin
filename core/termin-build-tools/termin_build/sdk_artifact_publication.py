"""Native dependency inspection and SDK artifact-manifest publication."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from .artifact_manifest import (
    BUILD_MANIFEST_KIND,
    BUILD_MANIFEST_NAME,
    SCHEMA_VERSION as ARTIFACT_MANIFEST_SCHEMA,
    SDK_MANIFEST_KIND,
    SDK_MANIFEST_NAME,
    compute_native_build_id,
    sha256_file,
)
from .python_abi import PythonAbiIdentity
from .sdk_capabilities import write_desktop_capabilities
from .sdk_native_artifacts import (
    find_installed_artifact as _find_installed_artifact,
    find_native_artifact as _find_native_artifact,
    pe_import_dependencies as _pe_import_dependencies,
)
from .sdk_product_inputs import _sdk_application_payloads, _sdk_packages
from .sdk_python_layout import _is_windows


def _native_runtime_dependencies(binary: Path) -> list[str]:
    if _is_windows():
        return _pe_import_dependencies(binary)
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["LANGUAGE"] = "C"
    try:
        result = subprocess.run(
            ["readelf", "-d", str(binary)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except OSError as error:
        raise RuntimeError(f"failed to execute readelf for {binary}: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if not detail:
            detail = f"exit code {result.returncode}"
        raise RuntimeError(f"readelf failed for {binary}: {detail}")
    dependencies = []
    for line in result.stdout.splitlines():
        if "(NEEDED)" not in line:
            continue
        opening = line.rfind("[")
        closing = line.find("]", opening + 1)
        if opening < 0 or closing < 0:
            raise RuntimeError(f"readelf returned an unrecognized NEEDED entry for {binary}: {line.strip()}")
        dependency = line[opening + 1 : closing]
        dependencies.append(dependency)
    return dependencies


def write_artifacts(
    repo_root: Path,
    build_dir: Path,
    sdk_prefix: Path,
    install_dir: Path | None = None,
    *,
    python_abi: PythonAbiIdentity | None = None,
) -> int:
    packages = _sdk_packages(repo_root)
    application_payloads = _sdk_application_payloads(repo_root)
    python_abi = python_abi or PythonAbiIdentity.current()
    build_artifacts = []
    sdk_artifacts = []
    missing_required = []
    artifact_install_dir = install_dir if install_dir is not None else sdk_prefix
    sdk_root = sdk_prefix.resolve()

    feature_cache_keys = {
        "sdl": "TERMIN_ENABLE_SDL",
        "recast": "TERMIN_NAVMESH_BUILD_RECAST",
    }
    cache_values: dict[str, bool] = {}
    cache_path = build_dir / "CMakeCache.txt"
    if cache_path.is_file():
        for line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("//") or ":" not in line or "=" not in line:
                continue
            key_and_type, value = line.split("=", 1)
            key, _type = key_and_type.split(":", 1)
            cache_values[key] = value.strip().upper() in {"1", "ON", "TRUE", "YES", "Y"}

    def feature_enabled(feature: str) -> bool:
        cache_key = feature_cache_keys.get(feature)
        return cache_key is None or cache_key not in cache_values or cache_values[cache_key]

    def bundled_runtime_dependencies(names: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        bundled = []
        external = []
        pending = list(names)
        visited = set()
        while pending:
            name = pending.pop(0)
            if name in visited:
                continue
            visited.add(name)
            candidates = (sdk_root / "lib" / name, sdk_root / "bin" / name)
            dependency_path = next((path for path in candidates if path.is_file()), None)
            if dependency_path is None:
                external.append(name)
                continue
            bundled.append(
                {
                    "name": name,
                    "path": dependency_path.relative_to(sdk_root).as_posix(),
                    "sha256": sha256_file(dependency_path),
                }
            )
            pending.extend(_native_runtime_dependencies(dependency_path))
        return bundled, external

    extension_owners = [
        (
            package.path,
            {"package_path": package.path, "distribution": package.distribution},
            package.features,
            native_extension,
        )
        for package in packages
        for native_extension in package.native_extensions
    ]
    extension_owners.extend(
        (
            payload.name,
            {"application_payload": payload.name},
            (),
            native_extension,
        )
        for payload in application_payloads
        for native_extension in payload.native_extensions
    )

    for owner, ownership, owner_features, native_extension in extension_owners:
        extension_features = tuple(dict.fromkeys((*owner_features, *native_extension.features)))
        if not all(feature_enabled(feature) for feature in extension_features):
            continue
        build_path = _find_native_artifact(
            build_dir,
            native_extension.target,
            python_abi=python_abi,
        )
        if build_path is None:
            if native_extension.optional:
                continue
            missing_required.append(f"{owner}: {native_extension.extension} (target {native_extension.target})")
            continue
        installed_path = _find_installed_artifact(
            artifact_install_dir,
            native_extension.extension,
            native_extension.target,
            python_abi=python_abi,
        )
        if installed_path is None:
            missing_required.append(
                f"{owner}: installed {native_extension.extension} (target {native_extension.target})"
            )
            continue
        installed_path = installed_path.resolve()
        try:
            installed_relative = installed_path.relative_to(sdk_root)
        except ValueError:
            missing_required.append(f"{owner}: installed artifact is outside SDK root: {installed_path}")
            continue
        try:
            dependency_names = _native_runtime_dependencies(installed_path)
            runtime_dependencies, external_dependencies = bundled_runtime_dependencies(dependency_names)
        except RuntimeError as error:
            print(
                f"ERROR: failed to inspect native dependencies: {error}",
                file=sys.stderr,
            )
            return 1
        common = {
            "kind": "python-extension",
            **ownership,
            "extension": native_extension.extension,
            "target": native_extension.target,
            "optional": native_extension.optional,
            "features": list(extension_features),
            "external_runtime_dependencies": external_dependencies,
        }
        build_artifacts.append(
            {
                **common,
                "path": str(build_path.resolve()),
                "sha256": sha256_file(build_path),
                "runtime_dependencies": [],
            }
        )
        sdk_artifacts.append(
            {
                **common,
                "path": installed_relative.as_posix(),
                "sha256": sha256_file(installed_path),
                "runtime_dependencies": runtime_dependencies,
            }
        )

    if missing_required:
        print("ERROR: required native artifacts are missing:", file=sys.stderr)
        for missing in missing_required:
            print(f"  - {missing}", file=sys.stderr)
        return 1

    build_manifest = {
        "schema": ARTIFACT_MANIFEST_SCHEMA,
        "manifest_kind": BUILD_MANIFEST_KIND,
        "python_abi": python_abi.to_dict(),
        "native_build_id": compute_native_build_id(build_artifacts, python_abi),
        "artifacts": build_artifacts,
    }
    build_output = build_dir / BUILD_MANIFEST_NAME
    build_output.parent.mkdir(parents=True, exist_ok=True)
    build_output.write_text(
        json.dumps(build_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sdk_manifest = {
        "schema": ARTIFACT_MANIFEST_SCHEMA,
        "manifest_kind": SDK_MANIFEST_KIND,
        "python_abi": python_abi.to_dict(),
        "native_build_id": compute_native_build_id(sdk_artifacts, python_abi),
        "artifacts": sdk_artifacts,
    }
    sdk_prefix.mkdir(parents=True, exist_ok=True)
    sdk_output = sdk_prefix / SDK_MANIFEST_NAME
    sdk_output.write_text(
        json.dumps(sdk_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        write_desktop_capabilities(sdk_root=sdk_prefix)
    except (OSError, RuntimeError) as error:
        print(f"ERROR: failed to write desktop SDK capabilities: {error}", file=sys.stderr)
        return 1
    print(f"Wrote build artifact manifest: {build_output}")
    print(f"Wrote SDK artifact manifest: {sdk_output}")
    return 0
