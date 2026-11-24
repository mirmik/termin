"""Authored scenes that share the lit web demo assets."""

import math


def object_entity(uuid, mesh, material, position, scale, *, cast_shadow=False):
    return {
        "uuid": uuid, "name": uuid, "pose": {"position": position, "rotation": [0, 0, 0, 1]}, "scale": scale,
        "components": [
            {"type": "MeshComponent", "data": {"mesh": {"uuid": mesh, "type": "uuid", "kind": "tc_mesh"}}},
            {"type": "MeshRenderer", "data": {"cast_shadow": cast_shadow, "material": {
                "uuid": material, "type": "uuid", "kind": "tc_material"}}},
        ],
    }


def studio_entities(camera):
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
    return entities


def physics_entities(camera):
    camera["pose"]["position"] = [0, -6, 0]
    for component in camera["components"]:
        if component["type"] == "CameraComponent":
            component["data"].update(fov_mode="FixVertical", fov_y_degrees=40)
        elif component["type"] == "OrbitCameraController":
            component["data"]["radius"] = 6

    world = {"uuid": "physics-world", "name": "Physics world", "components": [
        {"type": "PhysicsWorldComponent", "data": {
            "gravity": [0, 0, -9.81], "restitution": 0.63, "friction": 0.5, "iterations": 12,
        }},
    ]}
    ball = object_entity("drop-ball", "sphere", "amber", [0, 0, 1.05], [0.36] * 3, cast_shadow=True)
    ball["components"].extend([
        {"type": "ColliderComponent", "data": {"collider_type": "Sphere", "box_size": [2, 2, 2]}},
        {"type": "RigidBodyComponent", "data": {"mass": 1, "is_static": False}},
        {"type": "LightComponent", "data": {
            "light_type": "point", "color": [0.36, 0.115, 0.016], "intensity": 1.0, "shadows_enabled": False,
        }},
    ])
    platform = object_entity("platform", "cube", "porcelain", [0, 0, -1.2], [1.85, 1, 0.2])
    # The fixture cube spans [-0.85, +0.85] along each local axis.
    platform["components"].extend([
        {"type": "ColliderComponent", "data": {"collider_type": "Box", "box_size": [1.7] * 3}},
        {"type": "RigidBodyComponent", "data": {"mass": 1, "is_static": True}},
    ])
    fill = {"uuid": "fill-light", "name": "Cool fill",
            "pose": {"position": [-1.6, -1.4, 2.1], "rotation": [0, 0, 0, 1]},
            "components": [{"type": "LightComponent", "data": {
                "light_type": "point", "color": [0.15, 0.56, 1], "intensity": 0.45, "shadows_enabled": False,
            }}]}
    # Rotate local +Y onto (0.48, 0, -1), placing the suspended ball's shadow
    # about one unit to its right, inside the platform.
    slope = 0.48
    norm = math.sqrt(2 * (1 + slope * slope))
    key = {"uuid": "key-light", "name": "Directional key",
           "pose": {"position": [0, 0, 0], "rotation": [-1 / norm, 0, -slope / norm, math.sqrt(0.5)]},
           "components": [{"type": "LightComponent", "data": {
               "light_type": "directional", "color": [0.64, 0.81, 1], "intensity": 1.2,
               "shadows_enabled": True, "shadows_map_resolution": 512, "cascade_count": 1, "max_distance": 16,
           }}]}
    hud = {"uuid": "physics-hud", "name": "Physics controls", "components": [{
        "type": "UIComponent", "source_id": "physics-controls-component", "data": {"ui_layout": {
            "type": "uuid", "kind": "ui_document", "role": "ui_document", "uuid": "physics-controls",
        }},
    }]}
    return [camera, world, ball, platform, key, fill, hud]
