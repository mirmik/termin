"""Build the two-lamp demo using the web fixture's default pipeline and engine shaders."""

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


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


def build_shader(directory, manifest, args):
    # Stable phase UUID for the interactive-lit program and its opaque pass.
    shader = {
        "uuid": "shader-phase-96a0186326cade95", "name": "Point lighting", "language": "slang", "features": 1,
        "artifact_role": "executable", "artifacts": {}, "source_path": "shaders/lit.frag.slang",
    }
    sources = {}
    digest = hashlib.sha256()
    for stage, extension in (("vertex", "vert"), ("fragment", "frag")):
        filename = f"lit.{extension}.slang"
        path = Path("shaders") / filename
        shutil.copyfile(EXAMPLE / filename, directory / path)
        digest.update((EXAMPLE / filename).read_bytes())
        sources[stage] = directory / path
        shader[f"{stage}_source_path"] = path.as_posix()
        shader[f"{stage}_entry"] = "main"
    shader["source_identity"] = "sha256:" + digest.hexdigest()
    for target, suffix in (("webgpu", "wgsl"), ("webgl2", "glsl")):
        stages = {}
        for stage, source in sources.items():
            stage_suffix = "vert" if stage == "vertex" else "frag"
            path = Path("shaders") / target / f"{shader['uuid']}.{stage_suffix}.{suffix}"
            command = [
                args.shaderc, "compile", "--language", "slang", "--target", target, "--stage", stage,
                "--entry", "main", "--input", source, "--output", directory / path,
                "--slangc", args.slangc, "-I", directory / "builtin_shaders",
                "--program-source", sources["vertex"], "--program-source", sources["fragment"],
            ]
            if target == "webgpu":
                command.extend(["--wgsl-validator", args.wgsl_validator])
            subprocess.run(command, check=True)
            stages[stage] = path.as_posix()
        shader["artifacts"][target] = stages
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


def object_entity(uuid, mesh, material, position, scale):
    return {
        "uuid": uuid, "name": uuid, "pose": {"position": position, "rotation": [0, 0, 0, 1]}, "scale": scale,
        "components": [
            {"type": "MeshComponent", "data": {"mesh": {"uuid": mesh, "type": "uuid", "kind": "tc_mesh"}}},
            {"type": "MeshRenderer", "data": {"cast_shadow": False, "material": {
                "uuid": material, "type": "uuid", "kind": "tc_material"}}},
        ],
    }


def build_scene(directory, fixture):
    scene = read(fixture / "scenes/Main.scene.json")
    camera = next(entity for entity in scene["entities"] if entity["name"] == "Main Camera")
    camera["pose"]["position"] = [0, -5.5, 0]
    orbit = next(c for c in camera["components"] if c["type"] == "OrbitCameraController")
    orbit["data"]["radius"] = 5.5
    entities = [camera, object_entity("porcelain-sphere", "sphere", "porcelain", [0, 0, 0], [.87] * 3),
                object_entity("plinth", "cube", "porcelain", [0, 0, -.98], [1.65, 1.1, .14])]
    for name, x, rgb in (("amber", -1.06, [1, .25, .045]), ("cyan", 1.06, [.035, .46, 1])):
        lamp = object_entity(f"lamp-{name}", "sphere", name, [x, -.65, .18], [.23] * 3)
        lamp["components"].append({"type": "LightComponent", "data": {
            "light_type": "point", "color": rgb, "intensity": 1.65, "shadows_enabled": False,
        }})
        entities.extend([lamp, object_entity(f"stem-{name}", "cube", "porcelain",
                                             [x, -.65, -.44], [.085, .085, .50])])
    scene["entities"] = entities
    scene["extensions"]["render_state"]["lighting"].update(ambient_color=[.62, .69, .8], ambient_intensity=.085)
    write(directory / "scenes/Main.scene.json", scene)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("fixture", "shaderc", "slangc", "wgsl-validator", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    manifest = read(args.fixture / "manifest.json")
    manifest["resources"] = []
    with tempfile.TemporaryDirectory(prefix="termin-interactive-scene-") as temporary:
        directory = Path(temporary)
        for subdir in ("builtin_shaders", "shaders/webgpu", "shaders/webgl2"):
            shutil.copytree(args.fixture / subdir, directory / subdir, ignore=shutil.ignore_patterns("shader-phase-*"))
        build_shader(directory, manifest, args)
        build_meshes(directory, manifest, args.fixture)
        build_scene(directory, args.fixture)
        write(directory / "manifest.json", manifest)
        subprocess.run([sys.executable, BLOB_WRITER, directory, args.output], check=True)


if __name__ == "__main__":
    main()
