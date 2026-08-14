"""Prepare a complete runtime package for Android APK asset merging."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from termin.project_build.diagnostics import format_diagnostics
from termin.project_build.runtime_package.package_files import write_json
from termin.project_build.runtime_package.shaders import (
    write_default_pipeline_shader_artifacts,
)
from termin.project_build.runtime_package_validator import validate_runtime_package


@dataclass(frozen=True)
class PreparedAndroidRuntimeAssets:
    output_dir: Path
    generated_builtin_shader_contract: bool


def prepare_android_runtime_assets(
    source_dir: str | Path,
    output_dir: str | Path,
    shader_compiler: str | Path,
) -> PreparedAndroidRuntimeAssets:
    """Stage and validate APK assets, generating the built-in shader closure if absent."""

    source = Path(source_dir).resolve()
    output = Path(output_dir).resolve()
    compiler = Path(shader_compiler).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Android runtime assets directory does not exist: {source}")
    if source == output:
        raise ValueError("Android runtime asset staging output must differ from its source")
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError(
            "Android runtime asset staging output must not contain its source directory"
        )

    manifest_source = source / "manifest.json"
    if not manifest_source.is_file():
        raise FileNotFoundError(f"Android runtime manifest does not exist: {manifest_source}")

    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output)

    manifest_path = output / "manifest.json"
    manifest = _read_manifest(manifest_path)
    generated_contract = "builtin_shader_contract" not in manifest
    if generated_contract:
        if not compiler.is_file():
            raise FileNotFoundError(
                "Termin shader compiler is required to complete legacy Android runtime "
                f"assets: {compiler}"
            )
        export_diagnostics = []
        manifest["builtin_shader_contract"] = write_default_pipeline_shader_artifacts(
            output,
            export_diagnostics,
            compiler,
            ("vulkan",),
        )
        if any(diagnostic.level == "error" for diagnostic in export_diagnostics):
            raise RuntimeError(
                format_diagnostics(
                    "Android built-in shader export failed:", export_diagnostics
                )
            )
        write_json(manifest_path, manifest)

    validation_diagnostics = validate_runtime_package(output)
    if any(diagnostic.level == "error" for diagnostic in validation_diagnostics):
        raise RuntimeError(
            format_diagnostics(
                "Prepared Android runtime assets are invalid:", validation_diagnostics
            )
        )
    return PreparedAndroidRuntimeAssets(
        output_dir=output,
        generated_builtin_shader_contract=generated_contract,
    )


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read Android runtime manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Android runtime manifest must be an object: {path}")
    return value


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage and validate runtime assets for an Android APK"
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--shader-compiler", required=True, type=Path)
    return parser


def main() -> int:
    args = _create_parser().parse_args()
    result = prepare_android_runtime_assets(
        args.source,
        args.output,
        args.shader_compiler,
    )
    action = (
        "generated built-in shader closure"
        if result.generated_builtin_shader_contract
        else "preserved packaged built-in shader closure"
    )
    print(f"Prepared Android runtime assets: {result.output_dir} ({action})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
