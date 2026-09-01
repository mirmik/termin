import os
import subprocess
import sys
import textwrap


def test_default_scene_mesh_and_material_refs_survive_editor_roundtrip() -> None:
    overlay_manifest = os.environ["TERMIN_PYTHON_OVERLAY"]
    result = subprocess.run(
        [
            sys.executable,
            "--termin-overlay",
            str(overlay_manifest),
            "-c",
            textwrap.dedent(
                """
                from termin.bootstrap import bootstrap_editor, shutdown_editor
                from termin.default_assets.resource_manager import DefaultResourceManager
                from termin.materials import TcMaterial
                from termin.mesh.components import MeshComponent
                from termin.project import make_default_scene
                from termin.render_components import MeshRenderer
                from termin.scene import TcScene

                material_uuid = "00000000-0001-0000-0001-000000000003"
                expected_meshes = {
                    "Cube": "00000000-0000-0000-0003-000000000001",
                    "Ground": "00000000-0000-0000-0003-000000000003",
                }

                bootstrap_editor()
                resource_manager = DefaultResourceManager.instance()
                resource_manager.register_builtin_meshes()
                material = TcMaterial.create("NormalizedPBR", material_uuid)
                resource_manager.register_material("NormalizedPBR", material)

                source = TcScene.create("default-scene-source")
                restored = TcScene.create("default-scene-restored")
                try:
                    assert source.load_from_data(make_default_scene()["scene"]) == 4
                    serialized = source.serialize()

                    for entity_name, mesh_uuid in expected_meshes.items():
                        entity = source.find_entity_by_name(entity_name)
                        mesh_component = entity.get_component(MeshComponent)
                        renderer = entity.get_component(MeshRenderer)
                        assert mesh_component is not None
                        assert renderer is not None
                        assert mesh_component.mesh.uuid == mesh_uuid
                        assert renderer.material.uuid == material_uuid

                        entity_data = next(
                            item for item in serialized["entities"]
                            if item["name"] == entity_name
                        )
                        components = {
                            item["type"]: item["data"]
                            for item in entity_data["components"]
                        }
                        assert components["MeshComponent"]["mesh"] == {
                            "uuid": mesh_uuid,
                            "name": "Cube" if entity_name == "Cube" else "Plane",
                            "type": "uuid",
                            "kind": "tc_mesh",
                        }
                        assert "mesh" not in components["MeshRenderer"]
                        assert components["MeshRenderer"]["material"] == {
                            "uuid": material_uuid,
                            "name": "NormalizedPBR",
                            "type": "uuid",
                            "kind": "tc_material",
                        }

                    assert restored.load_from_data(serialized) == 4
                    reserialized = restored.serialize()
                    for entity_name, mesh_uuid in expected_meshes.items():
                        entity_data = next(
                            item for item in reserialized["entities"]
                            if item["name"] == entity_name
                        )
                        components = {
                            item["type"]: item["data"]
                            for item in entity_data["components"]
                        }
                        assert components["MeshComponent"]["mesh"]["uuid"] == mesh_uuid
                        assert components["MeshRenderer"]["material"]["uuid"] == material_uuid
                finally:
                    restored.destroy()
                    source.destroy()
                    DefaultResourceManager.shutdown_instance()
                    shutdown_editor()
                """
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "[ERROR]" not in output
