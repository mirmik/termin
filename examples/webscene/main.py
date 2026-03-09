#!/usr/bin/env python3
"""
Minimal example: termin scene → three.js web visualization.

Builds a 3D scene using termin Scene/Entity/MeshComponent,
extracts mesh data, and serves it as a web page via three.js.

Usage:
    python main.py
    # Open http://localhost:8000 in browser
"""

import json
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

from termin.visualization.core.scene import Scene
from termin.visualization.core.entity import Entity
from termin.mesh import TcMesh, MeshComponent
from termin.mesh.primitives import (
    CubeMesh,
    UVSphereMesh,
    CylinderMesh,
    TorusMesh,
    ConeMesh,
)
from termin.geombase import Pose3


STATIC_DIR = Path(__file__).parent / "static"
HOST = "0.0.0.0"
PORT = 8000

# Per-entity colors (MeshComponent has no material, so we store separately)
ENTITY_COLORS = {}


def add_mesh_entity(scene, name, mesh3, pose, color):
    """Create entity with MeshComponent and add to scene."""
    entity = Entity(pose=pose, name=name)
    mc = MeshComponent()
    mc.mesh = TcMesh.from_mesh3(mesh3, name)
    entity.add_component(mc)
    scene.add(entity)
    ENTITY_COLORS[name] = color
    return entity


def build_scene() -> Scene:
    """Build a termin scene with several mesh entities."""
    scene = Scene.create(name="webscene_demo")

    # Ground plane (flat cube)
    add_mesh_entity(scene, "ground",
                    CubeMesh(size=6.0, y=0.1, z=6.0),
                    Pose3.translation(0, -0.55, 0),
                    [0.35, 0.55, 0.35])

    # Blue cube
    add_mesh_entity(scene, "cube",
                    CubeMesh(size=1.0),
                    Pose3.identity(),
                    [0.3, 0.5, 0.8])

    # Red sphere
    add_mesh_entity(scene, "sphere",
                    UVSphereMesh(radius=0.6, n_meridians=24, n_parallels=16),
                    Pose3.translation(2.0, 0.1, 0.0),
                    [0.8, 0.25, 0.25])

    # Yellow cylinder
    add_mesh_entity(scene, "cylinder",
                    CylinderMesh(radius=0.4, height=1.2, segments=24),
                    Pose3.translation(-2.0, 0.0, 0.0),
                    [0.85, 0.75, 0.2])

    # Purple torus
    add_mesh_entity(scene, "torus",
                    TorusMesh(major_radius=0.5, minor_radius=0.15,
                              major_segments=24, minor_segments=12),
                    Pose3.translation(0.0, 0.6, -2.0),
                    [0.6, 0.3, 0.7])

    # Orange cone
    add_mesh_entity(scene, "cone",
                    ConeMesh(radius=0.5, height=1.0, segments=24),
                    Pose3.translation(-2.0, 0.0, -2.0),
                    [0.9, 0.5, 0.15])

    scene.update(0)
    return scene


def extract_scene_json(scene: Scene) -> str:
    """Walk the termin scene, extract mesh+transform data as JSON."""
    objects = []

    for entity in scene.get_all_entities():
        comp = entity.get_component(MeshComponent)
        if comp is None:
            continue

        mesh = comp.mesh
        if not mesh.is_valid:
            continue

        tr = entity.transform
        pos = tr.local_position()
        rot = tr.local_rotation()
        scl = tr.local_scale()

        objects.append({
            "name": entity.name,
            "mesh": {
                "vertices": mesh.vertices.flatten().tolist(),
                "indices": mesh.triangles.flatten().tolist(),
                "normals": mesh.vertex_normals.flatten().tolist(),
            },
            "position": [pos.x, pos.y, pos.z],
            "rotation": [rot.x, rot.y, rot.z, rot.w],
            "scale": [scl.x, scl.y, scl.z],
            "color": ENTITY_COLORS.get(entity.name, [0.5, 0.5, 0.5]),
        })

    return json.dumps(objects)


class SceneHandler(SimpleHTTPRequestHandler):
    """HTTP handler: serves static files and /api/scene endpoint."""

    scene_json: str = "[]"

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write((STATIC_DIR / "index.html").read_bytes())
        elif self.path == "/api/scene":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(self.scene_json.encode())
        else:
            file_path = STATIC_DIR / self.path.lstrip("/")
            if file_path.is_file():
                self.send_response(200)
                content_types = {
                    ".js": "application/javascript",
                    ".css": "text/css",
                    ".html": "text/html",
                    ".json": "application/json",
                }
                self.send_header("Content-Type",
                                 content_types.get(file_path.suffix, "application/octet-stream"))
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
            else:
                self.send_error(404)

    def log_message(self, format, *args):
        pass


def main():
    print("Building termin scene...")
    scene = build_scene()

    print("Extracting scene data...")
    scene_json = extract_scene_json(scene)
    print(f"  {len(json.loads(scene_json))} entities, {len(scene_json)} bytes JSON")

    SceneHandler.scene_json = scene_json

    server = HTTPServer((HOST, PORT), SceneHandler)
    print(f"Serving at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
