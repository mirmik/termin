import subprocess
import sys
import textwrap


def _run_python(code: str) -> None:
    subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=True,
    )


def test_prefab_edit_controller_roundtrips_v3_hierarchy(tmp_path) -> None:
    _run_python(
        f"""
        import termin.bootstrap
        from termin.editor_core.prefab_edit_controller import PrefabEditController
        from termin.engine import SceneManager
        from termin.inspect import InspectField
        from termin.prefab.persistence import PrefabPersistence, load_document
        from termin.scene import PythonComponent, publish_python_component

        class PrefabRoundtripProbe(PythonComponent):
            inspect_fields = {{
                "target": InspectField(path="target", label="Target", kind="entity"),
            }}

            def __init__(self):
                super().__init__()
                self.target = None

        termin.bootstrap.bootstrap_player()
        publish_python_component(PrefabRoundtripProbe, owner="termin-app-test")
        manager = SceneManager()
        editor_scene = manager.create_scene("editor", [])
        author_scene = manager.create_scene("author", [])
        root = author_scene.create_entity("[Root]")
        child = root.create_child("Child")
        child.create_child("Grandchild")
        root_uuid = root.uuid
        child_uuid = child.uuid
        component = PrefabRoundtripProbe()
        component.target = child
        root.add_component(component)
        component_source_id = component.source_id

        path = {str(tmp_path / 'Nested.prefab')!r}
        persistence = PrefabPersistence()
        persistence.save(root, path, uuid="prefab-asset-id")
        manager.close_scene("author")

        controller = PrefabEditController(
            manager,
            object(),
            get_editor_scene_name=lambda: "editor",
        )
        assert controller.open_prefab(path)
        assert controller.root_entity.valid()
        assert controller.root_entity.uuid == root_uuid
        loaded_child = controller.root_entity.find_child("Child")
        assert loaded_child.valid()
        assert loaded_child.uuid == child_uuid
        assert loaded_child.find_child("Grandchild").valid()
        loaded_component = controller.root_entity.get_python_component("PrefabRoundtripProbe")
        assert loaded_component is not None
        assert loaded_component.source_id == component_source_id
        assert loaded_component.target == loaded_child

        loaded_child.name = "RenamedChild"
        assert controller.save()
        saved = load_document(path)
        assert saved.version == "3.0"
        assert saved.uuid == "prefab-asset-id"
        assert saved.data["root"]["children"][0]["name"] == "RenamedChild"
        assert saved.data["root"]["children"][0]["uuid"] == child_uuid
        saved_component = saved.data["root"]["components"][0]
        assert saved_component["source_id"] == component_source_id
        assert saved_component["data"]["target"]["uuid"] == child_uuid

        controller.exit()
        assert not manager.has_scene("prefab")
        manager.close_scene("editor")
        termin.bootstrap.shutdown_player()
        """
    )


def test_prefab_edit_controller_failed_load_leaves_editor_scene_untouched(tmp_path) -> None:
    legacy_path = tmp_path / "Legacy.prefab"
    legacy_path.write_text(
        '{"version":"2.0","uuid":"legacy","root":{}}',
        encoding="utf-8",
    )
    _run_python(
        f"""
        import termin.bootstrap
        from termin.editor_core.prefab_edit_controller import PrefabEditController
        from termin.engine import SceneManager, scene as engine_scene

        termin.bootstrap.bootstrap_player()
        manager = SceneManager()
        manager.create_scene("editor", [])
        manager.set_mode("editor", engine_scene.SceneMode.STOP)
        controller = PrefabEditController(
            manager,
            object(),
            get_editor_scene_name=lambda: "editor",
        )

        assert not controller.open_prefab({str(legacy_path)!r})
        assert not controller.is_editing
        assert controller.root_entity is None
        assert not manager.has_scene("prefab")
        assert manager.get_mode("editor") == engine_scene.SceneMode.STOP

        manager.close_scene("editor")
        termin.bootstrap.shutdown_player()
        """
    )
