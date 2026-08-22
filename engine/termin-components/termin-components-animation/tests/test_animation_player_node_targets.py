import pytest

from termin.animation import TcAnimationClip
from termin.animation_components import AnimationPlayer
from termin.geombase import Vec3
from termin.scene import Entity


def test_animation_player_applies_non_bone_node_channel():
    node = Entity(name="Armature")
    clip = TcAnimationClip.create("RootMove", "pytest-animation-node-target")
    clip.set_tps(1.0)
    clip.set_loop(False)
    clip.set_channels([
        {
            "target_name": "Armature",
            "translation_keys": [
                (0.0, Vec3(0.0, 0.0, 0.0)),
                (1.0, Vec3(1.0, 2.0, 3.0)),
            ],
            "rotation_keys": [],
            "scale_keys": [],
        }
    ])

    player = AnimationPlayer()
    player.node_targets = [node]
    player.add_clip(clip)
    player.set_current("RootMove")
    player.update_bones_at_time(1.0)

    assert tuple(node.transform.global_position) == pytest.approx((1.0, 2.0, 3.0))


def test_animation_player_applies_bulk_track_by_exact_node_index():
    first = Entity(name="Duplicate")
    target = Entity(name="Duplicate")
    clip = TcAnimationClip.create("BulkNodeMove", "pytest-animation-bulk-node-target")
    clip.set_tps(1.0)
    clip.set_loop(False)
    clip.set_tracks([
        {
            "target_node_index": 2,
            "path": "translation",
            "interpolation": "step",
            "components": 3,
            "times": [0.0, 1.0],
            "values": [1.0, 2.0, 3.0, 7.0, 8.0, 9.0],
        },
        {
            "target_node_index": 2,
            "path": "scale",
            "interpolation": "linear",
            "components": 3,
            "times": [0.0, 1.0],
            "values": [1.0, 2.0, 3.0, 3.0, 6.0, 9.0],
        },
    ])

    player = AnimationPlayer()
    player.node_targets = [first, None, target]
    assert player.node_targets[1] is None
    player.add_clip(clip)
    player.set_current("BulkNodeMove")
    player.update_bones_at_time(0.5)

    assert tuple(first.transform.global_position) == pytest.approx((0.0, 0.0, 0.0))
    assert tuple(target.transform.global_position) == pytest.approx((1.0, 2.0, 3.0))
    assert tuple(target.transform.local_scale()) == pytest.approx((2.0, 4.0, 6.0))


def test_animation_player_refreshes_same_count_channel_target_after_replacement():
    first = Entity(name="First")
    second = Entity(name="Second")
    clip = TcAnimationClip.create("Retarget", "pytest-animation-channel-retarget")
    clip.set_tps(1.0)
    clip.set_loop(False)
    clip.set_channels([
        {
            "target_name": "First",
            "translation_keys": [(0.0, Vec3(1.0, 0.0, 0.0))],
            "rotation_keys": [],
            "scale_keys": [],
        }
    ])

    player = AnimationPlayer()
    player.node_targets = [first, second]
    player.add_clip(clip)
    player.set_current("Retarget")
    player.update_bones_at_time(0.0)
    assert tuple(first.transform.global_position) == pytest.approx((1.0, 0.0, 0.0))

    clip.set_channels([
        {
            "target_name": "Second",
            "translation_keys": [(0.0, Vec3(4.0, 5.0, 6.0))],
            "rotation_keys": [],
            "scale_keys": [],
        }
    ])
    player.update_bones_at_time(0.0)

    assert tuple(first.transform.global_position) == pytest.approx((1.0, 0.0, 0.0))
    assert tuple(second.transform.global_position) == pytest.approx((4.0, 5.0, 6.0))


def test_animation_player_resizes_channel_buffer_after_bulk_to_legacy_replacement():
    target = Entity(name="Target")
    clip = TcAnimationClip.create("RepresentationSwitch", "pytest-animation-representation-switch")
    clip.set_tps(1.0)
    clip.set_loop(False)
    clip.set_tracks([
        {
            "target_node_index": 0,
            "path": "translation",
            "interpolation": "step",
            "components": 3,
            "times": [0.0],
            "values": [1.0, 2.0, 3.0],
        }
    ])

    player = AnimationPlayer()
    player.node_targets = [target]
    player.add_clip(clip)
    player.set_current("RepresentationSwitch")
    player.update_bones_at_time(0.0)
    assert tuple(target.transform.global_position) == pytest.approx((1.0, 2.0, 3.0))

    clip.set_channels([
        {
            "target_name": "Target",
            "translation_keys": [(0.0, Vec3(7.0, 8.0, 9.0))],
            "rotation_keys": [],
            "scale_keys": [],
        }
    ])
    player.update_bones_at_time(0.0)

    assert tuple(target.transform.global_position) == pytest.approx((7.0, 8.0, 9.0))
