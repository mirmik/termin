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
        from termin.scene import Entity, PythonComponent, TcScene

        termin.bootstrap.bootstrap_player()

        class ProbeClonePythonComponent(PythonComponent):
            inspect_fields = {
                "value": InspectField(path="value", label="Value", kind="int"),
            }

            def __init__(self):
                super().__init__()
                self.value = 0

        scene = TcScene.create("python-clone-test")
        parent = scene.create_entity("parent")
        root = scene.create_entity("root")
        root.set_parent(parent)

        component = ProbeClonePythonComponent()
        component.value = 37
        root.add_component(component)

        source_data = root.serialize_hierarchy()
        assert source_data["uuid"] == root.uuid
        assert source_data["name"] == "root"
        assert source_data["components"][0]["type"] == "ProbeClonePythonComponent"
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
