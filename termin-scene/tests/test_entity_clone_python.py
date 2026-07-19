import subprocess
import sys
import textwrap


def _run_python(code: str) -> None:
    subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=True,
    )


def test_entity_clone_preserves_python_component_data_and_parent():
    _run_python(
        """
        import termin.bootstrap
        from termin.inspect import InspectField
        from termin.scene import Entity, PythonComponent, TcScene, publish_python_component

        termin.bootstrap.bootstrap_player()

        class ProbeClonePythonComponent(PythonComponent):
            inspect_fields = {
                "value": InspectField(path="value", label="Value", kind="int"),
            }

            def __init__(self):
                super().__init__()
                self.value = 0

        publish_python_component(ProbeClonePythonComponent, owner="termin-scene-test")

        scene = TcScene.create("python-clone-test")
        parent = scene.create_entity("parent")
        root = scene.create_entity("root")
        root.set_parent(parent)

        component = ProbeClonePythonComponent()
        component.value = 37
        root.add_component(component)
        assert component.source_id

        source_data = root.serialize_hierarchy()
        assert source_data["uuid"] == root.uuid
        assert source_data["name"] == "root"
        assert source_data["components"][0]["type"] == "ProbeClonePythonComponent"
        assert source_data["components"][0]["source_id"] == component.source_id
        assert source_data["components"][0]["data"]["value"] == 37

        clone_data, uuid_remap = Entity.make_clone_payload(source_data, "_copy")
        assert clone_data["name"] == "root_copy"
        assert clone_data["uuid"] != root.uuid
        assert clone_data["components"][0]["type"] == "ProbeClonePythonComponent"
        assert clone_data["components"][0]["data"]["value"] == 37
        clone_data = Entity.remap_entity_refs(clone_data, uuid_remap)

        clone_from_data = Entity.deserialize_hierarchy(clone_data, scene, parent)
        assert clone_from_data is not None
        assert clone_from_data.valid()
        assert clone_from_data.name == "root_copy"
        assert clone_from_data.parent == parent
        cloned_from_data_component = clone_from_data.get_python_component("ProbeClonePythonComponent")
        assert cloned_from_data_component is not None
        assert cloned_from_data_component.value == 37
        assert cloned_from_data_component.source_id == component.source_id

        clone = root.clone("_copy")
        assert clone is not None
        assert clone.valid()
        assert clone.name == "root_copy"
        assert clone.parent == parent

        cloned_component = clone.get_python_component("ProbeClonePythonComponent")
        assert cloned_component is not None
        assert cloned_component.value == 37
        assert cloned_component is not component

        scene.destroy()
        termin.bootstrap.shutdown_player()
        """
    )


def test_python_entity_constructor_and_scene_migration_preserve_explicit_uuid():
    _run_python(
        """
        import termin.bootstrap
        from termin.scene import Entity, TcScene

        termin.bootstrap.bootstrap_player()

        uuid = "python-entity-stable-uuid"
        standalone = Entity("standalone", uuid)
        assert standalone.uuid == uuid

        scene = TcScene.create("python-entity-migration")
        migrated = scene.migrate_entity(standalone)
        assert migrated.valid()
        assert migrated.uuid == uuid
        assert scene.get_entity(uuid) == migrated

        duplicate = Entity("duplicate", uuid)
        assert duplicate.uuid == uuid
        rejected = scene.migrate_entity(duplicate)
        assert not rejected.valid()
        assert duplicate.valid()
        assert scene.get_entity(uuid) == migrated
        """
    )
