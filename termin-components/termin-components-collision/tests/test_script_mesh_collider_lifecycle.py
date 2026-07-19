import subprocess
import sys
import textwrap


def _run_isolated(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_script_mesh_roundtrip_builds_convex_hull_after_mesh_publication() -> None:
    result = _run_isolated(
        """
        from termin.bootstrap import bootstrap_player, shutdown_runtime
        from termin.colliders import ColliderType
        from termin.colliders.collider_component import ColliderComponent
        from termin.mesh import MeshComponent, ScriptMeshComponent
        from termin.scene import TcScene
        from tmesh import TcMesh

        bootstrap_player()

        source = TcScene.create("script-mesh-collider-source")
        entity = source.create_entity("Generated")
        script = ScriptMeshComponent()
        entity.add_component(script)

        collider = ColliderComponent()
        collider.collider_type = "ConvexHull"
        collider.convex_hull_mesh_source = "MeshComponent"
        entity.add_component(collider)
        assert collider.collider.type() == ColliderType.ConvexHull

        payload = source.serialize()
        components = payload["entities"][0]["components"]
        components.sort(
            key=lambda item: {
                "MeshComponent": 0,
                "ColliderComponent": 1,
                "ScriptMeshComponent": 2,
            }.get(item["type"], 3)
        )
        source.destroy()

        restored = TcScene.create("script-mesh-collider-restored")
        restored.load_from_data(payload)
        restored_entity = restored.find_entity_by_name("Generated")
        restored_mesh = restored_entity.get_component(MeshComponent)
        restored_script = restored_entity.get_component(ScriptMeshComponent)
        restored_collider = restored_entity.get_component(ColliderComponent)

        assert restored_mesh.mesh_is_generated
        assert restored_mesh.mesh.vertex_count == 36
        assert restored_collider.collider.type() == ColliderType.ConvexHull

        revision = restored_collider.collider_revision
        restored_mesh.notify_mesh_changed()
        assert restored_collider.collider_revision == revision + 1

        restored_mesh.set_generated_mesh(TcMesh())
        assert restored_collider.collider is None
        restored_script.generate()
        assert restored_mesh.mesh.vertex_count == 36
        assert restored_collider.collider.type() == ColliderType.ConvexHull

        restored.destroy()
        shutdown_runtime()
        """
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "[TcMesh] Mesh 'script_mesh' not found" not in output
    assert "requires a valid entity" not in output
    assert "requires source mesh with loaded vertex data" not in output
    assert "[ERROR]" not in output


def test_invalid_convex_hull_source_reports_once_without_fallback_box() -> None:
    result = _run_isolated(
        """
        from termin.bootstrap import bootstrap_player, shutdown_runtime
        from termin.colliders.collider_component import ColliderComponent
        from termin.scene import TcScene

        bootstrap_player()
        scene = TcScene.create("invalid-convex-hull-source")
        entity = scene.create_entity("Invalid")

        collider = ColliderComponent()
        collider.collider_type = "ConvexHull"
        collider.convex_hull_mesh_source = "MeshComponent"
        entity.add_component(collider)

        assert collider.collider is None
        scene.update(0.0)
        collider.rebuild_collider()
        collider.rebuild_collider()
        assert collider.collider is None

        scene.destroy()
        shutdown_runtime()
        """
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    message = (
        "ColliderComponent: ConvexHull MeshComponent source requires "
        "MeshComponent on the same entity"
    )
    assert output.count(message) == 1, output
    assert "failed to create collider" not in output
    assert "requires a valid entity" not in output
