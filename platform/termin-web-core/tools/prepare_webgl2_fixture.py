#!/usr/bin/env python3

"""Stage canonical built-ins and compile the fixture-only WebGL2 shader."""

import argparse
import json
import pathlib
import shutil
import subprocess
import sys


def run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed with exit code {completed.returncode}: {' '.join(command)}")


def webgl2_artifacts(webgpu: dict[str, str]) -> dict[str, str]:
    return {
        stage: path.replace("shaders/webgpu/", "shaders/webgl2/").replace(".wgsl", ".glsl")
        for stage, path in webgpu.items()
    }


STAGE_EXTENSIONS = {
    "vertex": "vert",
    "fragment": "frag",
    "geometry": "geom",
    "compute": "comp",
}


def write_json(path: pathlib.Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shaderc", required=True)
    parser.add_argument("--slangc", required=True)
    parser.add_argument("--builtin-artifact-root", required=True)
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()

    fixture = pathlib.Path(args.fixture)
    shaderc = pathlib.Path(args.shaderc)
    slangc = pathlib.Path(args.slangc)
    if not shaderc.is_file():
        raise RuntimeError(f"host termin_shaderc does not exist: {shaderc}")
    if not slangc.is_file():
        raise RuntimeError(f"host slangc does not exist: {slangc}")
    builtin_artifact_root = pathlib.Path(args.builtin_artifact_root)
    artifact_manifest = builtin_artifact_root / "builtin-shader-artifacts.json"
    if not artifact_manifest.is_file():
        raise RuntimeError(f"built-in shader artifact manifest does not exist: {artifact_manifest}")
    artifact_contract = json.loads(artifact_manifest.read_text(encoding="utf-8"))
    if artifact_contract.get("schema_version") != 1:
        raise RuntimeError("built-in shader artifact manifest requires schema version 1")
    for relative in ("builtin_shaders", "shaders/webgpu", "shaders/webgl2"):
        source = builtin_artifact_root / relative
        if not source.is_dir():
            raise RuntimeError(f"built-in shader artifact directory does not exist: {source}")
        shutil.copytree(source, fixture / relative, dirs_exist_ok=True)

    builtin_source = builtin_artifact_root / "builtin_shaders"

    shader_descriptor_path = fixture / "shaders/shader-phase-3324b40c23af7090.shader.json"
    shader_descriptor = json.loads(shader_descriptor_path.read_text(encoding="utf-8"))
    output_dir = fixture / "shaders/webgl2"
    output_dir.mkdir(parents=True, exist_ok=True)
    stage_specs = {
        "vertex": (
            shader_descriptor["vertex_source_path"],
            shader_descriptor["vertex_entry"],
            "vert",
        ),
        "fragment": (
            shader_descriptor["fragment_source_path"],
            shader_descriptor["fragment_entry"],
            "frag",
        ),
    }
    compiled: dict[str, str] = {}
    for stage, (source_path, entry, extension) in stage_specs.items():
        relative_output = f"shaders/webgl2/{shader_descriptor['uuid']}.{extension}.glsl"
        output_path = fixture / relative_output
        run(
            [
                str(shaderc),
                "compile",
                "--language",
                "slang",
                "--target",
                "webgl2",
                "--stage",
                stage,
                "--entry",
                entry,
                "--input",
                str(fixture / source_path),
                "--output",
                str(output_path),
                "--slangc",
                str(slangc),
                "--include-dir",
                str(builtin_source),
                "--program-source",
                str(fixture / shader_descriptor["vertex_source_path"]),
                "--program-source",
                str(fixture / shader_descriptor["fragment_source_path"]),
            ]
        )
        compiled[stage] = relative_output
    shader_descriptor.setdefault("artifacts", {})["webgl2"] = compiled
    write_json(shader_descriptor_path, shader_descriptor)

    manifest_path = fixture / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    catalog = json.loads((builtin_source / "engine-shader-catalog.json").read_text(encoding="utf-8"))
    builtin_contract = []
    for shader in catalog["shaders"]:
        stages = shader.get("stages")
        if shader.get("language") != "slang" or not isinstance(stages, dict):
            continue
        stage_artifacts = {stage: f"shaders/webgpu/{shader['uuid']}.{STAGE_EXTENSIONS[stage]}.wgsl" for stage in stages}
        builtin_contract.append(
            {
                "uuid": shader["uuid"],
                "artifacts": {
                    "webgpu": stage_artifacts,
                    "webgl2": webgl2_artifacts(stage_artifacts),
                },
            }
        )
    manifest["builtin_shader_contract"]["catalog"] = "builtin_shaders/engine-shader-catalog.json"
    manifest["builtin_shader_contract"]["shaders"] = builtin_contract
    backends = manifest["target_requirements"]["backends"]
    if "webgl2" not in backends:
        backends.append("webgl2")
    write_json(manifest_path, manifest)
    print("Termin Web: prepared offline WebGPU/WebGL2 fixture artifacts")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Termin Web WebGL2 fixture preparation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
