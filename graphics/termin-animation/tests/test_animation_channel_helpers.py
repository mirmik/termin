from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from termin.animation.channel import channel_data_from_fbx
from termin.geombase import Quat, Vec3


def test_channel_data_from_fbx_converts_xyz_euler_keys_to_quaternions() -> None:
    channel = SimpleNamespace(
        node_name="Arm",
        pos_keys=[(0.0, (1.0, 2.0, 3.0))],
        rot_keys=[(12.0, (90.0, 0.0, 0.0))],
        scale_keys=[(0.0, (2.0, 3.0, 4.0))],
    )

    data = channel_data_from_fbx(channel)

    assert data["target_name"] == "Arm"
    translation_time, translation = data["translation_keys"][0]
    assert translation_time == 0.0
    assert isinstance(translation, Vec3)
    assert tuple(translation) == pytest.approx((1.0, 2.0, 3.0))

    rotation_time, rotation = data["rotation_keys"][0]
    assert rotation_time == 12.0
    assert isinstance(rotation, Quat)
    half_sqrt = math.sqrt(0.5)
    assert tuple(rotation) == pytest.approx((half_sqrt, 0.0, 0.0, half_sqrt))

    assert data["scale_keys"] == [(0.0, 3.0)]


def test_channel_data_from_fbx_rejects_non_finite_euler_key() -> None:
    channel = SimpleNamespace(
        node_name="Arm",
        pos_keys=[],
        rot_keys=[(0.0, (0.0, math.nan, 0.0))],
        scale_keys=[],
    )

    with pytest.raises(ValueError):
        channel_data_from_fbx(channel)
