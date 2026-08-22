import sys
import uuid

import numpy as np
import pytest

from termin.geombase import Quat, Vec3
from termin.skeleton import SkeletonInstance, TcSkeleton


def _bone(
    name: str,
    parent_index: int = -1,
    *,
    translation=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0, 1.0),
):
    return {
        "name": name,
        "parent_index": parent_index,
        "inverse_bind_matrix": [
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ],
        "bind_translation": translation,
        "bind_rotation": rotation,
        "bind_scale": (1.0, 1.0, 1.0),
    }


def test_bulk_bones_replace_complete_payload_and_roots() -> None:
    skeleton = TcSkeleton.create("Bulk", str(uuid.uuid4()))
    root = _bone("Root")
    root["inverse_bind_matrix"][12:15] = [-4.0, -5.0, -6.0]
    skeleton.set_bones([root, _bone("Child", 0, translation=(1.0, 2.0, 3.0))])

    assert skeleton.bone_count == 2
    assert skeleton.root_count == 1
    assert skeleton.bones[0]["inverse_bind_matrix"][12:15] == pytest.approx((-4.0, -5.0, -6.0))
    assert skeleton.bones[1]["name"] == "Child"
    assert skeleton.bones[1]["parent_index"] == 0
    assert skeleton.bones[1]["bind_translation"] == pytest.approx((1.0, 2.0, 3.0))


@pytest.mark.parametrize(
    "invalid",
    [
        [_bone("Self", 0)],
        [_bone("A", 1), _bone("B", 0)],
        [_bone("Missing", 4)],
    ],
)
def test_bulk_bone_replacement_is_transactional(invalid) -> None:
    skeleton = TcSkeleton.create("Rollback", str(uuid.uuid4()))
    skeleton.set_bones([_bone("Original")])
    version = skeleton.version

    with pytest.raises(RuntimeError, match="previous payload was preserved"):
        skeleton.set_bones(invalid)

    assert skeleton.version == version
    assert skeleton.bone_count == 1
    assert skeleton.bones[0]["name"] == "Original"


def test_bulk_bones_normalize_full_range_finite_rotations() -> None:
    skeleton = TcSkeleton.create("ScaledRotation", str(uuid.uuid4()))
    largest = sys.float_info.max

    skeleton.set_bones([_bone("Root", rotation=(largest, largest, largest, largest))])

    assert skeleton.bones[0]["bind_rotation"] == pytest.approx((0.5, 0.5, 0.5, 0.5))


@pytest.mark.parametrize(
    "rotation",
    [
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, float("nan")),
        (0.0, 0.0, 0.0, float("inf")),
    ],
    ids=["zero", "nan", "inf"],
)
def test_bulk_bone_invalid_rotation_preserves_previous_payload(rotation) -> None:
    skeleton = TcSkeleton.create("InvalidRotation", str(uuid.uuid4()))
    skeleton.set_bones([_bone("Original", translation=(1.0, 2.0, 3.0))])
    version = skeleton.version

    with pytest.raises(RuntimeError, match="previous payload was preserved"):
        skeleton.set_bones([_bone("Rejected", translation=(9.0, 8.0, 7.0), rotation=rotation)])

    assert skeleton.version == version
    assert skeleton.bones[0]["name"] == "Original"
    assert skeleton.bones[0]["bind_translation"] == pytest.approx((1.0, 2.0, 3.0))


def _skeleton_instance() -> tuple[SkeletonInstance, TcSkeleton]:
    skeleton = TcSkeleton.create("Instance", str(uuid.uuid4()))
    skeleton.set_bones([_bone("Root")])
    instance = SkeletonInstance()
    instance.skeleton = skeleton.get()
    return instance, skeleton


def test_skeleton_instance_normalizes_full_range_rotation() -> None:
    instance, _skeleton_owner = _skeleton_instance()
    largest = sys.float_info.max

    instance.set_bone_transform(
        0,
        translation=Vec3(1.0, 2.0, 3.0),
        rotation=Quat(largest, largest, largest, largest),
    )
    instance.update()

    matrix = np.asarray(instance.get_bone_world_matrix(0))
    expected = np.array(
        [
            [0.0, 0.0, 1.0, 1.0],
            [1.0, 0.0, 0.0, 2.0],
            [0.0, 1.0, 0.0, 3.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(matrix, expected, atol=1.0e-6)


@pytest.mark.parametrize(
    "rotation",
    [
        Quat(0.0, 0.0, 0.0, 0.0),
        Quat(0.0, 0.0, 0.0, float("nan")),
        Quat(0.0, 0.0, 0.0, float("inf")),
    ],
    ids=["zero", "nan", "inf"],
)
def test_skeleton_instance_invalid_rotation_is_transactional(rotation) -> None:
    instance, _skeleton_owner = _skeleton_instance()
    instance.set_bone_transform(
        0,
        translation=Vec3(1.0, 2.0, 3.0),
        rotation=Quat.identity(),
        scale=Vec3(1.0, 2.0, 3.0),
    )
    instance.update()
    before = np.array(instance.get_bone_world_matrix(0), copy=True)

    assert not instance.try_set_bone_transform(
        0,
        translation=Vec3(9.0, 8.0, 7.0),
        rotation=rotation,
        scale=Vec3(4.0, 5.0, 6.0),
    )
    with pytest.raises(ValueError, match="finite non-zero rotation"):
        instance.set_bone_transform(
            0,
            translation=Vec3(9.0, 8.0, 7.0),
            rotation=rotation,
            scale=Vec3(4.0, 5.0, 6.0),
        )
    instance.update()

    np.testing.assert_array_equal(instance.get_bone_world_matrix(0), before)
