from pathlib import Path
import subprocess
import sys
import textwrap

from termin.prefab.asset import PrefabAsset
from termin.prefab.asset_plugin import create_import_plugin, create_runtime_plugin
from termin_assets import AssetContext, PreLoadResult, set_resource_manager_factory


class FakeResourceManager:
    def __init__(self) -> None:
        self.prefabs = {}
        self.by_uuid = {}

    def get_prefab_asset(self, name: str):
        return self.prefabs.get(name)

    def get_prefab_by_uuid(self, uuid: str):
        return self.by_uuid.get(uuid)

    def register_prefab(self, name: str, asset, source_path: str | None = None) -> None:
        self.prefabs[name] = asset
        self.by_uuid[asset.uuid] = asset
        if source_path is not None:
            asset.source_path = source_path


def _run_python(code: str) -> None:
    subprocess.run([sys.executable, "-c", textwrap.dedent(code)], check=True)


def test_prefab_runtime_plugin_registers_lazy_asset() -> None:
    resource_manager = FakeResourceManager()
    result = PreLoadResult(
        resource_type="prefab",
        path="/tmp/Enemy.prefab",
        uuid="prefab-uuid",
    )

    create_runtime_plugin().register(
        AssetContext(resource_manager=resource_manager, name="Enemy"),
        result,
    )

    asset = resource_manager.get_prefab_asset("Enemy")
    assert isinstance(asset, PrefabAsset)
    assert asset.uuid == "prefab-uuid"
    assert asset.source_path == Path("/tmp/Enemy.prefab")
    assert not asset.is_loaded


def test_prefab_import_plugin_extracts_uuid(tmp_path: Path) -> None:
    prefab_path = tmp_path / "Enemy.prefab"
    prefab_path.write_text(
        '{"version": "2.0", "uuid": "prefab-uuid", "root": {"name": "Enemy"}}',
        encoding="utf-8",
    )

    result = create_import_plugin().preload(str(prefab_path))

    assert result is not None
    assert result.resource_type == "prefab"
    assert result.uuid == "prefab-uuid"
    assert result.content is not None


def test_prefab_asset_file_helpers(tmp_path: Path) -> None:
    prefab_path = tmp_path / "Enemy.prefab"
    prefab_path.write_text(
        '{"version": "2.0", "uuid": "prefab-uuid", "root": {"name": "Enemy", "children": []}}',
        encoding="utf-8",
    )

    asset = PrefabAsset.from_file(prefab_path)

    assert asset.name == "Enemy"
    assert asset.uuid == "prefab-uuid"
    assert asset.root_data == {"name": "Enemy", "children": []}
    assert asset.get_entity_count() == 1


def test_prefab_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "prefab"
    assert create_runtime_plugin().type_id == "prefab"


def test_prefab_instance_marker_uses_configured_resource_manager() -> None:
    from termin.prefab.instance_marker import PrefabInstanceMarker

    asset = PrefabAsset(name="Enemy", uuid="prefab-uuid")
    resource_manager = FakeResourceManager()
    resource_manager.by_uuid[asset.uuid] = asset

    set_resource_manager_factory(lambda: resource_manager)
    try:
        marker = PrefabInstanceMarker(prefab_uuid=asset.uuid)
        assert marker.get_prefab_asset() is asset
    finally:
        set_resource_manager_factory(None)


def test_prefab_asset_instantiates_complete_hierarchy_in_target_scene() -> None:
    _run_python(
        """
        import termin.bootstrap
        from termin.prefab.asset import PrefabAsset
        from termin.scene import TcScene

        termin.bootstrap.bootstrap_player()

        source_scene = TcScene.create("prefab-source")
        source_root = source_scene.create_entity("Root")
        source_child = source_root.create_child("Child")
        source_child.create_child("Grandchild")
        asset = PrefabAsset.from_entity(source_root, name="Nested")

        assert asset.get_entity_count() == 3
        assert len(asset.root_data["children"]) == 1
        assert len(asset.root_data["children"][0]["children"]) == 1

        target_scene = TcScene.create("prefab-target")
        parent = target_scene.create_entity("Parent")
        first = asset.instantiate(scene=target_scene, parent=parent.transform)
        second = asset.instantiate(scene=target_scene, parent=parent.transform)

        assert first.scene.equal(target_scene)
        assert second.scene.equal(target_scene)
        assert first.parent == parent
        assert second.parent == parent
        assert first.uuid != second.uuid
        assert first.uuid != source_root.uuid

        first_child = first.find_child("Child")
        second_child = second.find_child("Child")
        assert first_child is not None and first_child.valid()
        assert second_child is not None and second_child.valid()
        assert first_child.uuid != second_child.uuid
        assert first_child.find_child("Grandchild").valid()

        target_scene.destroy()
        source_scene.destroy()
        termin.bootstrap.shutdown_player()
        """
    )


def test_prefab_asset_reports_invalid_source_without_partial_scene_changes() -> None:
    _run_python(
        """
        import termin.bootstrap
        from termin.prefab.asset import PrefabAsset
        from termin.scene import TcScene

        termin.bootstrap.bootstrap_player()
        scene = TcScene.create("prefab-invalid-source")
        initial_count = scene.entity_count()
        asset = PrefabAsset(
            name="Broken",
            uuid="broken-prefab",
            data={
                "version": "2.0",
                "uuid": "broken-prefab",
                "root": {
                    "uuid": "duplicate-source-id",
                    "name": "Root",
                    "components": [],
                    "children": [{
                        "uuid": "duplicate-source-id",
                        "name": "Child",
                        "components": [],
                        "children": [],
                    }],
                },
            },
        )

        try:
            asset.instantiate(scene=scene)
        except RuntimeError as exc:
            assert "duplicates source uuid" in str(exc)
        else:
            raise AssertionError("invalid prefab must fail")

        assert scene.entity_count() == initial_count
        scene.destroy()
        termin.bootstrap.shutdown_player()
        """
    )
