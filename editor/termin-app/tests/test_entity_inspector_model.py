import pytest

from termin.bootstrap import bootstrap_player, shutdown_player
from termin.editor_core.entity_inspector_model import (
    EntityInspectorComponentType,
    EntityInspectorController,
)
from termin.editor_core.undo_stack import UndoStack
from termin.inspect import InspectField
from termin.scene import ComponentRegistry, PythonComponent, TcScene, publish_python_component


@pytest.fixture(scope="module", autouse=True)
def player_runtime():
    bootstrap_player()
    yield
    shutdown_player()


@pytest.fixture
def scene():
    value = TcScene.create("entity-inspector-model-test")
    yield value
    value.destroy()


def test_entity_inspector_properties_components_fields_and_undo(scene):
    entity = scene.create_entity("source")
    child = scene.create_entity("child")
    child.transform.set_parent(entity.transform)
    child.layer = 3
    entity.add_component(PythonComponent())
    stack = UndoStack()

    def set_enabled(component, value):
        component.enabled = bool(value)

    controller = EntityInspectorController(
        undo_handler=stack.push,
        field_collector=lambda _component: {
            "enabled": InspectField(
                path="enabled",
                label="Enabled",
                kind="bool",
                getter=lambda component: component.enabled,
                setter=set_enabled,
            )
        },
        metadata_collector=lambda _component: {},
    )
    controller.set_scene(scene)

    snapshot = controller.set_target(entity)
    assert snapshot.name == "source"
    assert snapshot.uuid == entity.uuid
    assert snapshot.layer == 0
    assert len(snapshot.layer_names) == 64
    assert [component.type_name for component in snapshot.components] == ["PythonComponent"]
    assert snapshot.transform.enabled
    assert snapshot.transform.position == pytest.approx((0.0, 0.0, 0.0))
    assert snapshot.transform.rotation_degrees == pytest.approx((0.0, 0.0, 0.0))
    assert snapshot.transform.scale == pytest.approx((1.0, 1.0, 1.0))

    controller.set_transform(
        (1.0, 2.0, 3.0),
        (10.0, 20.0, 30.0),
        (2.0, 3.0, 4.0),
    )
    snapshot = controller.snapshot
    assert snapshot.transform.position == pytest.approx((1.0, 2.0, 3.0))
    assert snapshot.transform.rotation_degrees == pytest.approx((10.0, 20.0, 30.0))
    assert snapshot.transform.scale == pytest.approx((2.0, 3.0, 4.0))

    controller.set_name("renamed")
    controller.set_layer(5)
    assert entity.name == "renamed"
    assert entity.layer == 5
    controller.apply_layer_to_descendants()
    assert child.layer == 5

    snapshot = controller.select_component(0)
    assert snapshot.selected_component == 0
    assert snapshot.fields.field_row("enabled").value
    controller.fields.apply_value("enabled", False)
    component = entity.tc_components[0]
    assert not component.enabled

    stack.undo()
    assert component.enabled
    stack.undo()
    assert child.layer == 3
    stack.undo()
    assert entity.layer == 0
    stack.undo()
    assert entity.name == "source"
    stack.undo()
    assert tuple(entity.transform.local_pose().lin) == pytest.approx((0.0, 0.0, 0.0))


def test_entity_inspector_clears_fields_for_non_component_or_missing_target(scene):
    entity = scene.create_entity("source")
    controller = EntityInspectorController()
    snapshot = controller.set_target(entity)
    assert snapshot.components == ()

    snapshot = controller.select_component(0)
    assert snapshot.fields.rows == ()
    snapshot = controller.set_target(None)
    assert snapshot.entity is None
    assert snapshot.components == ()


def test_entity_inspector_component_catalog_add_remove_and_undo(scene):
    class InspectorModelAddProbeComponent(PythonComponent):
        component_category = "Editor/Internal"

    publish_python_component(InspectorModelAddProbeComponent, owner="termin-app-tests")

    type_name = "InspectorModelAddProbeComponent"
    entity = scene.create_entity("source")
    stack = UndoStack()
    component_types = (
        EntityInspectorComponentType(type_name, "Inspector Probe", "Editor/Internal"),
    )
    controller = EntityInspectorController(
        undo_handler=stack.push,
        component_type_collector=lambda: component_types,
    )
    try:
        controller.set_scene(scene)
        controller.set_target(entity)

        available = controller.available_component_types()
        probe = next(item for item in available if item.type_name == type_name)
        assert probe.display_name
        assert probe.category

        snapshot = controller.add_component(type_name)
        assert [component.type_name for component in snapshot.components] == [type_name]
        assert snapshot.selected_component == 0
        assert entity.has_tc_component(type_name)

        snapshot = controller.remove_selected_component()
        assert snapshot.components == ()
        assert snapshot.selected_component == -1
        assert not entity.has_tc_component(type_name)

        stack.undo()
        assert entity.has_tc_component(type_name)
        stack.undo()
        assert not entity.has_tc_component(type_name)
    finally:
        ComponentRegistry.instance().unregister_python(type_name)
