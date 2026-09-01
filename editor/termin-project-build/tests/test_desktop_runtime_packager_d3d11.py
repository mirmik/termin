import json
from pathlib import Path

import pytest

from termin.project_build import export_runtime_package
from desktop_runtime_packager_test_support import (
    write_json as _write_json,
    write_target_marking_shader_compiler as _write_target_marking_shader_compiler,
)

full_runtime_package_exporter = pytest.mark.full(
    reason="runtime package export/build scenarios spawn shader compiler subprocesses"
)

@full_runtime_package_exporter
def test_export_runtime_package_can_record_d3d11_shader_artifacts(tmp_path: Path) -> None:
    import termin.graphics
    from termin.materials import TcMaterial

    project = tmp_path / "D3D11RuntimeGame"
    project.mkdir()
    material_uuid = "live-d3d11-material-uuid"
    shader_uuid = "live-d3d11-shader-uuid"

    material = TcMaterial.create("Live D3D11 Material", material_uuid)
    phase = material.add_phase_from_sources(
        "[shader(\"vertex\")] void main() {}\n",
        "[shader(\"fragment\")] void main() {}\n",
        "",
        "LiveD3D11Shader",
        "opaque",
        3,
        shader_uuid=shader_uuid,
        language=termin.graphics.ShaderLanguage.SLANG.value,
        artifact_policy=termin.graphics.ShaderArtifactPolicy.REQUIRED.value,
    )
    assert phase is not None

    shader = termin.graphics.TcShader.from_uuid(shader_uuid)
    assert shader.is_valid
    shader.set_language(termin.graphics.ShaderLanguage.SLANG)
    shader.set_artifact_policy(termin.graphics.ShaderArtifactPolicy.REQUIRED)

    _write_json(
        project / "Main.scene",
        {
            "uuid": "scene-uuid",
            "entities": [
                {
                    "uuid": "entity-uuid",
                    "components": [
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "material": {
                                    "uuid": material_uuid,
                                    "name": "Live D3D11 Material",
                                    "type": "uuid",
                                    "kind": "tc_material",
                                },
                            },
                        }
                    ],
                }
            ],
        },
    )

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "package",
        shader_compiler=_write_target_marking_shader_compiler(tmp_path),
        shader_targets=("vulkan", "opengl", "d3d11"),
    )

    shader_data = json.loads((result.package_dir / "shaders" / f"{shader_uuid}.shader.json").read_text(encoding="utf-8"))
    assert shader_data["artifacts"] == {
        "vulkan": {
            "vertex": f"shaders/vulkan/{shader_uuid}.vert.spv",
            "fragment": f"shaders/vulkan/{shader_uuid}.frag.spv",
        },
        "opengl": {
            "vertex": f"shaders/opengl/{shader_uuid}.vert.glsl",
            "fragment": f"shaders/opengl/{shader_uuid}.frag.glsl",
        },
        "d3d11": {
            "vertex": f"shaders/d3d11/{shader_uuid}.vs.cso",
            "fragment": f"shaders/d3d11/{shader_uuid}.ps.cso",
        },
    }
    assert (result.package_dir / "shaders" / "d3d11" / f"{shader_uuid}.vs.cso").read_bytes() == b"ARTIFACT-d3d11"
    assert (result.package_dir / "shaders" / "d3d11" / f"{shader_uuid}.ps.cso").read_bytes() == b"ARTIFACT-d3d11"

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["target_requirements"]["backends"] == ["vulkan", "opengl", "d3d11"]

    calls = [
        json.loads(line)
        for line in (tmp_path / "target_shaderc_calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert "d3d11" in {call[call.index("--target") + 1] for call in calls}
    assert result.diagnostics == []
