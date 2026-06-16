"""SPIR-V shader artifact generation for project builds."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from termin.shader_tools import existing_executable, resolve_path_tool, resolve_sdk_tool
from termin.project_builder.manifest import BuildResource


_STAGES: tuple[tuple[str, str, str], ...] = (
    ("vertex", "vert", "vertex_source"),
    ("fragment", "frag", "fragment_source"),
    ("geometry", "geom", "geometry_source"),
)

_TARGETS_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "glsl": ("vulkan",),
    "slang": ("vulkan", "opengl"),
}


def compile_shader_usages(
    shader_usages: Iterable[object],
    output_dir: Path,
    shader_compiler: Path | None,
) -> list[BuildResource]:
    compiler = _resolve_shader_compiler(shader_compiler)
    source_dir = output_dir / ".build" / "shaders" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    resources: list[BuildResource] = []
    seen: set[tuple[str, str, str]] = set()

    for shader in shader_usages:
        if not shader.is_valid:
            raise ValueError("Shader usage collector returned an invalid shader")

        shader_uuid = shader.uuid
        if shader_uuid == "":
            raise ValueError(f"Shader '{shader.name}' has empty uuid")

        language = _shader_language(shader)
        targets = _TARGETS_BY_LANGUAGE.get(language)
        if targets is None:
            raise ValueError(f"Shader '{shader.name}' has unsupported language: {language}")

        for stage_name, stage_ext, attr_name in _STAGES:
            source = _shader_stage_source(shader, attr_name)
            if source == "":
                continue

            source_path = source_dir / f"{shader_uuid}.{stage_ext}.{_source_extension(language)}"
            source_path.write_text(source, encoding="utf-8")

            for target in targets:
                key = (shader_uuid, target, stage_ext)
                if key in seen:
                    continue
                seen.add(key)

                artifact_dir = output_dir / "assets" / "shaders" / target
                artifact_path = artifact_dir / f"{shader_uuid}.{stage_ext}.{_artifact_extension(target)}"

                _run_shader_compiler(
                    compiler=compiler,
                    language=language,
                    target=target,
                    stage=stage_name,
                    input_path=source_path,
                    output_path=artifact_path,
                    debug_name=_shader_debug_name(shader, stage_name),
                )

                resources.append(
                    BuildResource(
                        kind="generated",
                        type=_resource_type(target),
                        source_path=_output_relative(output_dir, source_path),
                        build_path=_output_relative(output_dir, artifact_path),
                        uuid=shader_uuid,
                        name=shader.name or shader_uuid,
                        size=artifact_path.stat().st_size,
                    )
                )

    return resources


def _shader_language(shader: object) -> str:
    try:
        language = shader.language
    except AttributeError:
        return "glsl"

    if isinstance(language, str):
        text = language
    else:
        try:
            text = language.name
        except AttributeError:
            text = str(language)
    text = text.lower()
    if text.endswith(".glsl") or text == "glsl":
        return "glsl"
    if text.endswith(".slang") or text == "slang":
        return "slang"
    if text.endswith(".hlsl") or text == "hlsl":
        return "hlsl"
    return text


def _source_extension(language: str) -> str:
    if language == "slang":
        return "slang"
    return "glsl"


def _artifact_extension(target: str) -> str:
    if target == "vulkan":
        return "spv"
    if target == "opengl":
        return "glsl"
    raise ValueError(f"Unsupported shader target: {target}")


def _resource_type(target: str) -> str:
    if target == "vulkan":
        return "shader_spirv"
    if target == "opengl":
        return "shader_glsl"
    raise ValueError(f"Unsupported shader target: {target}")


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
        resolved = existing_executable(compiler)
        if resolved is None:
            raise FileNotFoundError(f"Shader compiler does not exist: {compiler}")
        return resolved

    found = resolve_path_tool("termin_shaderc")
    if found is not None:
        return found.resolve()

    sdk_compiler = resolve_sdk_tool("termin_shaderc", Path(__file__))
    if sdk_compiler is not None:
        return sdk_compiler.resolve()

    raise FileNotFoundError(
        "Shader compiler 'termin_shaderc' was not found. "
        "Pass shader_compiler=..., add it to PATH, or install the SDK compiler tools."
    )


def _run_shader_compiler(
    compiler: Path,
    language: str,
    target: str,
    stage: str,
    input_path: Path,
    output_path: Path,
    debug_name: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _executable_command(compiler) + [
        str(compiler),
        "compile",
        "--language",
        language,
        "--target",
        target,
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
