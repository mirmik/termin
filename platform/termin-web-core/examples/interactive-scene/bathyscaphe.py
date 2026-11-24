"""Turned metalwork and Fresnel lenses for the bathyscaphe signal receiver."""

import math
from itertools import pairwise

from demo_scenes import object_entity


# Positions are in the instrument face (world X/Z). Camera looks along +Y.
BEACONS = (
    ("seafoam", -.61, .61, [.045, .94, .48]),
    ("ochre", .61, .61, [1.0, .41, .035]),
    ("coral", -.61, -.61, [1.0, .075, .065]),
    ("cobalt", .61, -.61, [.11, .34, 1.0]),
)
FINISHES = {
    "enamel": [.018, .052, .055],
    "graphite": [.026, .036, .039],
    "bronze": [.39, .19, .068],
    "ivory": [.56, .52, .36],
}
BACKGROUND = [.005, .015, .019, 1]


def mesh_from_faces(name, fixture_mesh, vertices, indices):
    return fixture_mesh | {
        "name": name, "uuid": name, "vertices": vertices, "indices": indices,
        "vertex_count": len(vertices) // 12,
        "submeshes": [fixture_mesh["submeshes"][0] | {"name": name, "index_count": len(indices)}],
    }


def turn_profile(name, fixture_mesh, profile, segments=80):
    """Revolve a (radius, depth) tool profile around Y, keeping machined edges crisp."""
    vertices = []
    indices = []
    for (r0, y0), (r1, y1) in pairwise(profile):
        dr, dy = r1 - r0, y1 - y0
        length = math.hypot(dr, dy)
        first = len(vertices) // 12
        for i in range(segments + 1):
            angle = math.tau * i / segments
            c, s = math.cos(angle), math.sin(angle)
            normal = [dy * c / length, -dr / length, dy * s / length]
            for radius, y in ((r0, y0), (r1, y1)):
                vertices.extend([radius * c, y, radius * s, *normal, 0, 0, 0, 0, 0, 1])
            if i < segments:
                a = first + 2 * i
                if r0 > 0:
                    indices.extend([a, a + 1, a + 2])
                if r1 > 0:
                    indices.extend([a + 1, a + 3, a + 2])
    return mesh_from_faces(name, fixture_mesh, [round(v, 6) for v in vertices], indices)


def scale_marks(fixture_mesh):
    """Paint the perimeter graduations and four tactile-style channel markings in one draw."""
    vertices = []
    indices = []

    def rectangle(x, z, angle, width, height):
        c, s = math.cos(angle), math.sin(angle)
        first = len(vertices) // 12
        for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            dx, dz = u * width / 2, v * height / 2
            vertices.extend([x + c * dx + s * dz, -.025, z - s * dx + c * dz,
                             0, -1, 0, 0, 0, 0, 0, 0, 1])
        indices.extend([first, first + 1, first + 2, first, first + 2, first + 3])

    for i in range(80):
        angle = math.tau * i / 80
        radius = 1.39
        rectangle(radius * math.sin(angle), radius * math.cos(angle), angle,
                  .019 if i % 5 == 0 else .011, .077 if i % 5 == 0 else .035)
    for count, (_, x, z, _) in enumerate(BEACONS, start=1):
        for i in range(count):
            rectangle(x + .047 * (i - (count - 1) / 2), z - .535, 0, .016, .069)
    return mesh_from_faces("scale-marks", fixture_mesh, vertices, indices)


def instrument_meshes(fixture_mesh):
    lens = [(0, -.20), (.11, -.195)]
    for radius in (.18, .245, .31, .375, .42):
        depth = -.2 + .54 * radius * radius
        lens.extend([(radius - .009, depth), (radius, depth + .022)])
    profiles = {
        "flange": [(0, .16), (1.61, .16), (1.69, .21), (1.69, .38), (1.63, .43)],
        "outer-lip": [(1.455, .12), (1.482, .043), (1.516, .026), (1.57, .026),
                      (1.587, .049), (1.601, .1), (1.62, .12)],
        "dial-face": [(0, 0), (1.425, 0), (1.454, .015), (1.475, .054), (1.475, .14)],
        "socket": [(.391, -.149), (.41, -.192), (.44, -.195), (.466, -.172),
                   (.471, -.09), (.495, -.084), (.495, -.056), (.48, -.039)],
        "gasket": [(0, -.05), (.46, -.05), (.51, -.062), (.521, -.047), (.521, 0)],
        "fresnel-glass": lens + [(.421, -.082), (.407, -.045)],
    }
    for name, profile in profiles.items():
        yield turn_profile(name, fixture_mesh, profile)
    yield turn_profile("fastener", fixture_mesh, [(0, -.026), (.041, -.026), (.05, -.013), (.05, 0)], 6)
    yield scale_marks(fixture_mesh)


def instrument_entities(camera):
    camera["pose"]["position"] = [0, -5, 0]
    camera_component = next(c for c in camera["components"] if c["type"] == "CameraComponent")
    camera_component["data"].update(fov_mode="FixVertical", fov_y_degrees=40)
    camera["components"] = [camera_component]
    entities = [camera]

    def mount(name, mesh, finish, position=(0, 0, 0)):
        entity = object_entity(name, mesh, finish, position, [1, 1, 1])
        entity["pickable"] = False
        entities.append(entity)
        return entity

    mount("pressure-flange", "flange", "graphite")
    mount("retaining-ring", "outer-lip", "bronze")
    mount("instrument-face", "dial-face", "enamel")
    mount("graduations", "scale-marks", "ivory")
    for i in range(8):
        angle = math.tau * (i + .5) / 8
        mount(f"stud-{i}", "fastener", "graphite", [1.546 * math.cos(angle), .024, 1.546 * math.sin(angle)])

    for i, (name, x, z, rgb) in enumerate(BEACONS, start=1):
        mount(f"seal-{i}", "gasket", "graphite", [x, 0, z])
        mount(f"collar-{i}", "socket", "bronze", [x, 0, z])
        light = mount(f"beacon-{i}", "fresnel-glass", name, [x, -.13, z])
        light["pickable"] = True
        light["components"].append({"type": "LightComponent", "data": {
            "light_type": "point", "color": [v * .48 for v in rgb], "intensity": 1.6,
            "range": 1.4, "shadows_enabled": False,
        }})
    for name, position, rgb, intensity in (
        ("instrument-key", [-1.15, -1.8, 1.85], [1, .86, .68], 1.85),
        ("instrument-fill", [2.5, -1.65, -.9], [.36, .71, .9], .78),
    ):
        entities.append({"uuid": name, "name": name, "pose": {"position": position, "rotation": [0, 0, 0, 1]},
                         "components": [{"type": "LightComponent", "data": {
                             "light_type": "point", "color": rgb, "intensity": intensity, "shadows_enabled": False,
                         }}]})
    return entities
