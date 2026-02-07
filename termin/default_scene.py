"""Default scene template used by the launcher and editor."""

from __future__ import annotations

import json
import uuid


def make_default_scene() -> dict:
    """Create a default scene with a Cube, Light, and Ground plane."""
    return {
        "version": "1.0",
        "scene": {
            "uuid": str(uuid.uuid4()),
            "background_color": [0.05, 0.05, 0.08, 1.0],
            "ambient_color": [1.0, 1.0, 1.0],
            "ambient_intensity": 0.15,
            "shadow_settings": {
                "method": 1,
                "softness": 1.0,
                "bias": 0.005,
            },
            "skybox_type": "gradient",
            "skybox_color": [0.5, 0.7, 0.9],
            "skybox_top_color": [0.4, 0.6, 0.9],
            "skybox_bottom_color": [0.6, 0.5, 0.4],
            "entities": [
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Cube",
                    "priority": 0,
                    "visible": True,
                    "enabled": True,
                    "pickable": True,
                    "selectable": True,
                    "layer": 0,
                    "flags": 0,
                    "pose": {
                        "position": [0.0, 0.0, 0.5],
                        "rotation": [0.0, 0.0, 0.0, 1.0],
                    },
                    "scale": [1.0, 1.0, 1.0],
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "enabled": True,
                                "mesh": {
                                    "uuid": "00000000-0000-0000-0003-000000000001",
                                    "name": "Cube",
                                },
                                "material": {
                                    "uuid": "00000000-0001-0000-0001-000000000003",
                                    "name": "NormalizedPBR",
                                    "type": "uuid",
                                },
                                "cast_shadow": True,
                                "_override_material": True,
                                "_overridden_material_data": {
                                    "phases_uniforms": [
                                        {
                                            "u_diffuse_mul": 3.14,
                                            "u_color": [0.084, 0.671, 0.636, 1.0],
                                        },
                                        {
                                            "u_color": [0.084, 0.671, 0.636, 1.0],
                                            "u_metallic": 0.0,
                                            "u_roughness": 0.5,
                                            "u_subsurface": 0.0,
                                            "u_diffuse_mul": 3.14,
                                            "u_emission_color": [0.0, 0.0, 0.0, 1.0],
                                            "u_emission_intensity": 0.0,
                                            "u_normal_strength": 1.0,
                                        },
                                    ],
                                    "phases_textures": [
                                        {},
                                        {
                                            "u_albedo_texture": {
                                                "uuid": "5fb7972ad02ddfad",
                                                "name": "__white_1x1__",
                                                "type": "path",
                                                "path": "__white_1x1__",
                                            },
                                            "u_normal_texture": {
                                                "uuid": "07151644d3bb92c7",
                                                "name": "__normal_1x1__",
                                                "type": "path",
                                                "path": "__normal_1x1__",
                                            },
                                        },
                                    ],
                                },
                            },
                        }
                    ],
                },
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Light",
                    "priority": 0,
                    "visible": True,
                    "enabled": True,
                    "pickable": True,
                    "selectable": True,
                    "layer": 0,
                    "flags": 0,
                    "pose": {
                        "position": [0.83, 4.48, 4.57],
                        "rotation": [-0.1098, -0.4342, 0.8540, 0.2647],
                    },
                    "scale": [1.0, 1.0, 1.0],
                    "components": [
                        {
                            "type": "LightComponent",
                            "data": {
                                "light_type": "directional",
                                "color": [1.0, 1.0, 1.0],
                                "intensity": 1.0,
                                "shadows_enabled": True,
                                "shadows_map_resolution": 2048,
                                "cascade_count": 3,
                                "max_distance": 100.0,
                                "split_lambda": 0.5,
                                "cascade_blend": True,
                            },
                        }
                    ],
                },
                {
                    "uuid": str(uuid.uuid4()),
                    "name": "Ground",
                    "priority": 0,
                    "visible": True,
                    "enabled": True,
                    "pickable": True,
                    "selectable": True,
                    "layer": 0,
                    "flags": 0,
                    "pose": {
                        "position": [0.0, 0.0, 0.0],
                        "rotation": [0.0, 0.0, 0.0, 1.0],
                    },
                    "scale": [5.0, 5.0, 1.0],
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "enabled": True,
                                "mesh": {
                                    "uuid": "00000000-0000-0000-0003-000000000003",
                                    "name": "Plane",
                                },
                                "material": {
                                    "uuid": "00000000-0001-0000-0001-000000000003",
                                    "name": "NormalizedPBR",
                                    "type": "uuid",
                                },
                                "cast_shadow": True,
                                "_override_material": True,
                                "_overridden_material_data": {
                                    "phases_uniforms": [
                                        {
                                            "u_diffuse_mul": 3.14,
                                            "u_color": [0.416, 0.232, 0.030, 1.0],
                                        },
                                        {
                                            "u_color": [0.416, 0.232, 0.030, 1.0],
                                            "u_metallic": 0.0,
                                            "u_roughness": 0.5,
                                            "u_subsurface": 0.0,
                                            "u_diffuse_mul": 3.14,
                                            "u_emission_color": [0.0, 0.0, 0.0, 1.0],
                                            "u_emission_intensity": 0.0,
                                            "u_normal_strength": 1.0,
                                        },
                                    ],
                                    "phases_textures": [
                                        {},
                                        {
                                            "u_albedo_texture": {
                                                "uuid": "5fb7972ad02ddfad",
                                                "name": "__white_1x1__",
                                                "type": "path",
                                                "path": "__white_1x1__",
                                            },
                                            "u_normal_texture": {
                                                "uuid": "07151644d3bb92c7",
                                                "name": "__normal_1x1__",
                                                "type": "path",
                                                "path": "__normal_1x1__",
                                            },
                                        },
                                    ],
                                },
                            },
                        }
                    ],
                },
            ],
            "layer_names": {},
            "flag_names": {},
            "viewport_configs": [],
            "scene_pipelines": [],
        },
        "editor": {
            "camera": {
                "position": [-3.46, 6.50, 5.13],
                "rotation": [0.0735, -0.2864, 0.9253, -0.2376],
                "radius": 7.0,
            },
        },
    }


def write_default_scene(path: str) -> None:
    """Write a default scene to the given file path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(make_default_scene(), f, indent=2)
