import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from termin.prefab.asset import PrefabAsset
from termin.prefab.asset_plugin import create_import_plugin, create_runtime_plugin
from termin_assets import AssetContext, PreLoadResult


_OVERLAY = Path(__file__).resolve().parents[2] / "build/python-envs/test/overlay.json"


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


def _empty_entity_data(uuid: str, name: str) -> dict[str, object]:
    return {
        "uuid": uuid,
        "name": name,
        "priority": 0,
        "visible": True,
        "enabled": True,
        "pickable": True,
        "selectable": True,
        "layer": 0,
        "flags": 0,
        "pose": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0, 1.0],
        },
        "scale": [1.0, 1.0, 1.0],
        "components": [],
        "children": [],
    }


def _run_python(code: str) -> None:
    subprocess.run(
        [sys.executable, "--termin-overlay", str(_OVERLAY), "-c", textwrap.dedent(code)],
        check=True,
    )


def test_prefab_runtime_plugin_registers_lazy_asset() -> None:
    resource_manager = FakeResourceManager()
    result = PreLoadResult(
        resource_type="prefab",
        path="/tmp/Enemy.prefab",
        uuid="prefab-uuid",
    )

    create_runtime_plugin().register(
        AssetContext(resource_manager=resource_manager, name="Enemy", uuid="prefab-uuid"),
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
        '{"version": "3.0", "uuid": "prefab-uuid", "root": {"uuid": "enemy-root", "name": "Enemy", "components": [], "children": []}}',
        encoding="utf-8",
    )

    result = create_import_plugin().preload(str(prefab_path))

    assert result is not None
    assert result.resource_type == "prefab"
    assert result.uuid == "prefab-uuid"
    assert result.content is not None


def test_prefab_asset_file_helpers(tmp_path: Path) -> None:
    prefab_path = tmp_path / "Enemy.prefab"
    root_data = _empty_entity_data("enemy-root", "Enemy")
    prefab_path.write_text(
        json.dumps({"version": "3.0", "uuid": "prefab-uuid", "root": root_data}),
        encoding="utf-8",
    )

    asset = PrefabAsset.from_file(prefab_path)

    assert asset.name == "Enemy"
    assert asset.uuid == "prefab-uuid"
    assert asset.root_data == root_data
    assert asset.get_entity_count() == 1


def test_prefab_entry_point_factories() -> None:
    assert create_import_plugin().type_id == "prefab"
    assert create_runtime_plugin().type_id == "prefab"


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


def test_prefab_hot_reload_reaches_only_live_native_instances() -> None:
    _run_python(
        """
        import copy

        import termin.bootstrap
        from termin.inspect import InspectField
        from termin.prefab import (
            PrefabInstanceState,
            PrefabOverrideValue,
            PrefabReconcilePhase,
            count_live_instances,
            find_live_instances,
        )
        from termin.prefab.asset import PrefabAsset
        from termin.prefab.persistence import document_from_data
        from termin.scene import PythonComponent, TcScene, publish_python_component

        termin.bootstrap.bootstrap_player()

        class PrefabHotReloadProbe(PythonComponent):
            inspect_fields = {
                "value": InspectField(path="value", label="Value", kind="int"),
            }

            def __init__(self):
                super().__init__()
                self.value = 0

        publish_python_component(PrefabHotReloadProbe)
        source_scene = TcScene.create("prefab-hot-reload-source")
        source_root = source_scene.create_entity("Root")
        source_component = PrefabHotReloadProbe()
        source_component.value = 1
        source_root.add_component(source_component)
        asset = PrefabAsset.from_entity(source_root, name="HotReload")

        first_scene = TcScene.create("prefab-hot-reload-first")
        second_scene = TcScene.create("prefab-hot-reload-second")
        first = asset.instantiate(scene=first_scene)
        doomed = asset.instantiate(scene=first_scene)
        second = asset.instantiate(scene=second_scene)
        assert count_live_instances(asset.uuid) == 3
        assert len(find_live_instances(asset.uuid)) == 3

        doomed_state = doomed.get_component(PrefabInstanceState)
        assert doomed_state is not None
        assert doomed_state.prefab_asset_uuid == asset.uuid
        first_scene.remove_entity(doomed)
        assert not doomed.valid()
        assert count_live_instances(asset.uuid) == 2

        updated_data = copy.deepcopy(asset.data)
        updated_data["root"]["components"][0]["data"]["value"] = 9
        updated = PrefabAsset(
            data=updated_data,
            name="HotReload",
            uuid=asset.uuid,
        )
        asset.update_from(updated)

        assert first.get_python_component("PrefabHotReloadProbe").value == 9
        assert second.get_python_component("PrefabHotReloadProbe").value == 9
        expected_revision = document_from_data(updated_data).source_revision
        assert first.get_component(PrefabInstanceState).source_revision == expected_revision
        assert second.get_component(PrefabInstanceState).source_revision == expected_revision

        structural_data = copy.deepcopy(updated_data)
        added_child = copy.deepcopy(structural_data["root"])
        added_child.update({
            "uuid": "hot-reload-added-child",
            "name": "AddedChild",
            "components": [],
            "children": [],
        })
        structural_data["root"]["children"].append(added_child)
        structural = PrefabAsset(
            data=structural_data,
            name="HotReload",
            uuid=asset.uuid,
        )
        structural_result = structural.apply_to_instance(first)
        assert structural_result.ok
        assert structural_result.structure_operation_count >= 1
        assert (
            structural_result.structure_operations_applied
            == structural_result.structure_operation_count
        )
        assert first.find_child("AddedChild").valid()
        removal_result = updated.apply_to_instance(first)
        assert removal_result.ok
        assert not first.find_child("AddedChild").valid()

        first_state = first.get_component(PrefabInstanceState)
        first_probe = first.get_python_component("PrefabHotReloadProbe")
        first_probe.value = 42
        first_state.set_property_override(
            updated_data["root"]["uuid"],
            updated_data["root"]["components"][0]["source_id"],
            "value",
            "int",
            PrefabOverrideValue.from_python(42, kind="int"),
        )
        overridden_data = copy.deepcopy(updated_data)
        overridden_data["root"]["components"][0]["data"]["value"] = 11
        overridden = PrefabAsset(
            data=overridden_data,
            name="HotReload",
            uuid=asset.uuid,
        )
        overridden_result = overridden.apply_to_instance(first)
        assert overridden_result.ok
        assert overridden_result.revision_updated
        assert overridden_result.override_count == 1
        assert overridden_result.overrides_applied == 1
        assert first_probe.value == 42
        assert first_state.property_override_count == 1

        broken_data = copy.deepcopy(overridden_data)
        broken_data["root"]["components"][0]["data"]["unknown_field"] = 5
        broken = PrefabAsset(data=broken_data, name="HotReload", uuid=asset.uuid)
        completed_revision = first_state.source_revision
        broken_result = broken.apply_to_instance(first)
        assert not broken_result.ok
        assert not broken_result.revision_updated
        assert first_state.source_revision == completed_revision
        assert len(broken_result.failures) == 1
        assert broken_result.failures[0].phase == PrefabReconcilePhase.SOURCE_VALUE
        assert broken_result.failures[0].field_path == "unknown_field"
        assert first_state.property_override_count == 1
        assert first_probe.value == 42

        first_scene.destroy()
        assert count_live_instances(asset.uuid) == 1
        second_scene.destroy()
        assert count_live_instances(asset.uuid) == 0
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
        base = {
            "priority": 0,
            "visible": True,
            "enabled": True,
            "pickable": True,
            "selectable": True,
            "layer": 0,
            "flags": 0,
            "pose": {
                "position": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
            },
            "scale": [1.0, 1.0, 1.0],
            "components": [],
            "children": [],
        }
        asset = PrefabAsset(
            name="Broken",
            uuid="broken-prefab",
            data={
                "version": "3.0",
                "uuid": "broken-prefab",
                "root": {
                    **base,
                    "uuid": "duplicate-source-id",
                    "name": "Root",
                    "children": [{
                        **base,
                        "uuid": "duplicate-source-id",
                        "name": "Child",
                    }],
                },
            },
        )

        try:
            asset.instantiate(scene=scene)
        except RuntimeError as exc:
            assert "duplicates entity source identity" in str(exc)
        else:
            raise AssertionError("invalid prefab must fail")

        assert scene.entity_count() == initial_count
        scene.destroy()
        termin.bootstrap.shutdown_player()
        """
    )


def test_prefab_v3_persistence_rejects_legacy_and_saves_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from termin.prefab._prefab_native import PrefabDocument
    from termin.prefab.persistence import atomic_write_document, load_document

    legacy_path = tmp_path / "Legacy.prefab"
    legacy_path.write_text(
        '{"version":"2.0","uuid":"legacy","root":{}}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported prefab version"):
        load_document(legacy_path)
    assert legacy_path.read_text(encoding="utf-8").startswith('{"version":"2.0"')

    target = tmp_path / "Atomic.prefab"
    target.write_text("original", encoding="utf-8")
    document = PrefabDocument.empty("asset-id", "root-id", "[Root]")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError(f"replace failed: {source} -> {destination}")

    monkeypatch.setattr("termin.prefab.persistence.os.replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        atomic_write_document(document, target)

    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob("*.tmp")) == []
