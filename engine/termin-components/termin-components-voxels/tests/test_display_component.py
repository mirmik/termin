import pytest

from termin_voxel_components.display_component import VoxelDisplayComponent


def test_voxel_display_authored_colors_decode_rgb_and_preserve_alpha() -> None:
    linear = VoxelDisplayComponent._authored_color_to_linear((0.5, 0.5, 0.5, 0.5))

    assert linear == pytest.approx((0.21404114, 0.21404114, 0.21404114, 0.5))
