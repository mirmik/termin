import subprocess
import sys
import textwrap


def test_script_mesh_roundtrip_has_one_mesh_and_no_missing_renderer_error() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                from termin.bootstrap import bootstrap_player, shutdown_runtime
                from termin.mesh import MeshComponent, ScriptMeshComponent
                from termin.scene import ComponentRegistry, TcScene

                bootstrap_player()
                assert ComponentRegistry.instance().requirements_of(
                    "ScriptMeshComponent"
                ) == ["MeshComponent"]

                source = TcScene.create("script-mesh-source")
                entity = source.create_entity("Generated")
                entity.add_component(ScriptMeshComponent())
                assert source.consume_render_request()
                payload = source.serialize()

                components = payload["entities"][0]["components"]
                components.sort(
                    key=lambda item: 0 if item["type"] == "ScriptMeshComponent" else 1
                )
                source.destroy()

                restored = TcScene.create("script-mesh-restored")
                restored.load_from_data(payload)
                restored_entity = restored.find_entity_by_name("Generated")
                mesh_components = [
                    component
                    for component in restored_entity.components
                    if isinstance(component, MeshComponent)
                ]
                assert len(mesh_components) == 1
                assert mesh_components[0].mesh.is_valid

                restored.destroy()
                shutdown_runtime()
                """
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "[RenderingManager] instance() called but no instance set" not in output
    assert "[ScriptMeshComponent] Failed to request render update" not in output
