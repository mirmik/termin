import json
from pathlib import Path
import struct
import subprocess
import sys
import uuid

import numpy as np
import pytest

from termin.animation import clip_from_glb
from termin.geombase import Quat
from termin.glb import (
    GLBAnimationClip, GLBAnimationTrack, GLBNodeData, GLBSceneData, GLBSkinData,
    NativeStaticMeshDocument,
)
from termin.glb.loader import (
    _qmul,
    apply_blender_z_up_fix,
    convert_y_up_to_z_up,
    load_glb_file,
    load_glb_file_normalized,
    normalize_glb_scale,
)


def _write_exact_animation_gltf(path: Path) -> Path:
    chunks: list[bytes] = []

    def floats(*values: float) -> int:
        chunks.append(struct.pack(f"<{len(values)}f", *values))
        return len(chunks) - 1

    position = floats(0.0, 0.0, 0.0)
    morph_a = floats(0.0, 0.0, 0.0)
    morph_b = floats(0.0, 0.0, 0.0)
    times = floats(0.0, 1.0)
    translation = floats(1.0, 2.0, 3.0, 7.0, 8.0, 9.0)
    scale = floats(1.0, 2.0, 3.0, 3.0, 6.0, 9.0)
    cubic_rotation = floats(
        2.0,
        3.0,
        4.0,
        5.0,
        0.0,
        0.0,
        0.0,
        1.0,
        6.0,
        7.0,
        8.0,
        9.0,
        -2.0,
        -3.0,
        -4.0,
        -5.0,
        0.0,
        0.0,
        1.0,
        0.0,
        -6.0,
        -7.0,
        -8.0,
        -9.0,
    )
    cubic_weights = floats(
        0.0,
        0.0,
        0.25,
        0.75,
        0.1,
        -0.1,
        0.2,
        -0.2,
        0.6,
        0.4,
        0.0,
        0.0,
    )

    offsets = []
    payload = b""
    for chunk in chunks:
        offsets.append(len(payload))
        payload += chunk
    buffer_views = [
        {"buffer": 0, "byteOffset": offset, "byteLength": len(chunk)}
        for offset, chunk in zip(offsets, chunks, strict=True)
    ]
    accessors = [
        {"bufferView": position, "componentType": 5126, "count": 1, "type": "VEC3"},
        {"bufferView": morph_a, "componentType": 5126, "count": 1, "type": "VEC3"},
        {"bufferView": morph_b, "componentType": 5126, "count": 1, "type": "VEC3"},
        {"bufferView": times, "componentType": 5126, "count": 2, "type": "SCALAR"},
        {"bufferView": translation, "componentType": 5126, "count": 2, "type": "VEC3"},
        {"bufferView": scale, "componentType": 5126, "count": 2, "type": "VEC3"},
        {"bufferView": cubic_rotation, "componentType": 5126, "count": 6, "type": "VEC4"},
        {"bufferView": cubic_weights, "componentType": 5126, "count": 12, "type": "SCALAR"},
    ]
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "Animated", "mesh": 0}],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "targets": [{"POSITION": 1}, {"POSITION": 2}],
                    }
                ]
            }
        ],
        "animations": [
            {
                "name": "ExactPortable",
                "samplers": [
                    {"input": 3, "output": 4, "interpolation": "STEP"},
                    {"input": 3, "output": 5, "interpolation": "LINEAR"},
                    {"input": 3, "output": 6, "interpolation": "CUBICSPLINE"},
                    {"input": 3, "output": 7, "interpolation": "CUBICSPLINE"},
                ],
                "channels": [
                    {"sampler": 0, "target": {"node": 0, "path": "translation"}},
                    {"sampler": 1, "target": {"node": 0, "path": "scale"}},
                    {"sampler": 2, "target": {"node": 0, "path": "rotation"}},
                    {"sampler": 3, "target": {"node": 0, "path": "weights"}},
                ],
            }
        ],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"uri": "exact-animation.bin", "byteLength": len(payload)}],
    }
    (path.parent / "exact-animation.bin").write_bytes(payload)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_portable_gltf_preserves_exact_tracks_and_publishes_bulk_payload(tmp_path) -> None:
    scene = load_glb_file(_write_exact_animation_gltf(tmp_path / "exact-animation.gltf"))

    assert len(scene.animations) == 1
    source_clip = scene.animations[0]
    assert source_clip.name == "ExactPortable"
    assert source_clip.duration == pytest.approx(1.0)
    assert [(track.path, track.interpolation, track.components) for track in source_clip.tracks] == [
        ("translation", "step", 3),
        ("scale", "linear", 3),
        ("rotation", "cubic_spline", 4),
        ("weights", "cubic_spline", 2),
    ]
    np.testing.assert_array_equal(source_clip.tracks[1].values, [[1, 2, 3], [3, 6, 9]])
    assert source_clip.tracks[2].values.shape == (6, 4)
    np.testing.assert_array_equal(
        source_clip.tracks[2].values[:, 3],
        [5, 1, 9, -5, 0, -9],
    )
    np.testing.assert_allclose(
        source_clip.tracks[3].values,
        [[0.0, 0.0], [0.25, 0.75], [0.1, -0.1], [0.2, -0.2], [0.6, 0.4], [0.0, 0.0]],
    )

    clip = clip_from_glb(source_clip, str(uuid.uuid4()))

    assert clip.channel_count == 0
    assert clip.track_count == 4
    assert clip.tracks[0]["target_node_index"] == 0
    assert clip.tracks[0]["interpolation"] == "step"
    assert clip.tracks[1]["values"] == pytest.approx([1, 2, 3, 3, 6, 9])
    assert clip.tracks[2]["values"] == pytest.approx(source_clip.tracks[2].values.reshape(-1))
    assert clip.tracks[3]["components"] == 2
    assert clip.tracks[3]["interpolation"] == "cubic_spline"
    assert clip.tracks[3]["values"] == pytest.approx(source_clip.tracks[3].values.reshape(-1))
    assert tuple(clip.sample_track(0, 0.5)) == pytest.approx([1, 2, 3])
    assert tuple(clip.sample_track(1, 0.5)) == pytest.approx([2, 4, 6])
    with pytest.raises(RuntimeError, match="unsupported"):
        clip.sample_track(3, 0.5)


def test_extracted_tanim_reconstructs_exact_gltf_tracks_in_fresh_process(tmp_path) -> None:
    from termin.glb.extractor import extract_animations

    source = _write_exact_animation_gltf(tmp_path / "exact-animation.gltf")
    scene = load_glb_file(source)
    expected_tracks = [{
        "target_node_index": track.node_index,
        "path": track.path,
        "interpolation": track.interpolation,
        "components": track.components,
        "times": track.times.tolist(),
        "values": track.values.reshape(-1).tolist(),
    } for track in scene.animations[0].tracks]

    paths = extract_animations(source, tmp_path / "extracted", scene)

    assert len(paths) == 1
    assert paths[0].name == "ExactPortable.tanim"
    document = json.loads(paths[0].read_text(encoding="utf-8"))
    assert document["format"] == "termin.animation"
    assert document["version"] == 1
    assert document["tracks"] == expected_tracks
    result = subprocess.run(
        [sys.executable, "-c", """
import json
import sys
from termin.animation import TcAnimationClip, load_animation_clip
assert not TcAnimationClip.from_uuid(sys.argv[2]).is_valid
clip = load_animation_clip(sys.argv[1])
print(json.dumps({
    "name": clip.name, "tps": clip.tps, "loop": clip.loop,
    "tracks": clip.tracks, "duration": clip.duration,
    "step": list(clip.sample_track(0, 0.5)),
    "scale": list(clip.sample_track(1, 0.5)),
}))
""", str(paths[0]), document["uuid"]],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == {
        "name": "ExactPortable", "tps": 1.0, "loop": True,
        "tracks": expected_tracks, "duration": 1.0,
        "step": [1.0, 2.0, 3.0], "scale": [2.0, 4.0, 6.0],
    }


def test_portable_gltf_rejects_truncated_cubic_output(tmp_path) -> None:
    path = _write_exact_animation_gltf(tmp_path / "truncated-cubic.gltf")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["accessors"][6]["count"] = 5
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="malformed rotation output"):
        load_glb_file(path)


def test_y_up_conversion_transforms_every_cubic_tuple_without_normalizing_tangents() -> None:
    scene = GLBSceneData()
    scene.nodes = [
        GLBNodeData(
            name="Animated",
            children=[],
            mesh_index=None,
            translation=np.zeros(3),
            rotation=np.asarray([0.0, 0.0, 0.0, 1.0]),
            scale=np.ones(3),
        )
    ]
    rotation_rows = np.asarray(
        [[2.0, 3.0, 4.0, 5.0], [0.0, 0.0, 0.0, 1.0], [6.0, 7.0, 8.0, 9.0]]
    )
    scene.animations = [
        GLBAnimationClip(
            name="Cubic",
            tracks=[
                GLBAnimationTrack(
                    node_index=0,
                    node_name="Animated",
                    path="rotation",
                    interpolation="cubic_spline",
                    components=4,
                    times=[0.0],
                    values=rotation_rows.copy(),
                )
            ],
            duration=0.0,
        )
    ]

    convert_y_up_to_z_up(scene)

    expected = rotation_rows[:, [0, 2, 1, 3]].copy()
    expected[:, 1] *= -1.0
    np.testing.assert_array_equal(scene.animations[0].tracks[0].values, expected)
    assert np.linalg.norm(scene.animations[0].tracks[0].values[0]) == pytest.approx(
        np.linalg.norm(rotation_rows[0])
    )


def test_blender_and_scale_fixes_transform_all_cubic_value_and_derivative_rows() -> None:
    scene = GLBSceneData()
    scene.root_nodes = [0]
    scene.nodes = [
        GLBNodeData(
            name="Armature",
            children=[1],
            mesh_index=None,
            translation=np.zeros(3),
            rotation=np.asarray([0.0, 0.0, 0.0, 1.0]),
            scale=np.asarray([2.0, 2.0, 2.0]),
        ),
        GLBNodeData(
            name="RootJoint",
            children=[],
            mesh_index=None,
            translation=np.asarray([1.0, 2.0, 3.0]),
            rotation=np.asarray([0.0, 0.0, 0.0, 1.0]),
            scale=np.asarray([1.0, 2.0, 3.0]),
        ),
    ]
    scene.skins = [
        GLBSkinData(
            name="Skin",
            joint_node_indices=[1],
            inverse_bind_matrices=np.eye(4).reshape(1, 4, 4),
        )
    ]
    rows3 = np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    rows4 = np.asarray(
        [[2.0, 3.0, 4.0, 5.0], [0.0, 0.0, 0.0, 1.0], [6.0, 7.0, 8.0, 9.0]]
    )
    tracks = [
        GLBAnimationTrack(0, "Armature", "scale", "cubic_spline", 3, [0.0], rows3.copy()),
        GLBAnimationTrack(1, "RootJoint", "translation", "cubic_spline", 3, [0.0], rows3.copy()),
        GLBAnimationTrack(1, "RootJoint", "rotation", "cubic_spline", 4, [0.0], rows4.copy()),
        GLBAnimationTrack(1, "RootJoint", "scale", "cubic_spline", 3, [0.0], rows3.copy()),
    ]
    scene.animations = [GLBAnimationClip("CubicFixes", tracks, 0.0)]

    apply_blender_z_up_fix(scene)
    normalize_glb_scale(scene)

    np.testing.assert_allclose(tracks[0].values, rows3 / 2.0)
    expected_translation = rows3[:, [0, 2, 1]].copy()
    expected_translation[:, 1] *= -1.0
    np.testing.assert_allclose(tracks[1].values, expected_translation * 2.0)
    positive_x = np.asarray([0.70710678, 0.0, 0.0, 0.70710678])
    np.testing.assert_allclose(
        tracks[2].values,
        np.asarray([_qmul(positive_x, row) for row in rows4]),
    )
    np.testing.assert_allclose(tracks[3].values, rows3[:, [0, 2, 1]])
    assert np.linalg.norm(tracks[2].values[0]) == pytest.approx(np.linalg.norm(rows4[0]))


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_glb_quaternion_batch_agrees_with_scalar_sign_and_preserves_raw_rows(sign) -> None:
    s = np.sqrt(0.5) * sign
    left = Quat(s, 0.0, 0.0, s)
    storage = np.asarray([
        [0.0, 0.0, 0.0, 0.0],
        [2.0, 3.0, 4.0, 5.0],
        [0.0, 0.0, 0.0, 1.0],
        [0.0, 0.0, 0.0, -1.0],
        [-6.0, 7.0, -8.0, 9.0],
    ], dtype=np.float64)
    rows = storage[::-1]
    before = rows.copy()
    expected = np.column_stack((
        s * (rows[:, 0] + rows[:, 3]),
        s * (rows[:, 1] - rows[:, 2]),
        s * (rows[:, 1] + rows[:, 2]),
        s * (rows[:, 3] - rows[:, 0]),
    ))

    canonical = left.left_multiply_rows(rows)
    bridge = NativeStaticMeshDocument._quaternion_left_multiply((left.x, left.y, left.z, left.w), rows)
    scalar = []
    for row in rows:
        product = left * Quat(row)
        scalar.append([product.x, product.y, product.z, product.w])

    assert canonical.dtype == np.float64
    assert bridge.dtype == np.float64
    assert not np.shares_memory(canonical, rows)
    np.testing.assert_array_equal(rows, before)
    np.testing.assert_allclose(canonical, expected, atol=1e-14)
    np.testing.assert_allclose(bridge, expected, atol=1e-14)
    np.testing.assert_allclose(scalar, expected, atol=1e-14)
    np.testing.assert_allclose(np.linalg.norm(bridge, axis=1), np.linalg.norm(rows, axis=1), atol=1e-14)
    np.testing.assert_array_equal(bridge[1], -bridge[2])
    np.testing.assert_array_equal(bridge[-1], np.zeros(4))


@pytest.mark.parametrize("convert_to_z_up,blender_z_up_fix", [
    (True, False), (False, True), (True, True),
])
def test_native_and_portable_pose_corrections_preserve_cubic_rotation_tangents(
    tmp_path, convert_to_z_up, blender_z_up_fix,
) -> None:
    path = _write_exact_animation_gltf(tmp_path / "cubic-pose-corrections.gltf")
    document = json.loads(path.read_text(encoding="utf-8"))
    binary = (path.parent / document["buffers"][0].pop("uri")).read_bytes()
    json_chunk = json.dumps(document, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * (-len(json_chunk) % 4)
    binary_chunk = binary + b"\0" * (-len(binary) % 4)
    native_path = tmp_path / "cubic-pose-corrections.glb"
    native_path.write_bytes(
        struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(json_chunk) + 8 + len(binary_chunk))
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
        + struct.pack("<II", len(binary_chunk), 0x004E4942)
        + binary_chunk
    )
    original = load_glb_file(path).animations[0].tracks[2].values.astype(np.float64)
    expected = original.copy()
    if convert_to_z_up:
        expected = expected[:, [0, 2, 1, 3]]
        expected[:, 1] *= -1.0
    if blender_z_up_fix:
        # Left multiplication by -90 degrees about X, preserving derivative magnitude.
        s = np.sqrt(0.5)
        x, y, z, w = expected.T.copy()
        expected = np.column_stack((s * (x - w), s * (y + z), s * (z - y), s * (w + x)))
    flags = {"convert_to_z_up": convert_to_z_up, "blender_z_up_fix": blender_z_up_fix}

    portable = load_glb_file_normalized(path, normalize_scale=False, **flags)
    native = NativeStaticMeshDocument(native_path).build_animation_clip(0, str(uuid.uuid4()), **flags)
    portable_rows = portable.animations[0].tracks[2].values
    native_rows = np.asarray(native.tracks[2]["values"]).reshape(-1, 4)

    np.testing.assert_allclose(portable_rows, expected, atol=1e-6)
    np.testing.assert_allclose(native_rows, expected, atol=1e-6)
    np.testing.assert_allclose(native_rows, portable_rows, atol=1e-6)
    tangent_rows = [0, 2, 3, 5]
    assert all(np.linalg.norm(row) > 1.0 for row in original[tangent_rows])
    for rows in (portable_rows, native_rows):
        np.testing.assert_allclose(
            np.linalg.norm(rows[tangent_rows], axis=1),
            np.linalg.norm(original[tangent_rows], axis=1), atol=1e-6,
        )
