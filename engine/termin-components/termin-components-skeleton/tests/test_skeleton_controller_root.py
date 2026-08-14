from termin.scene import Entity
from termin.skeleton_components import SkeletonController


def test_skeleton_controller_exposes_explicit_skeleton_root():
    root = Entity(name="Armature")
    controller = SkeletonController()

    controller.skeleton_root = root

    assert controller.skeleton_root == root


def test_skeleton_controller_accepts_missing_skeleton_root():
    controller = SkeletonController()

    controller.skeleton_root = None

    assert controller.skeleton_root is None
