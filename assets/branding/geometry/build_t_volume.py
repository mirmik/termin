"""Preserve the original relief T front exactly, author a faceted rear volume."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import logging
import math
from pathlib import Path
import subprocess
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_logo import GLYPHS, make_glyph
from build_sculpture import aim, validate

LOG = logging.getLogger("termin.t-volume")
ROOT = HERE.parents[2]


def build(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    grey = bpy.data.materials.new("Satin grey | form study")
    grey.use_nodes = True
    grey.diffuse_color = (0.32, 0.35, 0.39, 1)
    bsdf = grey.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.32, 0.35, 0.39, 1)
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Metallic"].default_value = 0.15
    original, edge = make_glyph("T", *GLYPHS["T"], grey, grey)
    bpy.data.objects.remove(edge, do_unlink=True)
    front_count = original["front_triangles"]
    front_faces = [tuple(p.vertices) for p in original.data.polygons[:front_count]]
    n = len(original.data.vertices) // 2
    front = [tuple(v.co) for v in original.data.vertices[:n]]
    # The interior fan hub is the approved front's fold junction.
    hub = front[0]
    counts = Counter(tuple(sorted((a, b))) for tri in front_faces for a, b in zip(tri, tri[1:] + tri[:1]))
    boundary = []
    for tri in front_faces:
        for a, b in zip(tri, tri[1:] + tri[:1]):
            if counts[tuple(sorted((a, b)))] == 1:
                boundary.append((a, b))
    interior = set(range(n)) - {i for pair in boundary for i in pair}
    assert interior == {0}, "Original T triangulation changed: review the rear design"
    # A contracted rear contour stays strictly inside the original front
    # silhouette. The folded rear fan reaches 1.6 units behind the face.
    rear = []
    for i, (x, y, z) in enumerate(front):
        rx = hub[0] + 0.86 * (x - hub[0])
        ry = hub[1] + 0.86 * (y - hub[1])
        height = (y + 1.94) / 3.8
        depth = 0.45 + 0.40 * height + 0.12 * (x - hub[0]) / 4.24
        rear.append((rx, ry, -1.6 if i in interior else -depth))
    vertices = front + rear
    faces = front_faces + [tuple(i + n for i in reversed(tri)) for tri in front_faces]
    for a, b in boundary:
        faces.extend([(b, a, a + n), (b, a + n, b + n)])
    assert vertices[:n] == front and faces[:front_count] == front_faces
    # Rigid coordinate transform only: x right, z up, front towards -Y.
    cx = (min(v[0] for v in front) + max(v[0] for v in front)) / 2
    cy = (min(v[1] for v in front) + max(v[1] for v in front)) / 2

    def orient(v):
        return (v[0] - cx, -v[2], v[1] - cy)

    new_mesh = bpy.data.meshes.new("Original T front + folded rear")
    new_mesh.from_pydata([orient(v) for v in vertices], [], faces)
    new_mesh.update()
    if new_mesh.validate():
        raise ValueError("Blender repaired invalid geometry")
    result = bpy.data.objects.new("T | original front, volumetric rear", new_mesh)
    scene.collection.objects.link(result)
    result.data.materials.append(grey)
    for v in original.data.vertices:
        v.co = orient(v.co)
    original.data.update()
    original.name = "Reference | original relief T"
    original.hide_render = True
    original.hide_set(True)
    bpy.context.view_layer.update()
    report = validate(result)
    front_error = max((result.data.vertices[i].co - original.data.vertices[i].co).length for i in range(n))
    assert front_error == 0.0
    report.update(
        front_max_vertex_delta=front_error,
        front_triangles=front_count,
        source="build_logo.py: GLYPHS[T] and make_glyph",
        rear_contraction=0.86,
    )
    (out / "mesh-report.json").write_text(json.dumps(report, indent=2) + "\n")
    result["front_preservation"] = (
        "Front vertices and triangle indices match the original relief T exactly; only a rigid coordinate transform is applied."
    )
    # Save an independent offline rotatable view of exactly this mesh.
    positions = []
    normals = []
    for polygon in result.data.polygons:
        for i in polygon.vertices:
            positions.extend(round(float(v), 6) for v in result.data.vertices[i].co)
            normals.extend(round(float(v), 6) for v in polygon.normal)
    template = (HERE / "sculpture-viewer.html").read_text()
    template = template.replace("let yaw=.45,pitch=0,distance=13", "let yaw=.45,pitch=0,distance=11")
    (out / "viewer.html").write_text(
        template.replace("__MESH__", json.dumps(dict(positions=positions, normals=normals)))
    )
    rig = bpy.data.objects.new("Turntable", None)
    scene.collection.objects.link(rig)
    result.parent = rig
    rig.rotation_euler.z = 0
    rig.keyframe_insert(data_path="rotation_euler", frame=1)
    rig.rotation_euler.z = math.tau
    rig.keyframe_insert(data_path="rotation_euler", frame=145)
    for layer in rig.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = "LINEAR"
    scene.frame_start = 1
    scene.frame_end = 144
    scene.render.fps = 24
    scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    result.select_set(True)
    bpy.context.view_layer.objects.active = result
    bpy.ops.export_scene.gltf(
        filepath=str(out / "t-volume.glb"), export_format="GLB", use_selection=True, export_animations=False
    )
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.world.color = (0.10, 0.10, 0.10)
    data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (0, -12, 0)
    aim(camera, (0, 0, 0))
    data.type = "ORTHO"
    data.ortho_scale = 5.8
    for name, location, power, size in [
        ("Key", (-4, -5, 7), 1100, 5),
        ("Fill", (5, -2, 2), 650, 4),
        ("Rear", (2, 5, 5), 1300, 3),
    ]:
        light = bpy.data.lights.new(name, "AREA")
        light.energy = power
        light.shape = "DISK"
        light.size = size
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = location
        aim(obj, (0, 0, 0))
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -2.15))
    floor = bpy.context.object
    floor.name = "Studio floor"
    mat = bpy.data.materials.new("Charcoal")
    mat.use_nodes = True
    mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.04, 0.05, 0.065, 1)
    floor.data.materials.append(mat)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.shading.type = "MATERIAL"
    bpy.ops.object.select_all(action="DESELECT")
    result.select_set(True)
    bpy.context.view_layer.objects.active = result
    scene["README"] = (
        "Original relief T front preserved exactly. Only rear and side faces are new. Hidden Reference object is the original thin T. Neutral grey, 6-second turntable."
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "t-volume.blend"))
    result.hide_render = True
    original.hide_render = False
    scene.render.filepath = str(out / "original-front.png")
    bpy.ops.render.render(write_still=True)
    result.hide_render = False
    original.hide_render = True
    scene.render.filepath = str(out / "front.png")
    bpy.ops.render.render(write_still=True)
    camera.location = (0, -12, 2.5)
    aim(camera, (0, 0, 0))
    for name, frame in [("quarter", 19), ("side", 37), ("rear", 73)]:
        scene.frame_set(frame)
        scene.render.filepath = str(out / f"{name}.png")
        bpy.ops.render.render(write_still=True)
    if args.animate:
        scene.render.resolution_x = 600
        scene.render.resolution_y = 600
        scene.cycles.samples = 12
        frames = out / "frames"
        frames.mkdir(exist_ok=True)
        for i, frame in enumerate(range(1, 145, 2)):
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
                "72",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(out / "turntable.mp4"),
            ],
            check=True,
        )
    LOG.info("Original front preserved; volumetric back complete: %s", report)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "build/branding/t-volume")
    parser.add_argument("--animate", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    try:
        build(args)
    except Exception:
        LOG.exception("Original T volume build failed")
        raise
