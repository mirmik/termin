"""Build the angular TERMIN logo as editable, closed, faceted Blender meshes."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import logging
from pathlib import Path
import subprocess
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon

LOG = logging.getLogger("termin.branding")
ROOT = Path(__file__).resolve().parents[3]

# Hand-traced silhouettes in the reference's 2048 x 683 display coordinates.
# Each patch is a simple polygon. Shared coordinates are welded; the R's patches
# describe its counter explicitly, without hidden geometry across the opening.
GLYPHS = {
    "T": (
        [
            [(287, 205), a, b]
            for a, b in zip(
                [
                    (60, 226),
                    (149, 154),
                    (484, 154),
                    (430, 265),
                    (338, 267),
                    (338, 451),
                    (271, 534),
                    (210, 454),
                    (210, 272),
                ],
                [
                    (149, 154),
                    (484, 154),
                    (430, 265),
                    (338, 267),
                    (338, 451),
                    (271, 534),
                    (210, 454),
                    (210, 272),
                    (60, 226),
                ],
            )
        ],
        [],
    ),
    "E": (
        [[(513, 154), (774, 154), (584, 236), (614, 278), (740, 307), (536, 365), (773, 480), (511, 499)]],
        [(553, 210, 0.34), (558, 302, 0.4), (556, 428, 0.32)],
    ),
    "R": (
        [
            [(800, 154), (993, 155), (1054, 220), (999, 234), (873, 207)],
            [(1054, 220), (1054, 331), (996, 291), (999, 234)],
            [(1054, 331), (1000, 360), (871, 311), (996, 291)],
            [(800, 154), (873, 207), (871, 311), (870, 358), (869, 451), (801, 505)],
            [(871, 311), (1000, 360), (1086, 508), (944, 450), (870, 358)],
        ],
        [(836, 289, 0.35), (961, 189, 0.26), (1027, 275, 0.3), (956, 397, 0.4)],
    ),
    "M": (
        [
            [
                (1116, 145),
                (1270, 276),
                (1430, 145),
                (1430, 502),
                (1360, 451),
                (1360, 289),
                (1270, 405),
                (1180, 280),
                (1197, 445),
                (1116, 502),
            ]
        ],
        [(1150, 289, 0.33), (1270, 326, 0.38), (1392, 283, 0.38)],
    ),
    "I": ([[(1500, 155), (1586, 145), (1586, 438), (1548, 512)]], [(1530, 190, 0.28), (1540, 392, 0.3)]),
    "N": (
        [[(1652, 145), (1852, 304), (1840, 181), (1930, 145), (1930, 503), (1715, 278), (1734, 446), (1652, 503)]],
        [(1685, 260, 0.28), (1786, 331, 0.42), (1884, 312, 0.3)],
    ),
}


def signed_area(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def make_glyph(letter, patches, ridges, body_material, edge_material):
    points, lookup, triangles = [], {}, []

    def vertex(p):
        key = tuple(p[:2])
        if key not in lookup:
            lookup[key] = len(points)
            points.append([p[0], p[1], 0.035])
        return lookup[key]

    for patch in patches:
        ids = [vertex(p) for p in patch]
        vectors = [Vector((points[i][0], points[i][1], 0)) for i in ids]
        for tri in tessellate_polygon([vectors]):
            triangles.append(tuple(ids[index] for index in tri))
    if letter == "T":
        points[lookup[(287, 205)]][2] = 0.48
        points[lookup[(271, 534)]][2] = 0.22
    # Insert designed ridge vertices into the planar triangulation, including
    # shared-edge splits. The topology stays welded before elevation into 3D.
    for x, y, depth in ridges:
        containing = []
        for index, tri in enumerate(triangles):
            a, b, c = (points[i] for i in tri)
            area = signed_area(a, b, c)
            weights = [
                signed_area((x, y), b, c) / area,
                signed_area(a, (x, y), c) / area,
                signed_area(a, b, (x, y)) / area,
            ]
            if min(weights) >= -1e-7:
                containing.append((index, tri, weights))
        if not containing:
            raise ValueError(f"{letter}: ridge outside silhouette: {(x, y)}")
        new = vertex((x, y))
        points[new][2] = depth
        additions = []
        for _, tri, _ in containing:
            for a, b in zip(tri, tri[1:] + tri[:1]):
                if abs(signed_area(points[a], points[b], (x, y))) > 1e-6:
                    additions.append((a, b, new))
        remove = {item[0] for item in containing}
        triangles = [tri for i, tri in enumerate(triangles) if i not in remove] + additions
    verts = [((x - 1024) / 100, (340 - y) / 100, z) for x, y, z in points]
    front = []
    for a, b, c in triangles:
        if (Vector(verts[b]) - Vector(verts[a])).cross(Vector(verts[c]) - Vector(verts[a])).z < 0:
            b, c = c, b
        front.append((a, b, c))
    counts = Counter(tuple(sorted((a, b))) for tri in front for a, b in zip(tri, tri[1:] + tri[:1]))
    if max(counts.values()) > 2:
        raise ValueError(f"{letter}: overlapping patch edges")
    n = len(verts)
    verts += [(x, y, -0.22) for x, y, z in verts]
    faces = front + [tuple(i + n for i in reversed(tri)) for tri in front]
    boundary = []
    for tri in front:
        for a, b in zip(tri, tri[1:] + tri[:1]):
            if counts[tuple(sorted((a, b)))] == 1:
                faces.extend([(b, a, a + n), (b, a + n, b + n)])
                boundary.append((a, b))
    mesh = bpy.data.meshes.new(f"{letter}_triangular_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    if mesh.validate():
        raise ValueError(f"{letter}: Blender repaired invalid geometry")
    if any(p.area < 1e-9 for p in mesh.polygons):
        raise ValueError(f"{letter}: degenerate triangle")
    edge_counts = Counter(tuple(sorted((a, b))) for face in faces for a, b in zip(face, face[1:] + face[:1]))
    if set(edge_counts.values()) != {2}:
        raise ValueError(f"{letter}: mesh is not closed/manifold")
    obj = bpy.data.objects.new(f"TERMIN_{letter}", mesh)
    bpy.context.collection.objects.link(obj)
    obj["source"] = "Hand-traced angular reference; authored triangular relief"
    obj["front_triangles"] = len(front)
    obj.data.materials.append(body_material)
    # Only silhouette and strong fold edges glow: no indiscriminate wireframe.
    normals = [Vector(mesh.polygons[i].normal) for i in range(len(front))]
    adjacency = {}
    for index, tri in enumerate(front):
        for a, b in zip(tri, tri[1:] + tri[:1]):
            adjacency.setdefault(tuple(sorted((a, b))), []).append(index)
    curve = bpy.data.curves.new(f"{letter}_structural_light", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.007
    curve.bevel_resolution = 0
    curve.resolution_u = 1
    for (a, b), adjacent in adjacency.items():
        if len(adjacent) == 2 and normals[adjacent[0]].dot(normals[adjacent[1]]) > 0.65:
            continue
        spline = curve.splines.new("POLY")
        spline.points.add(1)
        for point, idx in zip(spline.points, (a, b)):
            x, y, z = verts[idx]
            point.co = (x, y, z + 0.008, 1)
    edge_obj = bpy.data.objects.new(f"{letter}_edge_light", curve)
    bpy.context.collection.objects.link(edge_obj)
    curve.materials.append(edge_material)
    return obj, edge_obj


def shader(name, edge=False):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (0.015, 0.48, 0.72, 1)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()

    def node(kind, name, x, y):
        n = nodes.new(kind)
        n.label = name
        n.location = (x, y)
        return n

    output = node("ShaderNodeOutputMaterial", "Surface", 850, 120)
    bsdf = node("ShaderNodeBsdfPrincipled", "Faceted cyan", 590, 120)
    bsdf.inputs["Base Color"].default_value = (0.008, 0.20, 0.34, 1)
    bsdf.inputs["Metallic"].default_value = 0.55
    bsdf.inputs["Roughness"].default_value = 0.32
    bsdf.inputs["Emission Color"].default_value = (0.025, 0.68, 1, 1)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    geometry = node("ShaderNodeNewGeometry", "World position", -850, 200)
    xyz = node("ShaderNodeSeparateXYZ", "Scan direction", -660, 200)
    links.new(geometry.outputs["Position"], xyz.inputs[0])
    spatial = node("ShaderNodeMath", "Spatial frequency", -470, 220)
    spatial.operation = "MULTIPLY"
    spatial.inputs[1].default_value = 0.60
    links.new(xyz.outputs["X"], spatial.inputs[0])
    time = node("ShaderNodeValue", "Loop phase (96 frames)", -660, -100)
    time.outputs[0].driver_add("default_value").driver.expression = "(frame-1)*2*pi/96"
    phase = node("ShaderNodeMath", "Travelling phase", -260, 200)
    phase.operation = "SUBTRACT"
    links.new(spatial.outputs[0], phase.inputs[0])
    links.new(time.outputs[0], phase.inputs[1])
    sine = node("ShaderNodeMath", "Smooth light wave", -80, 200)
    sine.operation = "SINE"
    links.new(phase.outputs[0], sine.inputs[0])
    positive = node("ShaderNodeMath", "Positive crest", 100, 200)
    positive.operation = "MAXIMUM"
    positive.inputs[1].default_value = 0
    links.new(sine.outputs[0], positive.inputs[0])
    narrow = node("ShaderNodeMath", "Broad soft pulse", 260, 200)
    narrow.operation = "POWER"
    narrow.inputs[1].default_value = 8
    links.new(positive.outputs[0], narrow.inputs[0])
    strength = node("ShaderNodeMath", "Base glow + moving highlight", 420, -80)
    strength.operation = "MULTIPLY_ADD"
    strength.inputs[1].default_value = 2.4 if edge else 0.95
    strength.inputs[2].default_value = 1.8 if edge else 0.045
    links.new(narrow.outputs[0], strength.inputs[0])
    links.new(strength.outputs[0], bsdf.inputs["Emission Strength"])
    return material


def aim(obj, target):
    forward = (Vector(target) - obj.location).normalized()
    right = forward.cross(Vector((0, 1, 0))).normalized()
    up = right.cross(forward)
    obj.rotation_euler = Matrix((right, up, -forward)).transposed().to_euler()


def build(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    body_material = shader("TERMIN | animated planar cyan")
    edge_material = shader("TERMIN | structural edge light", True)
    letters = []
    edges = []
    for name, (patches, ridges) in GLYPHS.items():
        body, edge = make_glyph(name, patches, ridges, body_material, edge_material)
        letters.append(body)
        edges.append(edge)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 96
    scene.render.fps = 24
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.world.color = (0.006, 0.009, 0.016)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    camera_data = bpy.data.cameras.new("Wordmark orthographic camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (-0.25, 0, 24)
    aim(camera, (-0.25, 0, 0))
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 21.8
    scene.camera = camera
    for name, location, power, color, size in [
        ("Key cyan", (-5, 5, 8), 1500, (0.25, 0.85, 1), 8),
        ("Cool fill", (7, -2, 5), 850, (0.08, 0.35, 1), 6),
        ("Top white", (0, 7, 3), 1000, (0.65, 0.95, 1), 7),
    ]:
        data = bpy.data.lights.new(name, "AREA")
        data.energy = power
        data.color = color
        data.shape = "DISK"
        data.size = size
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = location
        aim(obj, (0, 0, 0))
    # Opaque navy backdrop, physically separate from the six letter meshes.
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -1))
    backdrop = bpy.context.object
    backdrop.name = "Backdrop (not exported)"
    mat = bpy.data.materials.new("Midnight background")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.remove(nodes.get("Principled BSDF"))
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (0.0006, 0.0015, 0.004, 1)
    mat.node_tree.links.new(emission.outputs[0], nodes.get("Material Output").inputs["Surface"])
    backdrop.data.materials.append(mat)
    # Pack the reference into the blend for manual Edit Mode refinement.
    reference = bpy.data.images.load(str(Path(__file__).resolve().parents[1] / "wordmarks" / "12-termin-angular.png"))
    reference.pack()
    scene["README"] = (
        "Six closed hand-traced letter meshes, flat triangular faces. Shader loop: frames 1-96 at 24fps. GLB exports static PBR; procedural nodes stay in this blend."
    )
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.shading.type = "MATERIAL"
    # Export with conventional static PBR materials, retaining the original
    # procedural shader in the blend. Blender node graphs are not glTF shaders.
    static = bpy.data.materials.new("TERMIN static cyan")
    static.use_nodes = True
    p = static.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (0.008, 0.26, 0.44, 1)
    p.inputs["Metallic"].default_value = 0.55
    p.inputs["Roughness"].default_value = 0.32
    p.inputs["Emission Color"].default_value = (0.01, 0.25, 0.4, 1)
    p.inputs["Emission Strength"].default_value = 0.3
    bpy.ops.object.select_all(action="DESELECT")
    for obj in letters:
        obj.select_set(True)
        obj.data.materials[0] = static
    bpy.context.view_layer.objects.active = letters[0]
    bpy.ops.export_scene.gltf(
        filepath=str(out / "termin-angular.glb"),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
    )
    for obj in letters:
        obj.data.materials[0] = body_material
    scene.frame_set(25)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "termin-angular.blend"))
    report = {
        "letters": {
            obj.name: {"vertices": len(obj.data.vertices), "triangles": len(obj.data.polygons), "closed_manifold": True}
            for obj in letters
        },
        "loop_frames": 96,
        "fps": 24,
        "reference": "assets/branding/wordmarks/12-termin-angular.png",
    }
    (out / "mesh-report.json").write_text(json.dumps(report, indent=2) + "\n")
    scene.render.filepath = str(out / "preview.png")
    bpy.ops.render.render(write_still=True)
    # An oblique second view documents actual volume and the rear/side walls.
    camera.location = (4, -4, 22)
    aim(camera, (-0.25, 0, 0))
    scene.render.filepath = str(out / "preview-oblique.png")
    bpy.ops.render.render(write_still=True)
    camera.location = (-0.25, 0, 24)
    aim(camera, (-0.25, 0, 0))
    if args.animate:
        scene.render.resolution_x = 960
        scene.render.resolution_y = 320
        scene.cycles.samples = 8
        frames = out / "frames"
        frames.mkdir(exist_ok=True)
        for i, frame in enumerate(range(1, 97, 2)):
            scene.frame_set(frame)
            scene.render.filepath = str(frames / f"{i:04d}.png")
            bpy.ops.render.render(write_still=True)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-framerate",
                "12",
                "-i",
                str(frames / "%04d.png"),
                "-frames:v",
                "48",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(out / "shimmer.mp4"),
            ],
            check=True,
        )
    LOG.info("Created blend, GLB, previews and mesh report in %s", out)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "build/branding/termin-wordmark")
    parser.add_argument("--animate", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    try:
        build(args)
    except Exception:
        LOG.exception("TERMIN logo build failed")
        raise
