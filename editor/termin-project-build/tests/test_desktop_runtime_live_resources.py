import json
from pathlib import Path

import numpy as np
import pytest

from termin.project_build import export_runtime_package

from desktop_runtime_packager_test_support import (
    write_fake_shader_compiler as _write_fake_shader_compiler,
    write_json as _write_json,
)

full_runtime_package_exporter = pytest.mark.full(
    reason="runtime package export/build scenarios spawn shader compiler subprocesses"
)


@full_runtime_package_exporter
def test_export_runtime_package_uses_live_mesh_material_shader(tmp_path: Path) -> None:
    import termin.graphics
    from termin.materials import TcMaterial
    from termin.geombase import SrgbColor
    from termin.mesh import TcAttribType, TcDrawMode, TcMesh, TcVertexLayout

    project = tmp_path / "LiveResourceGame"
    project.mkdir()
    mesh_uuid = "live-mesh-uuid"
    material_uuid = "live-material-uuid"
    program_uuid = "live-shader-program-uuid"
    shader_uuid = termin.graphics.TcShaderProgram.make_phase_uuid(program_uuid, "opaque")

    program = termin.graphics.TcShaderProgram.declare(program_uuid, "LiveShaderProgram")
    program.set_payload(
        name="LiveShaderProgram",
        source_path="Assets/Live.shader",
        language="glsl",
        features=1,
        properties=[
            {
                "name": "u_color",
                "property_type": "SrgbColor",
                "label": "Color",
                "default": SrgbColor(1.0, 1.0, 1.0, 1.0),
            },
            {
                "name": "u_roughness",
                "property_type": "Float",
                "label": "Roughness",
                "default": 0.5,
                "range_min": 0.0,
                "range_max": 1.0,
            },
        ],
        phases=[
            {
                "phase_mark": "opaque",
                "priority": 7,
                "state": {
                    "polygon_mode": 0,
                    "cull": True,
                    "depth_test": True,
                    "depth_write": True,
                    "blend": False,
                    "blend_src": 2,
                    "blend_dst": 3,
                    "depth_func": 0,
                },
            }
        ],
    )

    layout = TcVertexLayout()
    layout.add("position", 3, TcAttribType.FLOAT32, 0)
    layout.add("color", 3, TcAttribType.FLOAT32, 1)
    vertices = np.array(
        [
            0.0, 0.5, 0.0, 1.0, 0.0, 0.0,
            -0.5, -0.5, 0.0, 0.0, 1.0, 0.0,
            0.5, -0.5, 0.0, 0.0, 0.0, 1.0,
        ],
        dtype=np.float32,
    )
    indices = np.array([0, 1, 2], dtype=np.uint32)
    mesh = TcMesh.from_interleaved(
        vertices,
        3,
        indices,
        layout,
        "Live Triangle",
        mesh_uuid,
        TcDrawMode.TRIANGLES,
    )
    assert mesh.is_valid

    material = TcMaterial.create("Live Material", material_uuid)
    phase = material.add_phase_from_sources(
        "#version 450\nlayout(location=0) in vec3 in_position;\nvoid main(){gl_Position=vec4(in_position,1.0);}\n",
        "#version 450\nlayout(location=0) out vec4 out_color;\nvoid main(){out_color=vec4(1.0);}\n",
        "",
        "LiveShader",
        "opaque",
        7,
        shader_uuid=shader_uuid,
        language=termin.graphics.ShaderLanguage.GLSL.value,
    )
    assert phase is not None
    material.set_shader_program_dependency(program_uuid, program.version)
    shader = termin.graphics.TcShader.from_uuid(shader_uuid)
    assert shader.is_valid
    shader.set_feature(1)
    material.set_uniform_srgb_color("u_color", SrgbColor(0.25, 0.5, 0.75, 1.0))
    material.set_uniform_float("u_roughness", 0.625)

    _write_json(
        project / "Main.scene",
        {
            "uuid": "scene-uuid",
            "entities": [
                {
                    "uuid": "entity-uuid",
                    "components": [
                        {
                            "type": "MeshComponent",
                            "data": {
                                "mesh": {
                                    "uuid": mesh_uuid,
                                    "name": "Live Triangle",
                                    "type": "uuid",
                                    "kind": "tc_mesh",
                                },
                            },
                        },
                        {
                            "type": "MeshRenderer",
                            "data": {
                                "material": {
                                    "uuid": material_uuid,
                                    "name": "Live Material",
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
    compiler = _write_fake_shader_compiler(tmp_path)

    result = export_runtime_package(
        project_root=project,
        entry_scene="Main.scene",
        output_dir=project / "dist" / "android" / "LiveResourceGame" / "package",
        shader_compiler=compiler,
    )

    mesh_data = json.loads((result.package_dir / "meshes" / f"{mesh_uuid}.tmesh.json").read_text(encoding="utf-8"))
    material_data = json.loads((result.package_dir / "materials" / f"{material_uuid}.tmat.json").read_text(encoding="utf-8"))
    shader_data = json.loads((result.package_dir / "shaders" / f"{shader_uuid}.shader.json").read_text(encoding="utf-8"))
    program_data = json.loads(
        (result.package_dir / "shaders" / f"{program_uuid}.shader-program.json").read_text(
            encoding="utf-8"
        )
    )

    assert mesh_data["vertices"] == vertices.astype(float).tolist()
    assert mesh_data["indices"] == [0, 1, 2]
    assert mesh_data["submeshes"] == [
        {
            "first_index": 0,
            "index_count": 3,
            "vertex_offset": 0,
            "material_slot": 0,
            "draw_mode": "triangles",
            "name": "Live Triangle",
        }
    ]
    assert mesh_data["layout"] == [
        {"name": "position", "location": 0, "components": 3, "type": "float32"},
        {"name": "color", "location": 1, "components": 3, "type": "float32"},
    ]
    assert material_data["phases"] == [
        {"mark": "opaque", "shader": shader_uuid, "priority": 7},
    ]
    assert material_data["shader_program"] == program_uuid
    assert material_data["uniforms"] == {
        "u_color": [0.25, 0.5, 0.75, 1.0],
        "u_roughness": 0.625,
    }
    assert shader_data["uuid"] == shader_uuid
    assert shader_data["language"] == "glsl"
    assert shader_data["features"] == 1
    assert program_data["schema_version"] == 1
    assert program_data["uuid"] == program_uuid
    assert program_data["phases"][0]["shader"] == shader_uuid
    assert program_data["properties"][1]["range_max"] == 1.0
    shader_sources = {
        path.relative_to(result.package_dir)
        for path in result.package_dir.rglob("*.shader")
    }
    assert shader_sources == {
        Path("builtin_shaders/termin-engine-skybox.shader"),
    }
    assert Path("shaders", f"{shader_uuid}.shader") not in shader_sources
    assert shader_data["artifacts"] == {
        "vulkan": {
            "vertex": f"shaders/vulkan/{shader_uuid}.vert.spv",
            "fragment": f"shaders/vulkan/{shader_uuid}.frag.spv",
        }
    }
    assert (result.package_dir / "shaders" / "vulkan" / f"{shader_uuid}.vert.spv").read_bytes() == b"SPIRV"
    assert (result.package_dir / "shaders" / "vulkan" / f"{shader_uuid}.frag.spv").read_bytes() == b"SPIRV"
    assert result.diagnostics == []
