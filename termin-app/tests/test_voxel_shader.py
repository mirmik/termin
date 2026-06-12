from termin.voxels.voxel_shader import voxel_display_shader


def test_voxel_display_shader_does_not_duplicate_reflected_material_layout():
    shader = voxel_display_shader()

    assert shader.is_valid
    assert shader.uuid == "termin-engine-voxel-display"
    assert shader.material_ubo_block_size == 0
    assert shader.material_ubo_entry_count == 0
    assert "ConstantBuffer<VoxelDisplayParams> material" in shader.fragment_source
