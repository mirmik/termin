"""The flooded cargo hold, rescue vehicle and flight recorder of the salvage game."""

import math
import random
from itertools import pairwise

from demo_scenes import object_entity


BACKGROUND = [0.012, 0.095, 0.14, 1]
FINISHES = {
    "ocean": [0.032, 0.23, 0.29],
    "haze": [0.045, 0.27, 0.31],
    "distant": [0.024, 0.117, 0.15],
    "rear-steel": [0.036, 0.14, 0.16],
    "steel": [0.09, 0.21, 0.22],
    "iron": [0.045, 0.09, 0.105],
    "cut-steel": [0.21, 0.33, 0.30],
    "rust": [0.31, 0.13, 0.062],
    "sand": [0.20, 0.26, 0.21],
    "weed": [0.052, 0.24, 0.17],
    "ivory": [0.82, 0.86, 0.66],
    "signal": [1.0, 0.55, 0.026],
    "rescue": [1.0, 0.115, 0.015],
    "mint": [0.16, 1.5, 0.85],
    "glass": [0.025, 0.47, 0.58],
    "black": [0.027, 0.047, 0.06],
}


class Model:
    """Bake each material into a single mesh, preserving a separate entity for each moving assembly."""

    def __init__(self, name):
        self.name = name
        self.parts = {}

    def face(self, material, points):
        p, q, r = points[:3]
        a = [q[i] - p[i] for i in range(3)]
        b = [r[i] - p[i] for i in range(3)]
        normal = (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
        length = math.hypot(*normal)
        if length < 1e-10:
            return
        normal = [v / length for v in normal]
        vertices, indices = self.parts.setdefault(material, ([], []))
        start = len(vertices) // 12
        for point in points:
            vertices.extend([*point, *normal, 0, 0, 1, 0, 0, 1])
        for i in range(1, len(points) - 1):
            indices.extend([start, start + i, start + i + 1])

    def plate(self, material, outline, y, depth):
        """Extrude a convex counterclockwise outline in the side-view X/Z plane."""
        front = [(x, y - depth / 2, z) for x, z in outline]
        rear = [(x, y + depth / 2, z) for x, z in outline]
        self.face(material, front)
        self.face(material, list(reversed(rear)))
        for i in range(len(front)):
            j = (i + 1) % len(front)
            self.face(material, [front[j], front[i], rear[i], rear[j]])

    def box(self, material, pos, size):
        x, y, z = pos
        w, d, h = size
        self.plate(
            material,
            [(x - w / 2, z - h / 2), (x + w / 2, z - h / 2), (x + w / 2, z + h / 2), (x - w / 2, z + h / 2)],
            y,
            d,
        )

    def beam(self, material, start, end, y, width, depth):
        x, z = start
        u, v = end
        length = math.hypot(u - x, v - z)
        dx, dz = (z - v) * width / (2 * length), (u - x) * width / (2 * length)
        self.plate(material, [(x - dx, z - dz), (u - dx, v - dz), (u + dx, v + dz), (x + dx, z + dz)], y, depth)

    def disc(self, material, x, y, z, radius, depth, n=20):
        ring = [(x + radius * math.cos(math.tau * i / n), z + radius * math.sin(math.tau * i / n)) for i in range(n)]
        self.plate(material, ring, y, depth)

    def meshes(self, template):
        for material, (vertices, indices) in self.parts.items():
            name = self.name + "-" + material
            yield template | {
                "uuid": name,
                "name": name,
                "vertices": [round(v, 6) for v in vertices],
                "indices": indices,
                "vertex_count": len(vertices) // 12,
                "submeshes": [template["submeshes"][0] | {"name": name, "index_count": len(indices)}],
            }

    def entities(self):
        return [
            object_entity(self.name + "-" + material, self.name + "-" + material, material, [0, 0, 0], [1, 1, 1])
            for material in self.parts
        ]


def body(name, pos, kind, size, mass=0):
    return {
        "uuid": name,
        "name": name,
        "pose": {"position": pos, "rotation": [0, 0, 0, 1]},
        "components": [
            {"type": "ColliderComponent", "data": {"collider_type": kind, "box_size": size}},
            {"type": "RigidBodyComponent", "data": {"mass": mass or 1, "is_static": mass == 0}},
        ],
    }


def vehicle():
    sub = Model("sub")
    # Ring stations of the pressure hull, from propeller to bow, revolved around X.
    stations = [
        (-0.42, 0.068),
        (-0.355, 0.14),
        (-0.24, 0.226),
        (-0.10, 0.255),
        (0.14, 0.25),
        (0.255, 0.216),
        (0.345, 0.148),
        (0.38, 0.06),
    ]
    for (x0, r0), (x1, r1) in pairwise(stations):
        for i in range(16):
            a, b = math.tau * i / 16, math.tau * (i + 1) / 16
            sub.face(
                "signal",
                [
                    (x0, r0 * math.cos(a), r0 * math.sin(a)),
                    (x0, r0 * math.cos(b), r0 * math.sin(b)),
                    (x1, r1 * math.cos(b), r1 * math.sin(b)),
                    (x1, r1 * math.cos(a), r1 * math.sin(a)),
                ],
            )
    sub.box("black", (-0.415, 0, 0), (0.07, 0.19, 0.17))
    sub.box("signal", (-0.36, 0, 0.114), (0.115, 0.065, 0.19))
    sub.box("black", (-0.01, 0, 0.24), (0.22, 0.20, 0.045))
    sub.box("signal", (-0.04, 0, 0.282), (0.15, 0.13, 0.048))
    sub.box("black", (0.008, 0, 0.32), (0.036, 0.042, 0.08))
    sub.box("ivory", (0.025, 0, 0.35), (0.068, 0.052, 0.025))
    for side in (-1, 1):
        y = side * 0.143
        sub.box("black", (0, y, -0.285), (0.63, 0.057, 0.043))
        for x in (-0.19, 0.19):
            sub.beam("iron", (x, -0.17), (x + 0.025, -0.277), y, 0.035, 0.037)
    # A thick brass viewport, its glazing and a sliver of reflected surface light.
    for x, z, r in ((0.108, 0.035, 0.135), (-0.17, 0.025, 0.068)):
        sub.disc("black", x, -0.225, z, r, 0.052)
        sub.disc("ivory", x, -0.255, z, r * 0.84, 0.022)
        sub.disc("glass", x, -0.273, z, r * 0.67, 0.018)
        sub.beam("ivory", (x - r * 0.36, z + r * 0.12), (x - r * 0.05, z + r * 0.43), -0.285, 0.011, 0.006)
    sub.box("black", (0.342, -0.024, 0.008), (0.09, 0.17, 0.13))
    sub.box("ivory", (0.391, -0.024, 0.008), (0.018, 0.135, 0.095))
    sub.disc("black", -0.32, -0.12, -0.10, 0.093, 0.16)
    sub.disc("steel", -0.32, -0.21, -0.10, 0.070, 0.035)
    for i in range(3):
        a = math.tau * i / 3
        sub.beam(
            "black", (-0.32, -0.10), (-0.32 + 0.057 * math.cos(a), -0.10 + 0.057 * math.sin(a)), -0.234, 0.019, 0.01
        )
    return sub


def recorder():
    cargo = Model("recorder")
    cargo.box("rescue", (0, 0, -0.025), (0.46, 0.36, 0.41))
    for x in (-0.195, 0.195):
        cargo.box("black", (x, 0, -0.025), (0.052, 0.388, 0.428))
    cargo.box("iron", (0, 0, -0.225), (0.46, 0.37, 0.04))
    cargo.box("ivory", (0, -0.189, -0.035), (0.235, 0.012, 0.064))
    cargo.box("black", (0, 0, 0.185), (0.24, 0.08, 0.035))
    for x in (-0.071, 0.071):
        cargo.box("black", (x, 0, 0.225), (0.034, 0.042, 0.077))
    cargo.box("ivory", (0, 0, 0.259), (0.177, 0.042, 0.032))
    return cargo


def wreck():
    hull = Model("hold")
    rng = random.Random(705)
    # The far side of the hull has buckled open. Water and fish show between exposed frames.
    hull.box("ocean", (0, 4.5, 0.1), (18, 0.12, 8.5))
    for _ in range(60):
        x, z = rng.uniform(-7.5, 7.5), rng.uniform(-2.2, 3.1)
        s = rng.uniform(0.018, 0.09)
        hull.plate("haze", [(x - s, z - 0.018), (x + s, z), (x - s * 0.4, z + 0.018)], 3.8, 0.012)
    for x, z in ((-2.9, 1.08), (-2.65, 1.30), (-3.3, 0.92), (1.39, 0.80), (1.67, 0.97), (1.85, 0.72)):
        hull.plate("distant", [(x - 0.12, z), (x, z - 0.035), (x + 0.09, z), (x, z + 0.036)], 3.0, 0.027)
        hull.plate("distant", [(x - 0.17, z - 0.035), (x - 0.09, z), (x - 0.17, z + 0.035)], 3.0, 0.027)

    # Jagged remains of the aft wall with closely spaced heavy frames and hull rivets.
    for index, x in enumerate((-5.5, -3.9, -2.3, -0.7, 0.9, 2.5, 4.1, 5.7)):
        top = (-0.93, -0.68, -1.16, -0.85, -1.08, -0.56, -0.64, -0.97)[index]
        hull.plate(
            "rear-steel",
            [(x - 0.79, -2.5), (x + 0.79, -2.5), (x + 0.79, top - 0.10), (x + 0.29, top + 0.15), (x - 0.79, top)],
            1.95,
            0.17,
        )
        hull.beam("distant", (x - 0.76, -2.30), (x - 0.76, 2.45), 2.23, 0.105, 0.22)
        hull.beam("distant", (x - 0.74, 1.32), (x - 0.26, 2.44), 2.23, 0.066, 0.16)
        for z in (-1.62, -1.35):
            hull.disc("cut-steel", x - 0.67, 1.85, z, 0.023, 0.018, 7)
    hull.box("distant", (0, 2.14, 2.43), (13.6, 0.28, 0.19))
    hull.box("rear-steel", (0, 1.85, -1.76), (12, 0.16, 0.08))
    # Deck, overhead girders and torn central frames. Fore edges sit in the playable depth plane.
    hull.box("iron", (0, 0.35, -2.61), (10.7, 2.6, 0.72))
    hull.box("steel", (0, -0.92, -2.31), (10.7, 0.16, 0.12))
    hull.box("rust", (0, -1.03, -2.42), (10.7, 0.13, 0.045))
    hull.box("iron", (0, 0.52, 2.82), (10.7, 2.35, 0.44))
    hull.box("cut-steel", (0, -0.64, 2.64), (10.65, 0.14, 0.09))
    for x in (-5.16, 5.16):
        hull.box("steel", (x, 0.1, 0.12), (0.32, 2.2, 5.55))
        inner = math.copysign(4.99, x)
        for y in (-0.76, 0.22, 0.99):
            hull.box("rear-steel", (inner, y, 0.14), (0.05, 0.061, 4.82))
        for z in (-1.36, 0.95, 1.06):
            hull.box("iron", (inner, 0.06, z), (0.062, 2.08, 0.034))
    for i in range(-6, 7):
        x = i * 0.78
        hull.box("cut-steel", (x, 0.27, -2.238), (0.034, 2.1, 0.019))
        hull.disc("cut-steel", x, -1.041, -2.32, 0.035, 0.02, 7)
    for z, h in ((-1.65, 1.20), (2.08, 1.06)):
        hull.box("steel", (0, 0.1, z), (0.42, 1.85, h))
        hull.box("rust", (0, -0.86, z), (0.39, 0.105, h))
        for side in (-1, 1):
            hull.box("cut-steel", (side * 0.18, -0.945, z), (0.047, 0.09, h))
        for dz in (-0.31, 0.31):
            hull.disc("iron", 0, -0.93, z + dz, 0.043, 0.035, 8)
        end = -1.05 if z < 0 else 1.55
        hull.box("signal", (0, -0.02, end + (-0.048 if z < 0 else 0.048)), (0.45, 1.98, 0.096))
        hull.box("black", (0, -1.018, end + (-0.049 if z < 0 else 0.049)), (0.065, 0.028, 0.089))

    # Cable run on the back plating and an overhead hoist pulley.
    hull.beam("rust", (-5.2, -1.09), (-3.82, -1.09), 1.66, 0.075, 0.09)
    hull.beam("rust", (-3.82, -1.09), (-3.62, -1.30), 1.66, 0.075, 0.09)
    hull.beam("rust", (-3.62, -1.30), (-1.38, -1.30), 1.66, 0.075, 0.09)
    for x in (-4.94, -4.3, -3.27, -2.77, -2.06):
        z = -1.09 if x < -3.7 else -1.30
        hull.box("cut-steel", (x, 1.58, z), (0.042, 0.053, 0.104))
    hull.beam("iron", (-3.9, 2.62), (-3.44, 2.25), 0.32, 0.10, 0.18)
    hull.box("rust", (-3.32, 0.32, 2.25), (0.34, 0.23, 0.14))
    hull.disc("iron", -3.32, 0.16, 2.16, 0.13, 0.12)
    hull.disc("cut-steel", -3.32, 0.07, 2.16, 0.064, 0.04)
    # Pickup cradle stripes and the raised return dock with a three-chevron beacon.
    for i in range(6):
        hull.box("cut-steel", (-4.22 + i * 0.21, 0.0, -2.225), (0.095, 0.73, 0.031))
    hull.box("iron", (3.4, 0.0, -1.935), (1.8, 1.6, 0.63))
    hull.box("steel", (3.4, -0.818, -1.94), (1.79, 0.06, 0.42))
    for i in range(6):
        x = 2.65 + i * 0.265
        hull.beam("iron", (x, -2.11), (x + 0.15, -1.77), -0.87, 0.080, 0.04)
    hull.box("mint", (3.4, -0.823, -1.67), (1.8, 0.095, 0.075))
    for x in (2.57, 4.23):
        hull.box("mint", (x, 0.03, -1.605), (0.063, 1.54, 0.026))
    for z in (-0.69, -0.49, -0.29):
        hull.beam("mint", (3.17, z + 0.11), (3.4, z), 0.87, 0.044, 0.055)
        hull.beam("mint", (3.4, z), (3.63, z + 0.11), 0.87, 0.044, 0.055)
    # Short weeds grow behind the collision plane and cast readable silhouettes on the deck.
    for center in (-4.77, -2.33, -1.89, 0.57, 1.35, 4.68):
        for _ in range(4):
            x = center + rng.uniform(-0.16, 0.16)
            h = rng.uniform(0.1, 0.36)
            hull.plate(
                "weed",
                [
                    (x - 0.037, -2.24),
                    (x + 0.036, -2.24),
                    (x + 0.049, -2.24 + h * 0.45),
                    (x + rng.uniform(0.04, 0.12), -2.24 + h),
                ],
                0.72,
                0.032,
            )
    return hull


def light(name, xyz, color, intensity):
    return {
        "uuid": name,
        "name": name,
        "pose": {"position": xyz, "rotation": [0, 0, 0, 1]},
        "components": [
            {
                "type": "LightComponent",
                "data": {
                    "light_type": "point",
                    "color": color,
                    "intensity": intensity,
                    "shadows_enabled": False,
                },
            }
        ],
    }


def salvage_scene(template):
    models = [wreck(), vehicle(), recorder()]
    meshes = [mesh for model in models for mesh in model.meshes(template)]
    cable = Model("line")
    cable.box("ivory", (0, 0, 0), (1, 1, 1))
    meshes.extend(cable.meshes(template))

    def entities(camera):
        camera["pose"] = {"position": [0, -10.1, 1.22], "rotation": [math.sin(-0.055), 0, 0, math.cos(0.055)]}
        component = next(c for c in camera["components"] if c["type"] == "CameraComponent")
        component["data"].update(fov_mode="FixVertical", fov_y_degrees=34)
        camera["components"] = [component]
        world = {
            "uuid": "salvage-world",
            "name": "Flooded hold",
            "components": [
                {
                    "type": "PhysicsWorldComponent",
                    "data": {"gravity": [0, 0, -3.2], "restitution": 0.10, "friction": 0.40, "iterations": 14},
                },
            ],
        }
        sub = body("salvage-sub", [-3.6, 0, -0.30], "Sphere", [0.84] * 3, mass=2)
        cargo = body("salvage-cargo", [-3.6, 0, -1.85], "Box", [0.46, 0.38, 0.47], mass=1)
        sub["children"] = models[1].entities()
        sub["children"].append(light("salvage-headlamp", (0.44, -0.19, 0.02), [1, 0.77, 0.41], 1.85))
        cargo["children"] = models[2].entities()
        line = object_entity("salvage-cable", "line-ivory", "ivory", [-3.6, 0, -0.5], [0.01, 0.01, 0.01])
        fixed = [
            ("salvage-floor", (0, 0, -2.61), (10.7, 2.65, 0.72)),
            ("salvage-ceiling", (0, 0, 2.82), (10.7, 2.65, 0.44)),
            ("salvage-port", (-5.16, 0, 0.12), (0.32, 2.65, 5.55)),
            ("salvage-starboard", (5.16, 0, 0.12), (0.32, 2.65, 5.55)),
            ("salvage-bulkhead-lower", (0, 0, -1.65), (0.42, 2.1, 1.2)),
            ("salvage-bulkhead-upper", (0, 0, 2.08), (0.42, 2.1, 1.06)),
            ("salvage-pad", (3.4, 0, -1.935), (1.8, 1.6, 0.63)),
        ]
        return [
            camera,
            world,
            sub,
            cargo,
            line,
            *models[0].entities(),
            *(body(name, pos, "Box", size) for name, pos, size in fixed),
            light("surface", (-2.5, -3.3, 4.2), [0.70, 0.88, 1], 2.8),
            light("hatch-worklight", (-3.7, -1.8, 0.85), [1, 0.75, 0.36], 0.85),
            light("dock-light", (3.45, -1.55, -0.18), [0.26, 1, 0.75], 1.4),
            light("port-light", (4, 1.25, 3.3), [0.17, 0.69, 1], 0.9),
        ]

    return meshes, entities
