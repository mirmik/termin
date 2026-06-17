import os
import subprocess
import sys
import textwrap

from termin.voxels.voxel_shader import voxel_display_shader


def test_voxel_display_shader_does_not_duplicate_reflected_material_layout():
    shader = voxel_display_shader()

    assert shader.is_valid
    assert shader.uuid == "termin-engine-voxel-display"
    assert shader.material_ubo_block_size == 0
    assert shader.material_ubo_entry_count == 0
    assert "ConstantBuffer<VoxelDisplayParams> material" in shader.fragment_source


def test_native_import_before_tgfx_keeps_builtin_shader_catalog_available():
    code = textwrap.dedent(
        """
        import termin._native
        from tgfx import TcShader

        shader = TcShader.from_builtin_catalog("termin-engine-voxel-display")
        if not shader.is_valid:
            raise SystemExit(
                "termin-engine-voxel-display did not load after importing termin._native first"
            )
        if shader.language.name != "SLANG":
            raise SystemExit(f"unexpected shader language: {shader.language}")
        if shader.artifact_policy.name != "REQUIRED":
            raise SystemExit(f"unexpected artifact policy: {shader.artifact_policy}")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
