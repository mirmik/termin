"""Stable UUIDs for default built-in resources."""

BUILTIN_UUIDS = {
    # Shaders
    "ShadowShader": "00000000-0000-0000-0001-000000000005",
    "PickShader": "00000000-0000-0000-0001-000000000006",
    # Meshes
    "Cube": "00000000-0000-0000-0003-000000000001",
    "Sphere": "00000000-0000-0000-0003-000000000002",
    "Plane": "00000000-0000-0000-0003-000000000003",
    "Cylinder": "00000000-0000-0000-0003-000000000004",
    # Pipelines
    "DefaultPipeline": "00000000-0000-0000-0004-000000000001",
    "TrianglePipeline": "00000000-0000-0000-0004-000000000002",
}

BUILTIN_TEXTURE_LEGACY_UUIDS = {
    "__white_1x1__": ("5fb7972ad02ddfad",),
    "__normal_1x1__": ("07151644d3bb92c7",),
}

__all__ = ["BUILTIN_TEXTURE_LEGACY_UUIDS", "BUILTIN_UUIDS"]
