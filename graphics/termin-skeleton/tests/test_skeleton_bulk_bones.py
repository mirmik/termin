import gc
import sys
import uuid

import numpy as np
import pytest

from termin.geombase import Mat44, Quat, Vec3
from termin.skeleton import SkeletonInstance, TcSkeleton


def _bone(
    name: str,
    parent_index: int = -1,
    *,
    inverse_bind_matrix: Mat44 | None = None,
    translation: Vec3 | None = None,
    rotation: Quat | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "parent_index": parent_index,
        "inverse_bind_matrix": (Mat44.identity() if inverse_bind_matrix is None else inverse_bind_matrix),
        "bind_translation": Vec3.zero() if translation is None else translation,
        "bind_rotation": Quat.identity() if rotation is None else rotation,
        "bind_scale": Vec3(1.0, 1.0, 1.0),
    }


def test_bulk_bones_replace_complete_payload_and_roots() -> None:
    skeleton = TcSkeleton.create("Bulk", str(uuid.uuid4()))
    root_inverse_bind = Mat44.identity()
    root_inverse_bind[3, 0] = -4.0
    root_inverse_bind[3, 1] = -5.0
    root_inverse_bind[3, 2] = -6.0
    root = _bone("Root", inverse_bind_matrix=root_inverse_bind)
    skeleton.set_bones([root, _bone("Child", 0, translation=Vec3(1.0, 2.0, 3.0))])

    assert skeleton.bone_count == 2
    assert skeleton.root_count == 1
    root_bone = skeleton.bones[0]
    stored_inverse_bind = root_bone["inverse_bind_matrix"]
    assert isinstance(stored_inverse_bind, Mat44)
    assert (
        stored_inverse_bind[3, 0],
        stored_inverse_bind[3, 1],
        stored_inverse_bind[3, 2],
    ) == pytest.approx((-4.0, -5.0, -6.0))
    assert isinstance(root_bone["bind_translation"], Vec3)
    assert isinstance(root_bone["bind_rotation"], Quat)
    assert isinstance(root_bone["bind_scale"], Vec3)

    child_bone = skeleton.bones[1]
    assert child_bone["name"] == "Child"
    assert child_bone["parent_index"] == 0
    child_translation = child_bone["bind_translation"]
    assert isinstance(child_translation, Vec3)
    assert tuple(child_translation) == pytest.approx((1.0, 2.0, 3.0))


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

    skeleton.set_bones([_bone("Root", rotation=Quat(largest, largest, largest, largest))])

    rotation = skeleton.bones[0]["bind_rotation"]
    assert isinstance(rotation, Quat)
    assert tuple(rotation) == pytest.approx((0.5, 0.5, 0.5, 0.5))


@pytest.mark.parametrize(
    "rotation",
    [
        Quat(0.0, 0.0, 0.0, 0.0),
        Quat(0.0, 0.0, 0.0, float("nan")),
        Quat(0.0, 0.0, 0.0, float("inf")),
    ],
    ids=["zero", "nan", "inf"],
)
def test_bulk_bone_invalid_rotation_preserves_previous_payload(rotation) -> None:
    skeleton = TcSkeleton.create("InvalidRotation", str(uuid.uuid4()))
    skeleton.set_bones([_bone("Original", translation=Vec3(1.0, 2.0, 3.0))])
    version = skeleton.version

    with pytest.raises(RuntimeError, match="previous payload was preserved"):
        skeleton.set_bones([_bone("Rejected", translation=Vec3(9.0, 8.0, 7.0), rotation=rotation)])

    assert skeleton.version == version
    assert skeleton.bones[0]["name"] == "Original"
    translation = skeleton.bones[0]["bind_translation"]
    assert isinstance(translation, Vec3)
    assert tuple(translation) == pytest.approx((1.0, 2.0, 3.0))


def test_bulk_bones_reject_legacy_flat_transform_payload_transactionally() -> None:
    skeleton = TcSkeleton.create("StrictTypes", str(uuid.uuid4()))
    skeleton.set_bones([_bone("Original", translation=Vec3(1.0, 2.0, 3.0))])
    version = skeleton.version
    legacy_bone = _bone("Legacy")
    legacy_bone["bind_translation"] = (9.0, 8.0, 7.0)

    with pytest.raises(TypeError, match="bind_translation.*Vec3"):
        skeleton.set_bones([legacy_bone])

    assert skeleton.version == version
    assert skeleton.bones[0]["name"] == "Original"
    translation = skeleton.bones[0]["bind_translation"]
    assert isinstance(translation, Vec3)
    assert tuple(translation) == pytest.approx((1.0, 2.0, 3.0))


@pytest.mark.parametrize("parent_index", [1 << 80, -(1 << 80)])
def test_bulk_bones_reject_out_of_range_parent_index_transactionally(parent_index: int) -> None:
    skeleton = TcSkeleton.create("StrictParentIndex", str(uuid.uuid4()))
    skeleton.set_bones([_bone("Original")])
    version = skeleton.version

    with pytest.raises(ValueError, match="parent_index.*signed 32-bit range"):
        skeleton.set_bones([_bone("Rejected", parent_index)])

    assert skeleton.version == version
    assert skeleton.bones[0]["name"] == "Original"


def _skeleton_instance() -> tuple[SkeletonInstance, TcSkeleton]:
    skeleton = TcSkeleton.create("Instance", str(uuid.uuid4()))
    skeleton.set_bones([_bone("Root")])
    instance = SkeletonInstance(skeleton)
    return instance, skeleton


def _temporary_instance(skeleton_uuid: str) -> SkeletonInstance:
    skeleton = TcSkeleton.create("Temporary", skeleton_uuid)
    skeleton.set_bones([_bone("Root", translation=Vec3(2.0, 0.0, 0.0))])
    return SkeletonInstance(skeleton)


def test_skeleton_instance_strongly_owns_temporary_resource() -> None:
    skeleton_uuid = str(uuid.uuid4())
    instance = _temporary_instance(skeleton_uuid)

    gc.collect()

    assert instance.skeleton is not None
    assert instance.skeleton.is_valid
    assert instance.skeleton.uuid == skeleton_uuid
    assert instance.bone_count() == 1
    assert np.asarray(instance.get_bone_matrices()).shape == (1, 4, 4)


def test_skeleton_instance_getter_returns_an_owning_resource_copy() -> None:
    skeleton_uuid = str(uuid.uuid4())
    instance = _temporary_instance(skeleton_uuid)
    resource = instance.skeleton
    assert resource is not None

    instance.skeleton = None
    del instance
    gc.collect()

    assert resource.is_valid
    assert resource.uuid == skeleton_uuid
    assert TcSkeleton.from_uuid(skeleton_uuid).is_valid


def test_skeleton_instance_none_reset_and_typed_boundary() -> None:
    instance, skeleton = _skeleton_instance()
    instance.skeleton = None

    assert instance.skeleton is None
    assert instance.bone_count() == 0
    assert np.asarray(instance.get_bone_matrices()).shape == (0, 4, 4)

    with pytest.raises(ValueError, match="live skeleton resource"):
        instance.skeleton = TcSkeleton()
    with pytest.raises(TypeError, match="TcSkeleton or None"):
        instance.skeleton = object()
    with pytest.raises(ValueError, match="live skeleton resource"):
        SkeletonInstance(TcSkeleton())
    with pytest.raises(TypeError, match="TcSkeleton or None"):
        SkeletonInstance(object())

    instance.skeleton = skeleton
    assert instance.bone_count() == 1


def test_skeleton_instance_survives_registry_pool_growth() -> None:
    skeleton_uuid = str(uuid.uuid4())
    instance = _temporary_instance(skeleton_uuid)

    resources = [TcSkeleton.create(f"Growth {index}", str(uuid.uuid4())) for index in range(40)]

    assert all(resource.is_valid for resource in resources)
    assert instance.skeleton is not None
    assert instance.skeleton.uuid == skeleton_uuid
    assert instance.bone_count() == 1
    np.testing.assert_allclose(np.asarray(instance.get_bone_world_matrix(0))[:3, 3], (2.0, 0.0, 0.0))


def test_skeleton_instance_refreshes_same_count_replacement_from_bind_pose() -> None:
    instance, skeleton = _skeleton_instance()
    instance.set_bone_transform(0, translation=Vec3(9.0, 0.0, 0.0))
    instance.update()
    assert np.asarray(instance.get_bone_world_matrix(0))[0, 3] == pytest.approx(9.0)
    previous_version = skeleton.version

    inverse_bind = Mat44.identity()
    inverse_bind[3, 0] = -1.0
    skeleton.set_bones(
        [
            _bone(
                "Root",
                inverse_bind_matrix=inverse_bind,
                translation=Vec3(4.0, 0.0, 0.0),
            )
        ]
    )

    assert skeleton.version == previous_version + 1
    assert instance.bone_count() == 1
    assert np.asarray(instance.get_bone_world_matrix(0))[0, 3] == pytest.approx(4.0)
    assert np.asarray(instance.get_bone_matrices())[0, 0, 3] == pytest.approx(3.0)


def test_skeleton_instance_refreshes_count_changing_replacement() -> None:
    instance, skeleton = _skeleton_instance()

    skeleton.set_bones([_bone("Root"), _bone("Child", 0, translation=Vec3(0.0, 3.0, 0.0))])

    assert instance.bone_count() == 2
    matrices = np.asarray(instance.get_bone_matrices())
    assert matrices.shape == (2, 4, 4)
    assert np.asarray(instance.get_bone_world_matrix(1))[1, 3] == pytest.approx(3.0)


def test_failed_skeleton_replacement_preserves_runtime_override() -> None:
    instance, skeleton = _skeleton_instance()
    instance.set_bone_transform(0, translation=Vec3(7.0, 0.0, 0.0))
    instance.update()
    before = np.array(instance.get_bone_world_matrix(0), copy=True)
    previous_version = skeleton.version

    with pytest.raises(RuntimeError, match="previous payload was preserved"):
        skeleton.set_bones([_bone("Cycle", 0)])

    assert skeleton.version == previous_version
    instance.update()
    np.testing.assert_array_equal(instance.get_bone_world_matrix(0), before)


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
