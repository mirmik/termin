"""SPIR-V shader artifact generation for project builds."""

from __future__ import annotations

import shutil
import subprocess
import os
import sys
from collections.abc import Iterable
from pathlib import Path

from termin.project_builder.manifest import BuildResource


_STAGES: tuple[tuple[str, str, str], ...] = (
    ("vertex", "vert", "vertex_source"),
    ("fragment", "frag", "fragment_source"),
    ("geometry", "geom", "geometry_source"),
)


def compile_shader_usages(
    shader_usages: Iterable[object],
    output_dir: Path,
    shader_compiler: Path | None,
) -> list[BuildResource]:
    compiler = _resolve_shader_compiler(shader_compiler)
    source_dir = output_dir / ".build" / "shaders" / "source"
    artifact_dir = output_dir / "assets" / "shaders" / "vulkan"
    source_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    resources: list[BuildResource] = []
    seen: set[tuple[str, str]] = set()

    for shader in shader_usages:
        if not shader.is_valid:
            raise ValueError("Shader usage collector returned an invalid shader")

        shader_uuid = shader.uuid
        if shader_uuid == "":
            raise ValueError(f"Shader '{shader.name}' has empty uuid")

        for stage_name, stage_ext, attr_name in _STAGES:
            source = _shader_stage_source(shader, attr_name)
            if source == "":
                continue

            key = (shader_uuid, stage_ext)
            if key in seen:
                continue
            seen.add(key)

            source_path = source_dir / f"{shader_uuid}.{stage_ext}.glsl"
            artifact_path = artifact_dir / f"{shader_uuid}.{stage_ext}.spv"
            source_path.write_text(source, encoding="utf-8")

            _run_shader_compiler(
                compiler=compiler,
                stage=stage_name,
                input_path=source_path,
                output_path=artifact_path,
                debug_name=_shader_debug_name(shader, stage_name),
            )

            resources.append(
                BuildResource(
                    kind="generated",
                    type="shader_spirv",
                    source_path=_output_relative(output_dir, source_path),
                    build_path=_output_relative(output_dir, artifact_path),
                    uuid=shader_uuid,
                    name=shader.name or shader_uuid,
                    size=artifact_path.stat().st_size,
                )
            )

    return resources


def _shader_stage_source(shader: object, attr_name: str) -> str:
    if attr_name == "vertex_source":
        return shader.vertex_source
    if attr_name == "fragment_source":
        return shader.fragment_source
    if attr_name == "geometry_source":
        return shader.geometry_source
    raise ValueError(f"Unknown shader stage attribute: {attr_name}")


def _shader_debug_name(shader: object, stage: str) -> str:
    shader_name = shader.name
    if shader_name == "":
        shader_name = shader.uuid
    return f"{shader_name}:{stage}"


def _resolve_shader_compiler(shader_compiler: Path | None) -> Path:
    if shader_compiler is not None:
        compiler = Path(shader_compiler).resolve()
        if not compiler.exists():
            raise FileNotFoundError(f"Shader compiler does not exist: {compiler}")
        return compiler

    found = shutil.which("termin_shaderc")
    if found is not None:
        return Path(found).resolve()

    sdk_env = os.environ.get("TERMIN_SDK")
    if sdk_env is not None and sdk_env != "":
        sdk_compiler = Path(sdk_env).resolve() / "bin" / "termin_shaderc"
        if sdk_compiler.exists():
            return sdk_compiler

    raise FileNotFoundError(
        "Shader compiler 'termin_shaderc' was not found. "
        "Pass shader_compiler=..., add it to PATH, or install the SDK compiler tools."
    )


def _run_shader_compiler(
    compiler: Path,
    stage: str,
    input_path: Path,
    output_path: Path,
    debug_name: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _executable_command(compiler) + [
        str(compiler),
        "compile",
        "--target",
        "vulkan",
        "--stage",
        stage,
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--entry",
        "main",
        "--debug-name",
        debug_name,
    ]
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Shader compilation failed for {input_path.name}: {message}"
        )
    if not output_path.exists():
        raise RuntimeError(
            f"Shader compiler did not produce expected output: {output_path}"
        )


def _executable_command(path: Path) -> list[str]:
    if os.name == "nt" and path.suffix.lower() == ".py":
        return [sys.executable]
    return []


def _output_relative(output_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(output_dir.resolve()).as_posix()
