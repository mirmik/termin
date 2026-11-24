"""Package the lit web scenes using the web fixture's default pipeline and engine shaders."""

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from demo_scenes import physics_entities, studio_entities


EXAMPLE = Path(__file__).resolve().parent
BLOB_WRITER = EXAMPLE.parents[3] / "editor/termin-project-build/python/termin/project_build/runtime_package_blob.py"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")


def add_resource(directory, manifest, kind, path, data):
    write(directory / path, data)
    manifest["resources"].append({"type": kind, "uuid": data["uuid"], "path": path})


def compile_stages(directory, shader, args):
    for target, suffix in (("webgpu", "wgsl"), ("webgl2", "glsl")):
        stages = {}
        for stage in ("vertex", "fragment"):
            stage_suffix = "vert" if stage == "vertex" else "frag"
            path = Path("shaders") / target / f"{shader['uuid']}.{stage_suffix}.{suffix}"
            command = [
                args.shaderc, "compile", "--language", "slang", "--target", target, "--stage", stage,
                "--entry", shader[f"{stage}_entry"], "--input", directory / shader[f"{stage}_source_path"], "--output", directory / path,
                "--slangc", args.slangc, "-I", directory / "builtin_shaders",
                "--program-source", directory / shader["vertex_source_path"],
                "--program-source", directory / shader["fragment_source_path"],
            ]
            if target == "webgpu":
                command.extend(["--wgsl-validator", args.wgsl_validator])
            subprocess.run(command, check=True)
            stages[stage] = path.as_posix()
        shader["artifacts"][target] = stages


def build_shader(directory, manifest, args):
    # Stable phase UUID for the interactive-lit program and its opaque pass.
    shader = {
        "uuid": "shader-phase-96a0186326cade95", "name": "Demo lighting", "language": "slang", "features": 1,
        "artifact_role": "executable", "artifacts": {}, "source_path": "shaders/lit.frag.slang",
    }
    digest = hashlib.sha256()
    for stage, extension in (("vertex", "vert"), ("fragment", "frag")):
        filename = f"lit.{extension}.slang"
        path = Path("shaders") / filename
        shutil.copyfile(EXAMPLE / filename, directory / path)
        digest.update((EXAMPLE / filename).read_bytes())
        shader[f"{stage}_source_path"] = path.as_posix()
        shader[f"{stage}_entry"] = "main"
    shader["source_identity"] = "sha256:" + digest.hexdigest()
    compile_stages(directory, shader, args)
    path = "shaders/interactive-lit.shader.json"
    add_resource(directory, manifest, "shader", path, shader)
    manifest["pipeline_shader_requirements"][0]["variants"] = [
        {key: shader[key] for key in ("uuid", "name", "source_identity")} | {"path": path}
    ]
    program = read(args.fixture / "shaders/web-render-fixture-textured-shader.shader-program.json")
    program.update(uuid="interactive-lit", name="Interactive lights", features=1, source_path=shader["source_path"],
                   properties=[{"name": "u_emission", "label": "Lamp color", "property_type": "Vec4",
                                "default": [0, 0, 0, 0]}])
    program["phases"][0]["shader"] = shader["uuid"]
    add_resource(directory, manifest, "shader_program", "shaders/interactive-lit.shader-program.json", program)
    for name, emission in (("porcelain", [0, 0, 0, 0]), ("amber", [1, 0.34, 0.05, 1]), ("cyan", [0.03, 0.65, 1, 1])):
        material = {
            "uuid": name, "name": name, "shader_program": program["uuid"],
            "phases": [{"mark": "opaque", "shader": shader["uuid"], "priority": 0}],
            "uniforms": {"u_emission": emission}, "textures": {},
        }
        add_resource(directory, manifest, "material", f"materials/{name}.tmat.json", material)


def build_shadow_casters(directory, manifest, args):
    # The ball's material participates in the shadow phase of the framegraph.
    source = "builtin_shaders/termin-engine-shadow-material.slang"
    caster = {
        "uuid": "shader-phase-9bdcb8d5ea79ea16", "name": "Demo lighting/shadow", "language": "slang",
        "source_path": source, "features": 0, "artifact_role": "executable", "artifacts": {},
        "source_identity": "sha256:" + hashlib.sha256((directory / source).read_bytes()).hexdigest(),
        "vertex_source_path": source, "vertex_entry": "vs_main",
        "fragment_source_path": source, "fragment_entry": "fs_main",
    }
    compile_stages(directory, caster, args)
    add_resource(directory, manifest, "shader", "shaders/demo-shadow.shader.json", caster)
    program_path = directory / "shaders/interactive-lit.shader-program.json"
    program = read(program_path)
    program["phases"].append({
        "phase_mark": "shadow", "priority": 0, "shader": caster["uuid"],
        "state": program["phases"][0]["state"] | {"cull": True},
    })
    write(program_path, program)
    material_path = directory / "materials/amber.tmat.json"
    material = read(material_path)
    material["phases"].append({"mark": "shadow", "priority": 0, "shader": caster["uuid"]})
    write(material_path, material)

    # Static-mesh variants from the Default pipeline's shader usage collector.
    # The scene exporter records both the pass shader and the planned mesh draw.
    vertex = "shaders/static-shadow.vert.slang"
    shutil.copyfile(EXAMPLE / "static-shadow.vert.slang", directory / vertex)
    fragment = "builtin_shaders/termin-engine-shadow.slang"
    for variant in read(EXAMPLE / "static-shadow.variants.json"):
        shader = {
            **variant, "artifact_role": "pipeline_variant", "language": "slang",
            "source_path": "runtime-registry", "features": 0, "artifacts": {},
            "vertex_source_path": vertex, "vertex_entry": "vs_main",
            "fragment_source_path": fragment, "fragment_entry": "fs_main",
        }
        compile_stages(directory, shader, args)
        path = f"shaders/{shader['uuid']}.shader.json"
        write(directory / path, shader)
        manifest["pipeline_shader_requirements"][0]["variants"].append(
            {key: shader[key] for key in ("uuid", "name", "source_identity")} | {"path": path}
        )


def build_meshes(directory, manifest, fixture):
    cube = read(fixture / "meshes/web-render-fixture-mesh-resource.tmesh.json")
    cube.update(uuid="cube", name="Cube")
    add_resource(directory, manifest, "mesh", "meshes/cube.tmesh.json", cube)
    vertices = []
    indices = []
    rings, slices = 36, 60
    for i in range(rings + 1):
        theta = math.pi * i / rings
        for j in range(slices + 1):
            phi = 2 * math.pi * j / slices
            normal = [round(c, 6) for c in (math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi), math.cos(theta))]
            vertices.extend([*normal, *normal, j / slices, i / rings, 0, 0, 0, 1])
    for i in range(rings):
        for j in range(slices):
            a = i * (slices + 1) + j
            b = a + slices + 1
            indices.extend([a, b, b + 1, a, b + 1, a + 1])
    sphere = cube | {"uuid": "sphere", "name": "Sphere", "vertices": vertices, "indices": indices,
                     "vertex_count": len(vertices) // 12,
                     "submeshes": [cube["submeshes"][0] | {"name": "Sphere", "index_count": len(indices)}]}
    add_resource(directory, manifest, "mesh", "meshes/sphere.tmesh.json", sphere)


def build_scene(directory, fixture, make_entities):
    scene = read(fixture / "scenes/Main.scene.json")
    camera = next(entity for entity in scene["entities"] if entity["name"] == "Main Camera")
    scene["entities"] = make_entities(camera)
    scene["extensions"]["render_state"]["lighting"].update(ambient_color=[.62, .69, .8], ambient_intensity=.085)
    write(directory / "scenes/Main.scene.json", scene)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("fixture", "shaderc", "slangc", "wgsl-validator", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--physics-output", type=Path, help="also package the rigid-body demo")
    args = parser.parse_args()
    manifest = read(args.fixture / "manifest.json")
    manifest["resources"] = []
    with tempfile.TemporaryDirectory(prefix="termin-interactive-scene-") as temporary:
        directory = Path(temporary)
        for subdir in ("builtin_shaders", "shaders/webgpu", "shaders/webgl2"):
            shutil.copytree(args.fixture / subdir, directory / subdir, ignore=shutil.ignore_patterns("shader-phase-*"))
        build_shader(directory, manifest, args)
        build_meshes(directory, manifest, args.fixture)
        write(directory / "manifest.json", manifest)
        build_scene(directory, args.fixture, studio_entities)
        subprocess.run([sys.executable, BLOB_WRITER, directory, args.output], check=True)
        if args.physics_output:
            build_shadow_casters(directory, manifest, args)
            write(directory / "manifest.json", manifest)
            build_scene(directory, args.fixture, physics_entities)
            subprocess.run([sys.executable, BLOB_WRITER, directory, args.physics_output], check=True)


if __name__ == "__main__":
    main()
