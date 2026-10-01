import copy
import gc
import json
from pathlib import Path
import struct
import uuid

import numpy as np
import pytest

from termin.geombase import Mat44
from termin.base import log
from termin.mesh import tc_mesh_get
from termin.glb import NativePrimitiveInfo, NativeStaticMeshDocument
from termin.glb import _glb_native
from termin.glb.native import NativeGLBSceneData
from termin.glb_adapters.asset import GLBAsset
from termin.glb_adapters.instantiator import instantiate_glb
from termin.default_assets.resource_manager import DefaultResourceManager


_FIXTURES = Path(__file__).parents[3] / "termin-thirdparty" / "cgltf" / "fuzz" / "data"


def _write_glb(path: Path, document: dict, binary: bytes) -> Path:
    document["buffers"] = [{"byteLength": len(binary)}]
    json_data = json.dumps(document, separators=(",", ":")).encode("utf-8")
    json_data += b" " * (-len(json_data) % 4)
    binary_data = binary + b"\0" * (-len(binary) % 4)
    total_size = 12 + 8 + len(json_data) + 8 + len(binary_data)
    path.write_bytes(
        struct.pack("<4sII", b"glTF", 2, total_size)
        + struct.pack("<II", len(json_data), 0x4E4F534A)
        + json_data
        + struct.pack("<II", len(binary_data), 0x004E4942)
        + binary_data
    )
    return path


def _write_bulk_animation_glb(path: Path) -> Path:
    times = struct.pack("<2f", 0.0, 1.0)
    translations = struct.pack("<6f", 1.0, 2.0, 3.0, 7.0, 8.0, 9.0)
    scales = struct.pack("<6f", 1.0, 2.0, 3.0, 3.0, 6.0, 9.0)
    binary = times + translations + scales
    return _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(times)},
                {
                    "buffer": 0,
                    "byteOffset": len(times),
                    "byteLength": len(translations),
                },
                {
                    "buffer": 0,
                    "byteOffset": len(times) + len(translations),
                    "byteLength": len(scales),
                },
            ],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 2, "type": "SCALAR"},
                {"bufferView": 1, "componentType": 5126, "count": 2, "type": "VEC3"},
                {"bufferView": 2, "componentType": 5126, "count": 2, "type": "VEC3"},
            ],
            "nodes": [{"name": "Animated"}],
            "animations": [
                {
                    "name": "ExactTracks",
                    "samplers": [
                        {"input": 0, "output": 1, "interpolation": "STEP"},
                        {"input": 0, "output": 2, "interpolation": "LINEAR"},
                    ],
                    "channels": [
                        {"sampler": 0, "target": {"node": 0, "path": "translation"}},
                        {"sampler": 1, "target": {"node": 0, "path": "scale"}},
                    ],
                }
            ],
        },
        binary,
    )


def _write_column_major_skin_glb(path: Path) -> Path:
    inverse_bind = struct.pack(
        "<16f",
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        -2.0, -3.0, -4.0, 1.0,
    )
    return _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(inverse_bind)},
            ],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 1, "type": "MAT4"},
            ],
            "nodes": [{"name": "Joint"}],
            "skins": [{"name": "Skin", "joints": [0], "inverseBindMatrices": 0}],
        },
        inverse_bind,
    )


def _write_production_native_glb(
    path: Path, *, duplicate_animation_name: bool = False
) -> Path:
    positions = struct.pack(
        "<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0
    )
    indices = struct.pack("<3H", 0, 1, 2)
    times = struct.pack("<2f", 0.0, 1.0)
    translations = struct.pack("<6f", 0.0, 0.0, 0.0, 2.0, 3.0, 4.0)
    chunks = (positions, indices, times, translations)
    offsets = []
    binary = b""
    for chunk in chunks:
        offsets.append(len(binary))
        binary += chunk
    animation = {
        "name": "Move",
        "samplers": [{"input": 2, "output": 3, "interpolation": "STEP"}],
        "channels": [
            {
                "sampler": 0,
                "target": {"node": 1, "path": "translation"},
            }
        ],
    }
    animations = [animation]
    if duplicate_animation_name:
        animations.append(animation.copy())
    return _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "bufferViews": [
                {
                    "buffer": 0,
                    "byteOffset": offset,
                    "byteLength": len(chunk),
                }
                for offset, chunk in zip(offsets, chunks, strict=True)
            ],
            "accessors": [
                {
                    "bufferView": 0,
                    "componentType": 5126,
                    "count": 3,
                    "type": "VEC3",
                },
                {
                    "bufferView": 1,
                    "componentType": 5123,
                    "count": 3,
                    "type": "SCALAR",
                },
                {
                    "bufferView": 2,
                    "componentType": 5126,
                    "count": 2,
                    "type": "SCALAR",
                },
                {
                    "bufferView": 3,
                    "componentType": 5126,
                    "count": 2,
                    "type": "VEC3",
                },
            ],
            "meshes": [
                {
                    "name": "Body",
                    "primitives": [
                        {
                            "attributes": {"POSITION": 0},
                            "indices": 1,
                            "mode": 4,
                        }
                    ],
                }
            ],
            "nodes": [
                {"name": "Root", "scale": [2.0, 2.0, 2.0], "children": [1]},
                {"name": "Animated", "translation": [1.0, 0.0, 0.0]},
                {"name": "MeshResource", "mesh": 0},
            ],
            "animations": animations,
        },
        binary,
    )


def _write_indexed_triangle_glb(path: Path, component_type: int | None, indices=(0, 1, 2)) -> Path:
    positions = b"".join(
        struct.pack("<4f", *position, 99.0)
        for position in ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0))
    )
    buffer_views = [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions), "byteStride": 16}]
    accessors = [
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": 3,
            "type": "VEC3",
        }
    ]
    primitive = {"attributes": {"POSITION": 0}, "mode": 4}
    binary = positions
    if component_type is not None:
        formats = {5121: "B", 5123: "H", 5125: "I"}
        index_data = struct.pack("<3" + formats[component_type], *indices)
        index_offset = len(binary)
        binary += index_data
        buffer_views.append(
            {"buffer": 0, "byteOffset": index_offset, "byteLength": len(index_data)}
        )
        accessors.append(
            {
                "bufferView": 1,
                "componentType": component_type,
                "count": 3,
                "type": "SCALAR",
            }
        )
        primitive["indices"] = 1
    return _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "bufferViews": buffer_views,
            "accessors": accessors,
            "meshes": [{"name": "StridedTriangle", "primitives": [primitive]}],
        },
        binary,
    )


def _write_sparse_triangle_glb(path: Path) -> Path:
    sparse_indices = struct.pack("<3B", 0, 1, 2)
    sparse_values = struct.pack(
        "<9f", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0
    )
    binary = sparse_indices + b"\0" + sparse_values
    return _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": 3},
                {"buffer": 0, "byteOffset": 4, "byteLength": len(sparse_values)},
            ],
            "accessors": [
                {
                    "componentType": 5126,
                    "count": 3,
                    "type": "VEC3",
                    "sparse": {
                        "count": 3,
                        "indices": {"bufferView": 0, "componentType": 5121},
                        "values": {"bufferView": 1},
                    },
                }
            ],
            "meshes": [
                {
                    "name": "SparseTriangle",
                    "primitives": [{"attributes": {"POSITION": 0}, "mode": 4}],
                }
            ],
        },
        binary,
    )


def _write_normalized_tangent_glb(
    path: Path, *, include_tangent: bool = True, mirrored_uv: bool = False
) -> Path:
    positions = struct.pack("<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    normals = struct.pack("<9b", 127, 0, -128, 127, 0, -128, 127, 0, -128)
    uv_values = (0, 65535, 65535, 65535, 0, 0) if mirrored_uv else (0, 0, 65535, 0, 0, 65535)
    uvs = struct.pack("<6H", *uv_values)
    tangents = struct.pack("<12b", 127, 0, 0, 127, 127, 0, 0, 127, 127, 0, 0, -128)
    binary = positions + normals + b"\0" * 3 + uvs + tangents
    attributes = {
        "POSITION": 0,
        "NORMAL": 1,
        "TEXCOORD_0": 2,
    }
    if include_tangent:
        attributes["TANGENT"] = 3
    return _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(positions)},
                {"buffer": 0, "byteOffset": 36, "byteLength": len(normals)},
                {"buffer": 0, "byteOffset": 48, "byteLength": len(uvs)},
                {"buffer": 0, "byteOffset": 60, "byteLength": len(tangents)},
            ],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                {
                    "bufferView": 1,
                    "componentType": 5120,
                    "normalized": True,
                    "count": 3,
                    "type": "VEC3",
                },
                {
                    "bufferView": 2,
                    "componentType": 5123,
                    "normalized": True,
                    "count": 3,
                    "type": "VEC2",
                },
                {
                    "bufferView": 3,
                    "componentType": 5120,
                    "normalized": True,
                    "count": 3,
                    "type": "VEC4",
                },
            ],
            "meshes": [
                {
                    "name": "NormalizedTangent",
                    "primitives": [
                        {
                            "attributes": attributes,
                            "mode": 4,
                        }
                    ],
                }
            ],
        },
        binary,
    )


def _write_directional_triangle_glb(
    path: Path,
    *,
    positions=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    normals=((0.0, 0.0, 1.0),) * 3,
    uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
    tangents=None,
    indices=(0, 1, 2),
    skinned=False,
) -> Path:
    binary = bytearray()
    views = []
    accessors = []
    attributes = {}

    def append_accessor(rows, component_type=5126, format_code="f"):
        components = len(rows[0])
        values = [value for row in rows for value in row]
        payload = struct.pack("<" + str(len(values)) + format_code, *values)
        binary.extend(b"\0" * (-len(binary) % 4))
        views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(payload)})
        binary.extend(payload)
        accessors.append(
            {
                "bufferView": len(views) - 1,
                "componentType": component_type,
                "count": len(rows),
                "type": "SCALAR" if components == 1 else f"VEC{components}",
            }
        )
        return len(accessors) - 1

    for semantic, rows in (
        ("POSITION", positions), ("NORMAL", normals),
        ("TEXCOORD_0", uvs), ("TANGENT", tangents),
    ):
        if rows is not None:
            attributes[semantic] = append_accessor(rows)
    if skinned:
        attributes["JOINTS_0"] = append_accessor(((0, 0, 0, 0),) * len(positions), 5123, "H")
        attributes["WEIGHTS_0"] = append_accessor(((1.0, 0.0, 0.0, 0.0),) * len(positions))
    index_accessor = append_accessor(tuple((index,) for index in indices), 5123, "H")
    document = {
        "asset": {"version": "2.0"},
        "bufferViews": views,
        "accessors": accessors,
        "meshes": [{"name": "Directions", "primitives": [{"attributes": attributes, "indices": index_accessor, "mode": 4}]}],
    }
    if skinned:
        document["nodes"] = [{"mesh": 0, "skin": 0}, {"name": "Joint"}]
        document["skins"] = [{"joints": [1]}]
    return _write_glb(path, document, bytes(binary))


def _mesh_snapshot(mesh):
    return (
        mesh.uuid, mesh.name, mesh.version, mesh.stride,
        mesh.vertex_count, mesh.index_count, mesh.submesh_count,
        np.asarray(mesh.mesh.get_vertices_buffer()).tobytes(),
        np.asarray(mesh.mesh.get_indices_buffer()).tobytes(),
        tuple((section.name, section.material_slot) for section in mesh.submeshes),
    )


def _assert_direction_build_rejected_without_publication(path: Path, semantic: str, location: str):
    sentinel_uuid = str(uuid.uuid4())
    sentinel_path = _write_indexed_triangle_glb(path.parent / "sentinel.glb", 5123)
    sentinel = NativeStaticMeshDocument(sentinel_path).build_mesh(
        0, sentinel_uuid, name="unchanged sentinel", convert_to_z_up=False
    )
    before = _mesh_snapshot(sentinel)
    fresh_uuid = str(uuid.uuid4())
    errors = []
    log.capture_start(128)
    try:
        for target_uuid in (sentinel_uuid, fresh_uuid):
            with pytest.raises(RuntimeError, match="^invalid_format:") as failure:
                document = NativeStaticMeshDocument(path)
                document.build_mesh(0, target_uuid, name="replacement", convert_to_z_up=False)
            errors.append(str(failure.value))
        records, dropped = log.capture_drain(128)
    finally:
        log.capture_stop()
    assert dropped == 0
    for message in errors:
        assert path.name in message
        assert "mesh[0]" in message
        assert "primitive[0]" in message
        assert semantic in message
        assert location in message
    error_records = [message for level, message in records if level == log.Level.ERROR]
    assert len(error_records) >= 2
    assert all(any(message.removeprefix("invalid_format: ") in record for record in error_records) for message in errors)
    assert _mesh_snapshot(sentinel) == before
    assert _mesh_snapshot(tc_mesh_get(sentinel_uuid)) == before
    assert tc_mesh_get(fresh_uuid) is None


def _write_multi_primitive_glb(path: Path) -> Path:
    first = struct.pack("<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    second = struct.pack("<9f", 2.0, 0.0, 0.0, 3.0, 0.0, 0.0, 2.0, 1.0, 0.0)
    return _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(first)},
                {"buffer": 0, "byteOffset": len(first), "byteLength": len(second)},
            ],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC3"},
            ],
            "materials": [{"name": "First"}, {"name": "Second"}],
            "meshes": [
                {
                    "name": "Multi",
                    "primitives": [
                        {"attributes": {"POSITION": 0}, "material": 0, "mode": 4},
                        {"attributes": {"POSITION": 1}, "material": 1, "mode": 4},
                    ],
                }
            ],
        },
        first + second,
    )


def _write_material_texture_glb(path: Path, *, texture_transform: bool = False) -> Path:
    positions = struct.pack("<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    fallback = b"PNG-fallback"
    webp = b"WEBP-selected"
    base_color_view = {"index": 0, "texCoord": 0}
    if texture_transform:
        base_color_view["extensions"] = {
            "KHR_texture_transform": {"offset": [0.25, 0.5]}
        }
    binary = positions + fallback + webp
    return _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "extensionsUsed": ["EXT_texture_webp"],
            "extensionsRequired": ["EXT_texture_webp"],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(positions)},
                {
                    "buffer": 0,
                    "byteOffset": len(positions),
                    "byteLength": len(fallback),
                },
                {
                    "buffer": 0,
                    "byteOffset": len(positions) + len(fallback),
                    "byteLength": len(webp),
                },
            ],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}
            ],
            "images": [
                {"name": "Fallback", "mimeType": "image/png", "bufferView": 1},
                {"name": "SelectedWebP", "mimeType": "image/webp", "bufferView": 2},
            ],
            "samplers": [
                {"magFilter": 9728, "minFilter": 9987, "wrapS": 33071, "wrapT": 33648}
            ],
            "textures": [
                {
                    "name": "WebPTexture",
                    "source": 0,
                    "sampler": 0,
                    "extensions": {"EXT_texture_webp": {"source": 1}},
                },
                {"name": "DefaultSampler", "source": 1},
            ],
            "materials": [
                {
                    "name": "NativePBR",
                    "pbrMetallicRoughness": {
                        "baseColorFactor": [0.1, 0.2, 0.3, 0.4],
                        "baseColorTexture": base_color_view,
                        "metallicFactor": 0.6,
                        "roughnessFactor": 0.7,
                        "metallicRoughnessTexture": {"index": 1},
                    },
                    "normalTexture": {"index": 1, "scale": 0.8},
                    "occlusionTexture": {"index": 1, "strength": 0.9},
                    "emissiveTexture": {"index": 0},
                    "emissiveFactor": [0.4, 0.5, 0.6],
                    "alphaMode": "MASK",
                    "alphaCutoff": 0.25,
                    "doubleSided": True,
                }
            ],
            "meshes": [
                {
                    "name": "MaterialTriangle",
                    "primitives": [
                        {"attributes": {"POSITION": 0}, "material": 0, "mode": 4}
                    ],
                }
            ],
        },
        binary,
    )


def test_native_backend_reports_pinned_cgltf_revision():
    info = _glb_native.backend_info()

    assert info == {
        "name": "cgltf",
        "cgltf_version": "1.15",
        "cgltf_revision": "85cd62382dfea638278962690cf515023f33ed00",
    }
    assert _glb_native.error_code_name(_glb_native.NativeErrorCode.UNSUPPORTED) == "unsupported"


def test_native_document_discovers_and_builds_box_without_python_geometry_arrays():
    document = NativeStaticMeshDocument(_FIXTURES / "Box.glb")

    assert document.meshes == (
        type(document.meshes[0])(
            name="Mesh",
            primitive_count=1,
            vertex_count=24,
            index_count=36,
            skinned=False,
            primitives=(
                NativePrimitiveInfo(
                    first_index=0,
                    index_count=36,
                    material_index=0,
                    material_slot=0,
                ),
            ),
        ),
    )

    raw = document.build_mesh(0, "pytest-native-box-raw", convert_to_z_up=False)
    converted = document.build_mesh(0, "pytest-native-box-z-up", convert_to_z_up=True)

    assert raw.vertex_count == converted.vertex_count == 24
    assert raw.index_count == converted.index_count == 36
    assert raw.submesh_count == converted.submesh_count == 1
    assert raw.stride == converted.stride == 24
    assert raw.submeshes[0].name == "Mesh/Red"

    raw_vertices = np.asarray(raw.mesh.get_vertices_buffer()).reshape(24, 6)
    converted_vertices = np.asarray(converted.mesh.get_vertices_buffer()).reshape(24, 6)
    np.testing.assert_array_equal(converted_vertices[:, 0], raw_vertices[:, 0])
    np.testing.assert_array_equal(converted_vertices[:, 1], -raw_vertices[:, 2])
    np.testing.assert_array_equal(converted_vertices[:, 2], raw_vertices[:, 1])
    np.testing.assert_array_equal(converted_vertices[:, 3], raw_vertices[:, 3])
    np.testing.assert_array_equal(converted_vertices[:, 4], -raw_vertices[:, 5])
    np.testing.assert_array_equal(converted_vertices[:, 5], raw_vertices[:, 4])


def test_native_document_errors_include_source_path(tmp_path):
    source = _FIXTURES / "Box.glb"
    truncated = tmp_path / "truncated.glb"
    truncated.write_bytes(source.read_bytes()[:32])

    with pytest.raises(RuntimeError, match="truncated\\.glb"):
        NativeStaticMeshDocument(truncated)

    with pytest.raises(RuntimeError, match="binary GLB only"):
        NativeStaticMeshDocument(_FIXTURES / "TriangleWithoutIndices.gltf")


def test_native_document_repeated_mapping_lifetime():
    for _ in range(64):
        document = NativeStaticMeshDocument(_FIXTURES / "Box.glb")
        assert document.meshes[0].vertex_count == 24
        del document
    gc.collect()


@pytest.mark.parametrize("component_type", [5121, 5123, 5125, None])
def test_native_static_mesh_supports_index_widths_nonindexed_and_stride(tmp_path, component_type):
    # This position-only fixture is deliberately collinear: no direction
    # generation is requested, so geometric degeneracy remains accepted.
    path = _write_indexed_triangle_glb(tmp_path / f"triangle-{component_type}.glb", component_type)
    document = NativeStaticMeshDocument(path)
    mesh = document.build_mesh(
        0,
        f"pytest-native-index-{component_type}",
        convert_to_z_up=True,
    )

    assert (mesh.vertex_count, mesh.index_count, mesh.stride) == (3, 3, 12)
    np.testing.assert_array_equal(np.asarray(mesh.mesh.get_indices_buffer()), [0, 1, 2])
    vertices = np.asarray(mesh.mesh.get_vertices_buffer()).reshape(3, 3)
    np.testing.assert_array_equal(
        vertices[:, :3],
        [[1.0, -3.0, 2.0], [4.0, -6.0, 5.0], [7.0, -9.0, 8.0]],
    )


def test_native_static_mesh_reads_sparse_position_accessor(tmp_path):
    document = NativeStaticMeshDocument(_write_sparse_triangle_glb(tmp_path / "sparse.glb"))
    mesh = document.build_mesh(0, "pytest-native-sparse", convert_to_z_up=False)

    vertices = np.asarray(mesh.mesh.get_vertices_buffer()).reshape(3, 3)
    np.testing.assert_array_equal(
        vertices[:, :3],
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],
    )


def test_native_static_mesh_decodes_normalized_attributes_and_tangents(tmp_path):
    path = _write_normalized_tangent_glb(tmp_path / "normalized-tangent.glb")
    mesh = NativeStaticMeshDocument(path).build_mesh(
        0,
        "pytest-native-normalized-tangent",
        convert_to_z_up=False,
    )

    assert mesh.stride == 48
    vertices = np.asarray(mesh.mesh.get_vertices_buffer()).reshape(3, 12)
    half = np.sqrt(0.5)
    np.testing.assert_allclose(vertices[:, 3:6], [[half, 0.0, -half]] * 3, atol=1e-6)
    np.testing.assert_allclose(vertices[:, 6:8], [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    np.testing.assert_allclose(vertices[:, 8:11], [[1.0, 0.0, 0.0]] * 3)
    np.testing.assert_allclose(vertices[:, 11], [1.0, 1.0, -1.0])


@pytest.mark.parametrize("mirrored_uv", [False, True])
def test_native_static_mesh_generates_pbr_tangents_when_uvs_are_present(tmp_path, mirrored_uv):
    path = _write_normalized_tangent_glb(
        tmp_path / "generated-tangent.glb",
        include_tangent=False,
        mirrored_uv=mirrored_uv,
    )
    mesh = NativeStaticMeshDocument(path).build_mesh(
        0,
        "pytest-native-generated-tangent",
        convert_to_z_up=False,
    )

    assert mesh.stride == 48
    vertices = np.asarray(mesh.mesh.get_vertices_buffer()).reshape(3, 12)
    half = np.sqrt(0.5)
    np.testing.assert_allclose(vertices[:, 3:6], [[half, 0.0, -half]] * 3, atol=1e-6)
    np.testing.assert_allclose(vertices[:, 8:11], [[half, 0.0, half]] * 3, atol=1e-6)
    np.testing.assert_allclose(np.linalg.norm(vertices[:, 3:6], axis=1), 1.0, atol=1e-6)
    np.testing.assert_allclose(np.linalg.norm(vertices[:, 8:11], axis=1), 1.0, atol=1e-6)
    np.testing.assert_allclose(np.sum(vertices[:, 3:6] * vertices[:, 8:11], axis=1), 0.0, atol=1e-6)
    np.testing.assert_allclose(vertices[:, 11], [1.0 if mirrored_uv else -1.0] * 3)


@pytest.mark.parametrize("skinned", [False, True])
@pytest.mark.parametrize(
    "normal,tangent",
    [
        ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0, -1.0)),
        ((1.0, 0.0, -1.0), (8.0, 0.0, 0.0, 1.0)),
        ((1e38, 1e38, -1e38), (1e38, -1e38, 1e38, -1.0)),
    ],
    ids=["unit", "nonunit", "large-finite"],
)
def test_native_mesh_normalizes_authored_directions_for_static_and_skinned_ingress(
    tmp_path, skinned, normal, tangent
):
    path = _write_directional_triangle_glb(
        tmp_path / "authored-directions.glb", normals=(normal,) * 3,
        tangents=(tangent,) * 3, skinned=skinned,
    )
    mesh = NativeStaticMeshDocument(path).build_mesh(0, str(uuid.uuid4()), convert_to_z_up=False)
    assert mesh.stride == (80 if skinned else 48)
    vertices = np.asarray(mesh.mesh.get_vertices_buffer()).reshape(3, mesh.stride // 4)
    expected_normal = np.asarray(normal, dtype=np.float64)
    expected_normal /= np.linalg.norm(expected_normal)
    expected_tangent = np.asarray(tangent[:3], dtype=np.float64)
    expected_tangent /= np.linalg.norm(expected_tangent)
    np.testing.assert_allclose(vertices[:, 3:6], [expected_normal] * 3, atol=1e-6)
    # Authored directions are normalized, preserving their orientation rather
    # than applying the generated-tangent Gram-Schmidt policy.
    np.testing.assert_allclose(vertices[:, 8:11], [expected_tangent] * 3, atol=1e-6)
    np.testing.assert_allclose(vertices[:, 11], [tangent[3]] * 3)


@pytest.mark.parametrize("convert_to_z_up", [False, True])
def test_native_static_mesh_generates_unit_normals_and_tangents(tmp_path, convert_to_z_up):
    path = _write_directional_triangle_glb(
        tmp_path / "generated-directions.glb", normals=None,
        positions=((0.0, 0.0, 0.0), (8.0, 0.0, 0.0), (0.0, 3.0, 0.0)),
    )
    mesh = NativeStaticMeshDocument(path).build_mesh(
        0, str(uuid.uuid4()), convert_to_z_up=convert_to_z_up
    )
    vertices = np.asarray(mesh.mesh.get_vertices_buffer()).reshape(3, 12)
    normal = (0.0, -1.0, 0.0) if convert_to_z_up else (0.0, 0.0, 1.0)
    np.testing.assert_allclose(vertices[:, 3:6], [normal] * 3, atol=1e-6)
    np.testing.assert_allclose(vertices[:, 8:11], [[1.0, 0.0, 0.0]] * 3, atol=1e-6)
    np.testing.assert_allclose(vertices[:, 11], 1.0)


def test_native_static_mesh_skips_zero_uv_triangle_when_valid_neighbors_cover_every_vertex(tmp_path):
    path = _write_directional_triangle_glb(
        tmp_path / "mixed-uv.glb",
        positions=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        normals=((0.0, 0.0, 1.0),) * 4,
        uvs=((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (0.0, 1.0)),
        indices=(0, 1, 2, 0, 1, 3, 0, 2, 3),
    )
    mesh = NativeStaticMeshDocument(path).build_mesh(0, str(uuid.uuid4()), convert_to_z_up=False)
    vertices = np.asarray(mesh.mesh.get_vertices_buffer()).reshape(4, 12)
    diagonal = np.sqrt(0.5)
    combined = (3 / np.sqrt(10), 1 / np.sqrt(10), 0.0)
    np.testing.assert_allclose(
        vertices[:, 8:11], [combined, (1.0, 0.0, 0.0), (diagonal, diagonal, 0.0), combined], atol=1e-6
    )
    np.testing.assert_allclose(vertices[:, 11], 1.0)


def test_native_skinned_mesh_keeps_missing_tangent_generation_policy(tmp_path):
    path = _write_directional_triangle_glb(tmp_path / "skinned-no-tangent.glb", skinned=True)
    mesh = NativeStaticMeshDocument(path).build_mesh(0, str(uuid.uuid4()), convert_to_z_up=False)
    assert mesh.stride == 80
    vertices = np.asarray(mesh.mesh.get_vertices_buffer()).reshape(3, 20)
    np.testing.assert_array_equal(vertices[:, 8:12], np.zeros((3, 4)))


@pytest.mark.parametrize("skinned", [False, True])
@pytest.mark.parametrize(
    "field,semantic,bad_value",
    [
        ("positions", "POSITION", (float("nan"), 0.0, 0.0)),
        ("positions", "POSITION", (float("inf"), 0.0, 0.0)),
        ("normals", "NORMAL", (0.0, 0.0, 0.0)),
        ("normals", "NORMAL", (float("nan"), 0.0, 1.0)),
        ("normals", "NORMAL", (float("inf"), 0.0, 1.0)),
        ("uvs", "TEXCOORD_0", (float("nan"), 0.0)),
        ("uvs", "TEXCOORD_0", (0.0, float("inf"))),
        ("tangents", "TANGENT", (0.0, 0.0, 0.0, 1.0)),
        ("tangents", "TANGENT", (float("nan"), 0.0, 0.0, 1.0)),
        ("tangents", "TANGENT", (float("inf"), 0.0, 0.0, 1.0)),
        ("tangents", "TANGENT", (1.0, 0.0, 0.0, 0.0)),
        ("tangents", "TANGENT", (1.0, 0.0, 0.0, float("nan"))),
        ("tangents", "TANGENT", (1.0, 0.0, 0.0, float("inf"))),
    ],
)
def test_native_mesh_rejects_invalid_authored_attributes_without_partial_publication(
    tmp_path, skinned, field, semantic, bad_value
):
    attributes = {
        "positions": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        "normals": [(0.0, 0.0, 1.0)] * 3,
        "uvs": [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        "tangents": [(1.0, 0.0, 0.0, 1.0)] * 3,
    }
    attributes[field][2] = bad_value
    path = _write_directional_triangle_glb(tmp_path / "invalid-authored.glb", skinned=skinned, **attributes)
    _assert_direction_build_rejected_without_publication(path, semantic, "vertex[2]")


@pytest.mark.parametrize("skinned", [False, True])
@pytest.mark.parametrize(
    "field,semantic,bad_shape",
    [
        ("normals", "NORMAL", (0.0, 0.0, 1.0, 1.0)),
        ("uvs", "TEXCOORD_0", (0.0, 0.0, 0.0)),
        ("tangents", "TANGENT", (1.0, 0.0, 0.0)),
    ],
)
def test_native_mesh_rejects_malformed_direction_accessors_with_context(
    tmp_path, skinned, field, semantic, bad_shape
):
    path = _write_directional_triangle_glb(
        tmp_path / "malformed-direction.glb", skinned=skinned, **{field: (bad_shape,) * 3}
    )
    _assert_direction_build_rejected_without_publication(path, semantic, "accessor")


@pytest.mark.parametrize(
    "settings,semantic,location",
    [
        ({"normals": None, "positions": ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0))}, "generated NORMAL", "vertex["),
        ({"normals": None, "positions": ((0.0, 0.0, 0.0), (1e20, 0.0, 0.0), (0.0, 1e20, 0.0))}, "generated NORMAL", "triangle["),
        ({"positions": ((-3e38, 0.0, 0.0), (3e38, 0.0, 0.0), (0.0, 1.0, 0.0))}, "generated TANGENT", "triangle["),
        ({"uvs": ((0.0, 0.0), (3e38, 0.0), (0.0, 3e38))}, "generated TANGENT", "triangle["),
        ({"uvs": ((-3e38, 0.0), (3e38, 0.0), (-3e38, 1.0))}, "generated TANGENT", "triangle["),
        ({"positions": ((0.0, 0.0, 0.0), (3e38, 0.0, 0.0), (0.0, 1.0, 0.0)), "indices": (0, 1, 2, 0, 1, 2)}, "generated TANGENT", "triangle["),
        ({"positions": ((0.0, 0.0, 0.0), (3e38, 3e38, 0.0), (0.0, 0.0, 1.0)), "normals": ((1.0, 1.0, 1.0),) * 3}, "generated TANGENT", "vertex["),
        ({"normals": ((1.0, 0.0, 0.0),) * 3}, "generated TANGENT", "vertex["),
        ({"normals": ((0.0, 1.0, 0.0),) * 3}, "generated TANGENT", "vertex["),
        ({"uvs": ((0.0, 0.0),) * 3}, "generated TANGENT", "vertex["),
    ],
    ids=["zero-normal", "cross-overflow", "edge-overflow", "uv-determinant-overflow", "uv-edge-overflow", "accumulation-overflow", "projection-overflow", "parallel-tangent", "degenerate-handedness", "unsupported-uv"],
)
def test_native_static_mesh_rejects_invalid_generated_directions_transactionally(
    tmp_path, settings, semantic, location
):
    path = _write_directional_triangle_glb(tmp_path / "invalid-generated.glb", **settings)
    _assert_direction_build_rejected_without_publication(path, semantic, location)


def test_native_static_mesh_preserves_primitive_sections_and_material_slots(tmp_path):
    path = _write_multi_primitive_glb(tmp_path / "multi.glb")
    document = NativeStaticMeshDocument(path)
    assert document.meshes[0].primitive_count == 2
    assert [primitive.material_index for primitive in document.meshes[0].primitives] == [0, 1]
    assert [primitive.material_slot for primitive in document.meshes[0].primitives] == [0, 1]
    assert [primitive.first_index for primitive in document.meshes[0].primitives] == [0, 3]
    mesh = document.build_mesh(0, "pytest-native-multi", convert_to_z_up=False)

    assert (mesh.vertex_count, mesh.index_count, mesh.submesh_count) == (6, 6, 2)
    np.testing.assert_array_equal(np.asarray(mesh.mesh.get_indices_buffer()), [0, 1, 2, 3, 4, 5])
    assert [section.material_slot for section in mesh.submeshes] == [0, 1]
    assert [section.name for section in mesh.submeshes] == ["Multi/First", "Multi/Second"]


def test_native_static_mesh_reports_context_for_out_of_range_index(tmp_path):
    path = _write_indexed_triangle_glb(
        tmp_path / "invalid-index.glb",
        5121,
        indices=(0, 1, 9),
    )
    with pytest.raises(
        RuntimeError,
        match=r"invalid-index\.glb: mesh\[0\] primitive\[0\] INDICES accessor index\[2\]=9",
    ):
        NativeStaticMeshDocument(path)


def test_native_material_texture_discovery_selects_webp_and_preserves_sampler(tmp_path):
    path = _write_material_texture_glb(tmp_path / "materials.glb")
    document = NativeStaticMeshDocument(path)

    assert [image.encoded_size for image in document.images] == [12, 13]
    assert document.image_payload(0) == b"PNG-fallback"
    assert document.image_payload(1) == b"WEBP-selected"
    assert document.textures[0].image_index == 1
    assert document.textures[0].selected_webp
    assert (
        document.textures[0].mag_filter,
        document.textures[0].min_filter,
        document.textures[0].wrap_s,
        document.textures[0].wrap_t,
    ) == (9728, 9987, 33071, 33648)
    assert document.textures[1].sampler_index is None
    assert (
        document.textures[1].mag_filter,
        document.textures[1].min_filter,
        document.textures[1].wrap_s,
        document.textures[1].wrap_t,
    ) == (9729, 9729, 10497, 10497)

    material = document.materials[0]
    assert material.base_color_factor == pytest.approx((0.1, 0.2, 0.3, 0.4))
    assert (material.metallic_factor, material.roughness_factor) == pytest.approx((0.6, 0.7))
    assert material.base_color_texture.texture_index == 0
    assert material.normal_texture.scale == pytest.approx(0.8)
    assert material.occlusion_texture.scale == pytest.approx(0.9)
    assert material.alpha_mode == 1
    assert material.alpha_cutoff == pytest.approx(0.25)
    assert material.double_sided

    materials, textures = document.build_material_texture_data()
    assert textures[0].data == b"WEBP-selected"
    assert textures[0].name == "SelectedWebP"
    assert textures[0].image_index == 1
    assert textures[0].sampler == {
        "magFilter": 9728,
        "minFilter": 9987,
        "wrapS": 33071,
        "wrapT": 33648,
    }
    assert materials[0].base_color_texture == 0
    assert materials[0].occlusion_strength == pytest.approx(0.9)


def test_native_material_bridge_rejects_texture_transform(tmp_path):
    path = _write_material_texture_glb(tmp_path / "texture-transform.glb", texture_transform=True)
    document = NativeStaticMeshDocument(path)

    assert document.materials[0].base_color_texture.has_transform
    with pytest.raises(RuntimeError, match="KHR_texture_transform"):
        document.build_material_texture_data()


def test_native_document_rejects_unknown_required_extension(tmp_path):
    path = tmp_path / "required-extension.glb"
    positions = struct.pack(
        "<12f",
        1.0,
        2.0,
        3.0,
        99.0,
        4.0,
        5.0,
        6.0,
        99.0,
        7.0,
        8.0,
        9.0,
        99.0,
    )
    _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "extensionsRequired": ["VENDOR_not_supported"],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(positions), "byteStride": 16}
            ],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}
            ],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "mode": 4}]}],
        },
        positions,
    )
    with pytest.raises(RuntimeError, match="VENDOR_not_supported"):
        NativeStaticMeshDocument(path)


def test_native_document_rejects_required_basisu_without_ktx2_decoder(tmp_path):
    path = tmp_path / "required-basisu.glb"
    _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "extensionsUsed": ["KHR_texture_basisu"],
            "extensionsRequired": ["KHR_texture_basisu"],
        },
        b"",
    )

    with pytest.raises(RuntimeError, match="KHR_texture_basisu"):
        NativeStaticMeshDocument(path)


def test_native_document_ignores_optional_basisu_and_uses_core_fallback(tmp_path):
    path = tmp_path / "optional-basisu.glb"
    fallback = b"PNG-fallback"
    basisu = b"KTX2-unsupported"
    _write_glb(
        path,
        {
            "asset": {"version": "2.0"},
            "extensionsUsed": ["KHR_texture_basisu"],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": len(fallback)},
                {
                    "buffer": 0,
                    "byteOffset": len(fallback),
                    "byteLength": len(basisu),
                },
            ],
            "images": [
                {"name": "Fallback", "mimeType": "image/png", "bufferView": 0},
                {"name": "BasisU", "mimeType": "image/ktx2", "bufferView": 1},
            ],
            "textures": [
                {
                    "source": 0,
                    "extensions": {"KHR_texture_basisu": {"source": 1}},
                }
            ],
        },
        fallback + basisu,
    )

    document = NativeStaticMeshDocument(path)

    assert document.textures[0].image_index == 0
    assert not document.textures[0].selected_basisu
    assert document.image_payload(document.textures[0].image_index) == fallback


def test_native_animation_bridge_preserves_step_vec3_scale_and_node_index(tmp_path):
    path = _write_bulk_animation_glb(tmp_path / "bulk-animation.glb")
    document = NativeStaticMeshDocument(path)

    clip = document.build_animation_clip(
        0,
        "pytest-native-glb-bulk-animation",
        convert_to_z_up=True,
    )

    assert clip.name == "ExactTracks"
    assert clip.track_count == 2
    assert clip.tracks[0]["target_node_index"] == 0
    assert clip.tracks[0]["interpolation"] == "step"
    assert tuple(clip.sample_track(0, 0.5)) == pytest.approx([1.0, -3.0, 2.0])
    assert tuple(clip.sample_track(1, 0.5)) == pytest.approx([2.0, 6.0, 4.0])


def test_native_skin_keeps_column_major_inverse_bind_storage(tmp_path):
    path = _write_column_major_skin_glb(tmp_path / "column-major-skin.glb")
    document = NativeStaticMeshDocument(path)

    rig = document.rig_data()
    raw_matrix = np.frombuffer(
        rig["skins"][0]["inverse_bind_matrices"], dtype=np.float32
    )
    assert raw_matrix[12:15] == pytest.approx((-2.0, -3.0, -4.0))

    skeleton = document.build_skeleton(
        0,
        "pytest-native-column-major-skeleton",
        convert_to_z_up=False,
    )
    inverse_bind_matrix = skeleton.bones[0]["inverse_bind_matrix"]
    assert isinstance(inverse_bind_matrix, Mat44)
    assert (
        inverse_bind_matrix[3, 0],
        inverse_bind_matrix[3, 1],
        inverse_bind_matrix[3, 2],
    ) == pytest.approx((-2.0, -3.0, -4.0))


def _write_node_rotation_glb(path, magnitude=1.0):
    directions = np.asarray([[1.0, 2.0, 3.0, 4.0], [-4.0, 3.0, -2.0, 1.0]])
    return _write_glb(path, {
        "asset": {"version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [
            {"name": "Root", "children": [1], "rotation": (directions[0] * magnitude).tolist()},
            {"name": "Joint", "rotation": (directions[1] * magnitude).tolist()},
        ],
        "skins": [{"joints": [1]}],
    }, b"")


@pytest.mark.parametrize("magnitude", [2.0 ** -149, 1.0e-30, 7.0, 2.5e37])
@pytest.mark.parametrize("convert_to_z_up,blender_z_up_fix", [
    (False, False), (True, False), (False, True), (True, True),
])
def test_native_authored_rotations_normalize_before_pose_corrections(
    tmp_path, magnitude, convert_to_z_up, blender_z_up_fix,
):
    flags = {"convert_to_z_up": convert_to_z_up, "blender_z_up_fix": blender_z_up_fix}
    actual = NativeStaticMeshDocument(
        _write_node_rotation_glb(tmp_path / "scaled.glb", magnitude),
    ).prepared_rig_data(**flags)
    expected = NativeStaticMeshDocument(
        _write_node_rotation_glb(tmp_path / "unit-direction.glb"),
    ).prepared_rig_data(**flags)

    for actual_node, expected_node in zip(actual["nodes"], expected["nodes"], strict=True):
        assert np.isfinite(actual_node["rotation"]).all()
        assert np.linalg.norm(actual_node["rotation"]) == pytest.approx(1.0, abs=1e-6)
        np.testing.assert_allclose(actual_node["rotation"], expected_node["rotation"], atol=1e-6)


@pytest.mark.parametrize("magnitude", [5.0e-324, 1.0e-300, 1.0e300, 2.5e307])
def test_native_python_rig_ingress_preserves_finite_double_extremes(tmp_path, monkeypatch, magnitude):
    document = NativeStaticMeshDocument(_write_node_rotation_glb(tmp_path / "double-ingress.glb"))
    rig = copy.deepcopy(document.rig_data())
    for node in rig["nodes"]:
        node["rotation"] = (np.asarray(node["rotation"]) * magnitude).tolist()
    monkeypatch.setattr(document, "rig_data", lambda: rig)

    prepared = document.prepared_rig_data(convert_to_z_up=False)

    directions = np.asarray([[1.0, 2.0, 3.0, 4.0], [-4.0, 3.0, -2.0, 1.0]])
    for node, direction in zip(prepared["nodes"], directions, strict=True):
        assert np.isfinite(node["rotation"]).all()
        np.testing.assert_allclose(node["rotation"], direction / np.linalg.norm(direction), atol=1e-12)


@pytest.mark.parametrize("rotation", [
    [0.0, 0.0, 0.0, 0.0], [float("nan"), 0.0, 0.0, 1.0],
    [0.0, float("inf"), 0.0, 1.0], [0.0, 0.0, -float("inf"), 1.0],
])
def test_native_invalid_later_rotation_preserves_raw_rig_and_prepared_cache(
    tmp_path, monkeypatch, rotation,
):
    path = _write_node_rotation_glb(tmp_path / "invalid-rotation.glb")
    document = NativeStaticMeshDocument(path)
    raw = document.rig_data()
    retained = document.prepared_rig_data(convert_to_z_up=False)
    retained_rotations = [node["rotation"].copy() for node in retained["nodes"]]
    raw_rotations = [tuple(node["rotation"]) for node in raw["nodes"]]
    keys_before = set(document._prepared_rigs)
    incoming = copy.deepcopy(raw)
    broken = copy.deepcopy(incoming["nodes"][1])
    broken.update(name="Broken", rotation=rotation, parent_index=None, default_scene_root=False)
    incoming["nodes"].append(broken)
    monkeypatch.setattr(document, "rig_data", lambda: incoming)
    messages = []
    monkeypatch.setattr(log, "error", lambda message, **_: messages.append(message))

    with pytest.raises(ValueError, match="node 2.*Broken"):
        document.prepared_rig_data(convert_to_z_up=True, blender_z_up_fix=True)

    assert set(document._prepared_rigs) == keys_before
    assert document.prepared_rig_data(convert_to_z_up=False) is retained
    assert [tuple(node["rotation"]) for node in raw["nodes"]] == raw_rotations
    for node, expected in zip(retained["nodes"], retained_rotations, strict=True):
        np.testing.assert_array_equal(node["rotation"], expected)
    assert any(str(path) in message and "node 2" in message and "Broken" in message for message in messages)

    incoming["nodes"][2]["rotation"] = [0.0, 0.0, 0.0, 2.0]
    recovered = document.prepared_rig_data(convert_to_z_up=True, blender_z_up_fix=True)
    assert len(recovered["nodes"]) == 3
    np.testing.assert_array_equal(recovered["nodes"][2]["rotation"], [0.0, 0.0, 0.0, 1.0])


@pytest.mark.parametrize("scale", [
    [-2.0, 3.0, 4.0],
    [0.0, 3.0, 4.0], [2.0, 0.0, 4.0], [2.0, 3.0, 0.0],
    [2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0],
    [0.0, 0.0, 0.0],
])
def test_native_matrix_rotation_reconstructs_reflection_and_every_deficient_rank(tmp_path, scale):
    rotation = np.asarray([
        [2.0 / 15.0, -2.0 / 3.0, 11.0 / 15.0],
        [14.0 / 15.0, 1.0 / 3.0, 2.0 / 15.0],
        [-1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0],
    ])
    authored = np.eye(4)
    authored[:3, :3] = rotation @ np.diag(scale)
    authored[:3, 3] = [4.0, 5.0, 6.0]
    path = _write_glb(tmp_path / "matrix-rank.glb", {
        "asset": {"version": "2.0"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"matrix": authored.T.reshape(-1).tolist()}],
    }, b"")
    first = NativeStaticMeshDocument(path).prepared_rig_data(convert_to_z_up=False)["nodes"][0]
    second = NativeStaticMeshDocument(path).prepared_rig_data(convert_to_z_up=False)["nodes"][0]
    x, y, z, w = first["rotation"]
    restored_rotation = np.asarray([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])

    assert np.linalg.norm(first["rotation"]) == pytest.approx(1.0, abs=1e-6)
    np.testing.assert_allclose(restored_rotation @ np.diag(first["scale"]), authored[:3, :3], atol=1e-5)
    np.testing.assert_allclose(first["translation"], authored[:3, 3])
    np.testing.assert_array_equal(first["rotation"], second["rotation"])
    np.testing.assert_array_equal(first["scale"], second["scale"])


def test_glb_asset_default_cgltf_backend_publishes_children_and_node_targets(
    tmp_path, monkeypatch
):
    import termin_assets

    class _Material:
        is_valid = True

    class _InstantiationResourceManager:
        def get_material(self, name):
            assert name == "CookTorrancePBR"
            return _Material()

        def list_runtime_asset_names(self, asset_type):
            assert asset_type == "texture"
            return []

    DefaultResourceManager._reset_for_testing()
    resource_manager = DefaultResourceManager.instance()
    path = _write_production_native_glb(tmp_path / "production-native.glb")
    asset = GLBAsset(name="production-native", source_path=path)
    asset.set_resource_manager(resource_manager)
    asset.parse_spec(
        {
            "uuid": "pytest-production-native-glb",
            "convert_to_z_up": False,
            "normalize_scale": True,
        }
    )

    assert asset.ensure_loaded()
    assert isinstance(asset.scene_data, NativeGLBSceneData)
    assert list(asset.get_mesh_assets()) == ["Body"]
    assert asset.get_mesh_assets()["Body"].data.is_valid
    assert asset.scene_data.meshes[0].submeshes[0].material_index == -1
    assert list(asset.get_animation_assets()) == ["Move"]
    clip = asset.get_animation_assets()["Move"].clip
    assert clip.track_count == 1
    assert clip.tracks[0]["target_node_index"] == 1
    assert clip.tracks[0]["interpolation"] == "step"
    assert tuple(clip.sample_track(0, 1.0)) == pytest.approx((4.0, 6.0, 8.0))

    monkeypatch.setattr(
        termin_assets,
        "get_resource_manager",
        lambda: _InstantiationResourceManager(),
    )
    result = instantiate_glb(asset, name="Model")

    imported_root = result.entity.transform.children[0].entity
    animated = imported_root.transform.children[0].entity
    assert imported_root.name == "Root"
    assert tuple(imported_root.transform.local_scale()) == pytest.approx((1.0, 1.0, 1.0))
    assert animated.name == "Animated"
    assert tuple(animated.transform.local_position()) == pytest.approx((2.0, 0.0, 0.0))
    assert result.animation_player is not None
    assert result.animation_player.node_targets[1].name == "Animated"
    assert result.animation_player.node_targets[2] is None


def test_glb_asset_cgltf_backend_rejects_duplicate_animation_names(tmp_path):
    path = _write_production_native_glb(
        tmp_path / "duplicate-animation.glb", duplicate_animation_name=True
    )
    document = NativeStaticMeshDocument(path)

    with pytest.raises(
        RuntimeError,
        match=r"duplicate-animation\.glb: duplicate animation names.*'Move'",
    ):
        NativeGLBSceneData(
            document,
            convert_to_z_up=False,
            blender_z_up_fix=False,
            normalize_scale=False,
        )


def test_glb_asset_default_cgltf_failure_never_falls_back_to_python(
    tmp_path, monkeypatch
):
    import termin.glb.loader as legacy_loader

    path = tmp_path / "malformed.glb"
    path.write_bytes(b"not a GLB")
    legacy_called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal legacy_called
        legacy_called = True
        raise AssertionError("legacy GLB loader must not be called")

    monkeypatch.setattr(legacy_loader, "load_glb_file_from_buffer", fail_if_called)
    monkeypatch.setattr(legacy_loader, "load_glb_file_normalized", fail_if_called)
    asset = GLBAsset(name="malformed", source_path=path)

    assert not asset.ensure_loaded()
    assert not legacy_called
