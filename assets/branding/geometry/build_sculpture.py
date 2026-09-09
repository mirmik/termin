"""An all-sided T sculpture: twisted hollow beam, fork, triangular stem."""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
import subprocess
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

LOG = logging.getLogger("termin.sculpture")
ROOT = Path(__file__).resolve().parents[3]


def mesh_object(name, vertices, faces, collection):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    if mesh.validate():
        raise ValueError(f"{name}: invalid mesh")
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def hollow_crossbar(collection):
    # Triangular annulus rotates 120 degrees over the beam's length.
    # The axial tunnel is real geometry, including open ends and wall thickness.
    stations = [(-2.5, 0.64, -35), (-1.35, 0.88, -5), (0, 0.94, 25), (1.35, 0.85, 55), (2.5, 0.60, 85)]
    vertices, faces = [], []
    for x, radius, twist in stations:
        for r in (radius, radius - 0.23):
            for j in range(3):
                angle = math.radians(twist) + j * math.tau / 3
                vertices.append((x, r * math.cos(angle), 1.35 + r * math.sin(angle)))
    for station in range(len(stations) - 1):
        for j in range(3):
            k = (j + 1) % 3
            a, b = station * 6 + j, station * 6 + k
            # Alternate diagonal directions to give broad intentional facets.
            faces.extend([(a, b, b + 6), (a, b + 6, a + 6)])
            a, b = a + 3, b + 3
            faces.extend([(a, b + 6, b), (a, a + 6, b + 6)])
    for station in (0, len(stations) - 1):
        base = station * 6
        for j in range(3):
            k = (j + 1) % 3
            faces.append((base + j, base + k, base + 3 + k, base + 3 + j))
    return mesh_object("Crossbar | twisted triangular tunnel", vertices, faces, collection)


def triangular_stem(collection):
    stations = [(-2.4, 0.035, -30), (-1.95, 0.39, -10), (-0.85, 0.55, 25), (-0.10, 0.43, 65)]
    vertices, faces = [], []
    for z, radius, twist in stations:
        for j in range(3):
            angle = math.radians(twist) + j * math.tau / 3
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), z))
    for i in range(len(stations) - 1):
        for j in range(3):
            a = i * 3 + j
            b = i * 3 + (j + 1) % 3
            faces.extend([(a, b, b + 3), (a, b + 3, a + 3)])
    faces.extend([(2, 1, 0), (9, 10, 11)])
    return mesh_object("Stem | rotating triangular section", vertices, faces, collection)


def fork_arm(name, points, collection):
    vertices, faces = [], []
    for i, (center, radius) in enumerate(points):
        center = Vector(center)
        direction = Vector(points[min(i + 1, len(points) - 1)][0]) - Vector(points[max(0, i - 1)][0])
        direction.normalize()
        side = direction.cross(Vector((0, 1, 0))).normalized()
        depth = direction.cross(side).normalized()
        for j in range(3):
            a = j * math.tau / 3 + 0.3
            vertices.append(tuple(center + radius * (math.cos(a) * side + math.sin(a) * depth)))
    for i in range(len(points) - 1):
        for j in range(3):
            a = i * 3 + j
            b = i * 3 + (j + 1) % 3
            faces.extend([(a, b, b + 3), (a, b + 3, a + 3)])
    faces.extend([(2, 1, 0), tuple(range((len(points) - 1) * 3, len(points) * 3))])
    return mesh_object(name, vertices, faces, collection)


def validate(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if not all(e.is_manifold for e in bm.edges):
        raise ValueError("Sculpture has a non-manifold edge")
    if any(f.calc_area() < 1e-10 for f in bm.faces):
        raise ValueError("Sculpture has a degenerate face")
    pending = set(bm.verts)
    components = 0
    while pending:
        components += 1
        stack = [pending.pop()]
        while stack:
            current = stack.pop()
            for edge in current.link_edges:
                other = edge.other_vert(current)
                if other in pending:
                    pending.remove(other)
                    stack.append(other)
    if components != 1:
        raise ValueError(f"Sculpture is disconnected: {components} components")
    volume = bm.calc_volume(signed=False)
    report = {
        "vertices": len(bm.verts),
        "triangles": len(bm.faces),
        "connected_components": components,
        "closed_manifold": True,
        "volume": volume,
        "dimensions": list(obj.dimensions),
    }
    bm.free()
    return report


def aim(obj, target):
    forward = (Vector(target) - obj.location).normalized()
    # Camera is Z-up in the scene; use world Z as the stable up vector.
    right = forward.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(forward)
    obj.rotation_euler = Matrix((right, up, -forward)).transposed().to_euler()


def build(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    construction = bpy.data.collections.new("Construction | editable source parts")
    scene.collection.children.link(construction)
    crossbar = hollow_crossbar(construction)
    stem = triangular_stem(construction)
    left = fork_arm(
        "Fork | left", [((0, 0, -0.50), 0.30), ((-0.30, -0.09, 0.10), 0.23), ((-0.60, -0.25, 0.64), 0.10)], construction
    )
    right = fork_arm(
        "Fork | right", [((0, 0, -0.50), 0.30), ((0.32, 0.05, 0.12), 0.23), ((0.60, 0.11, 0.59), 0.10)], construction
    )
    # Exact booleans preserve the authored planes. No voxel remesh or smoothing.
    result = crossbar.copy()
    result.data = crossbar.data.copy()
    result.name = "T | volumetric sculpture"
    scene.collection.objects.link(result)
    bpy.context.view_layer.objects.active = result
    result.select_set(True)
    for part in (left, right, stem):
        modifier = result.modifiers.new("Join " + part.name, "BOOLEAN")
        modifier.operation = "UNION"
        modifier.solver = "EXACT"
        modifier.object = part
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    modifier = result.modifiers.new("Explicit triangular faces", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    construction.hide_render = True
    construction.hide_viewport = True
    bpy.context.view_layer.update()
    report = validate(result)
    (out / "mesh-report.json").write_text(json.dumps(report, indent=2) + "\n")
    positions, normals = [], []
    for polygon in result.data.polygons:
        for index in polygon.vertices:
            positions.extend(round(float(v), 6) for v in result.data.vertices[index].co)
            normals.extend(round(float(v), 6) for v in polygon.normal)
    template = Path(__file__).with_name("sculpture-viewer.html").read_text()
    payload = json.dumps({"positions": positions, "normals": normals})
    (out / "viewer.html").write_text(template.replace("__MESH__", payload))
    material = bpy.data.materials.new("Neutral grey | no emission")
    material.use_nodes = True
    material.diffuse_color = (0.32, 0.34, 0.37, 1)
    p = material.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (0.32, 0.34, 0.37, 1)
    p.inputs["Metallic"].default_value = 0.12
    p.inputs["Roughness"].default_value = 0.46
    result.data.materials.clear()
    result.data.materials.append(material)
    for polygon in result.data.polygons:
        polygon.use_smooth = False
    result["design"] = (
        "Full-volume T: 120-degree triangular tunnel twist, fork opening, 95-degree stem twist. Inspect all sides."
    )
    # Animation lives on a parent; the mesh remains in its authored coordinates.
    rig = bpy.data.objects.new("Turntable | one full rotation", None)
    scene.collection.objects.link(rig)
    result.parent = rig
    rig.rotation_euler.z = 0
    rig.keyframe_insert(data_path="rotation_euler", frame=1)
    rig.rotation_euler.z = math.tau
    rig.keyframe_insert(data_path="rotation_euler", frame=145)
    action = rig.animation_data.action
    for layer in action.layers:
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
        filepath=str(out / "t-sculpture.glb"), export_format="GLB", use_selection=True, export_animations=False
    )
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "AgX"
    scene.world.color = (0.15, 0.15, 0.15)
    camera_data = bpy.data.cameras.new("Sculpture camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, -11, 4.6)
    aim(camera, (0, 0, -0.05))
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 6.7
    scene.camera = camera
    for name, location, power, size in [
        ("Key softbox", (-4, -5, 7), 1100, 5),
        ("Side softbox", (5, -1, 3), 650, 4),
        ("Rear softbox", (1, 5, 5), 1400, 3),
    ]:
        light = bpy.data.lights.new(name, "AREA")
        light.energy = power
        light.shape = "DISK"
        light.size = size
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = location
        aim(obj, (0, 0, 0))
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -2.55))
    floor = bpy.context.object
    floor.name = "Studio floor"
    floor_mat = bpy.data.materials.new("Studio charcoal")
    floor_mat.use_nodes = True
    floor_mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.065, 0.075, 0.09, 1)
    floor.data.materials.append(floor_mat)
    reference = bpy.data.images.load(str(Path(__file__).resolve().parents[1] / "wordmarks" / "12-termin-angular.png"))
    reference.pack()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
                area.spaces.active.shading.type = "MATERIAL"
    bpy.ops.object.select_all(action="DESELECT")
    result.select_set(True)
    bpy.context.view_layer.objects.active = result
    scene["README"] = (
        "Rotate the actual mesh freely. Neutral grey material has no emission. Construction collection contains original editable pieces. Timeline 1-144 = 360 degrees in 6 seconds."
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "t-sculpture.blend"))
    for name, frame in [("front", 1), ("quarter", 19), ("side", 37), ("rear", 73)]:
        scene.frame_set(frame)
        scene.render.filepath = str(out / f"{name}.png")
        bpy.ops.render.render(write_still=True)
    if args.animate:
        scene.render.resolution_x = 640
        scene.render.resolution_y = 640
        scene.cycles.samples = 12
        frames = out / "frames"
        frames.mkdir(exist_ok=True)
        for index, frame in enumerate(range(1, 145, 2)):
            scene.frame_set(frame)
            scene.render.filepath = str(frames / f"{index:04d}.png")
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
    LOG.info("Finished volumetric T: %s", report)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "build/branding/t-sculpture")
    parser.add_argument("--animate", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    try:
        build(args)
    except Exception:
        LOG.exception("Volumetric T build failed")
        raise
