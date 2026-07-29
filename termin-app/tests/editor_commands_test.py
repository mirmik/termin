import unittest
import math

import numpy as np

from termin.editor_core.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    DuplicateEntityCommand,
    EntityPropertyEditCommand,
    RenameEntityCommand,
    ReparentEntityCommand,
    RecursiveLayerChangeCommand,
    ScenePropertyEditCommand,
    SkyboxTypeEditCommand,
    TransformEditCommand,
    ComponentFieldEditCommand,
    RemoveComponentCommand,
)
from termin.editor_core.undo_stack import UndoStack
from termin.editor_core.inspector_fields_model import collect_inspect_fields
from termin.editor_core.entity_inspector_model import EntityInspectorController
from termin.geombase import GeneralPose3, Quat, Vec3
from termin.inspect import InspectField
from termin.scene import PythonComponent, TcScene, publish_python_component
from termin.bootstrap import bootstrap_player, shutdown_player
from termin.render import scene_render_state
from termin.prefab import (
    PrefabAsset,
    PrefabInstanceState,
    PrefabStructuralOverrideKind,
)


_EDITOR_PREFAB_PROBE_CLASS = None


def _rotation_z(radians: float) -> Quat:
    half = radians * 0.5
    return Quat(0.0, 0.0, math.sin(half), math.cos(half))


def _assert_affine_near(test, actual, expected, places: int = 9) -> None:
    for actual_column, expected_column in (
        (actual.basis.x, expected.basis.x),
        (actual.basis.y, expected.basis.y),
        (actual.basis.z, expected.basis.z),
        (actual.translation, expected.translation),
    ):
        for index in range(3):
            test.assertAlmostEqual(
                actual_column[index],
                expected_column[index],
                places=places,
            )


def _editor_prefab_probe_class():
    global _EDITOR_PREFAB_PROBE_CLASS
    if _EDITOR_PREFAB_PROBE_CLASS is None:
        class EditorPrefabProbe(PythonComponent):
            inspect_fields = {
                "weight": InspectField(path="weight", label="Weight", kind="float"),
            }

            def __init__(self) -> None:
                super().__init__()
                self.weight = 1.0

        _EDITOR_PREFAB_PROBE_CLASS = EditorPrefabProbe
    return _EDITOR_PREFAB_PROBE_CLASS


class TestEditorUndoCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_player()
        publish_python_component(_editor_prefab_probe_class(), owner="termin-app-tests")

    @classmethod
    def tearDownClass(cls) -> None:
        shutdown_player()

    def setUp(self) -> None:
        self.scene = TcScene.create("editor-command-test")

    def tearDown(self) -> None:
        self.scene.destroy()

    def test_transform_command_survives_delete_restore(self) -> None:
        entity = self.scene.create_entity("entity")
        uuid = entity.uuid
        old_pose = entity.transform.local_pose()
        new_pose = GeneralPose3(
            lin=Vec3(1.0, 2.0, 3.0),
            ang=old_pose.ang.copy(),
            scale=old_pose.scale.copy(),
        )

        stack = UndoStack()
        stack.push(TransformEditCommand(entity.transform, old_pose, new_pose))
        stack.push(DeleteEntityCommand(self.scene, entity))

        self.assertIsNone(self.scene.get_entity(uuid))

        stack.undo()
        restored = self.scene.get_entity(uuid)
        self.assertIsNotNone(restored)
        self.assertAlmostEqual(restored.transform.local_pose().lin[0], 1.0)

        stack.undo()
        restored = self.scene.get_entity(uuid)
        self.assertIsNotNone(restored)
        self.assertAlmostEqual(restored.transform.local_pose().lin[0], old_pose.lin[0])

    def test_rename_command_survives_delete_restore(self) -> None:
        entity = self.scene.create_entity("entity")
        uuid = entity.uuid

        stack = UndoStack()
        stack.push(RenameEntityCommand(entity, "entity", "renamed"))
        stack.push(DeleteEntityCommand(self.scene, entity))

        stack.undo()
        self.assertEqual(self.scene.get_entity(uuid).name, "renamed")

        stack.undo()
        self.assertEqual(self.scene.get_entity(uuid).name, "entity")

    def test_add_entity_redo_restores_parent(self) -> None:
        parent = self.scene.create_entity("parent")
        entity = self.scene.create_entity("child")
        entity.transform.set_parent(parent.transform)
        entity_uuid = entity.uuid
        parent_uuid = parent.uuid

        stack = UndoStack()
        stack.push(AddEntityCommand(self.scene, entity))
        stack.undo()
        self.assertIsNone(self.scene.get_entity(entity_uuid))

        stack.redo()
        restored = self.scene.get_entity(entity_uuid)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.transform.parent.entity.uuid, parent_uuid)

    def test_reparent_command_survives_parent_restore(self) -> None:
        parent = self.scene.create_entity("parent")
        child = self.scene.create_entity("child")
        child.transform.set_parent(parent.transform)
        parent_uuid = parent.uuid

        stack = UndoStack()
        stack.push(ReparentEntityCommand(child, parent.transform, None))
        stack.push(DeleteEntityCommand(self.scene, parent))

        stack.undo()
        restored_parent = self.scene.get_entity(parent_uuid)
        self.assertIsNotNone(restored_parent)

        stack.undo()
        self.assertEqual(child.transform.parent.entity.uuid, parent_uuid)

    def test_reparent_command_restores_persistent_sibling_order(self) -> None:
        self.scene.create_entity("first")
        self.scene.create_entity("second")
        third = self.scene.create_entity("third")
        stack = UndoStack()

        stack.push(
            ReparentEntityCommand(
                third,
                None,
                None,
                new_sibling_index=0,
            )
        )
        self.assertEqual(
            [entity.name for entity in self.scene.root_entities],
            ["third", "first", "second"],
        )

        stack.undo()
        self.assertEqual(
            [entity.name for entity in self.scene.root_entities],
            ["first", "second", "third"],
        )

    def test_reparent_preserves_exact_world_affine_without_undo_drift(self) -> None:
        parent = self.scene.create_entity("uniform-parent")
        parent.transform.set_local_pose(
            GeneralPose3(
                ang=_rotation_z(0.35),
                lin=Vec3(3.0, -1.0, 2.0),
                scale=Vec3(2.0, 2.0, 2.0),
            )
        )
        child = self.scene.create_entity("child")
        child.transform.set_local_pose(
            GeneralPose3(
                ang=_rotation_z(-0.2),
                lin=Vec3(7.0, 4.0, -3.0),
                scale=Vec3(1.0, 1.0, 1.0),
            )
        )
        expected_world = child.transform.global_affine()
        expected_root_local = child.transform.local_pose()

        stack = UndoStack()
        stack.push(ReparentEntityCommand(child, None, parent.transform))
        _assert_affine_near(self, child.transform.global_affine(), expected_world)

        for _ in range(10):
            stack.undo()
            self.assertIsNone(child.transform.parent)
            _assert_affine_near(self, child.transform.global_affine(), expected_world)
            self.assertAlmostEqual(
                child.transform.local_pose().lin.x,
                expected_root_local.lin.x,
            )
            stack.redo()
            self.assertEqual(child.parent, parent)
            _assert_affine_near(self, child.transform.global_affine(), expected_world)

    def test_reparent_accepts_axis_scaled_and_affine_parent_when_exact(self) -> None:
        axis_parent = self.scene.create_entity("axis-parent")
        axis_parent.transform.set_local_scale(Vec3(2.0, 3.0, 4.0))
        rigid = self.scene.create_entity("rigid")
        rigid.transform.set_local_position(Vec3(5.0, -2.0, 1.0))
        rigid_world = rigid.transform.global_affine()

        stack = UndoStack()
        stack.push(ReparentEntityCommand(rigid, None, axis_parent.transform))
        _assert_affine_near(self, rigid.transform.global_affine(), rigid_world)
        stack.undo()
        _assert_affine_near(self, rigid.transform.global_affine(), rigid_world)

        affine_a = axis_parent.create_child("affine-a")
        affine_b = axis_parent.create_child("affine-b")
        shared_rotation = _rotation_z(0.5)
        affine_a.transform.set_local_pose(
            GeneralPose3(
                ang=shared_rotation,
                lin=Vec3(1.0, 0.0, 0.0),
                scale=Vec3(1.0, 1.0, 1.0),
            )
        )
        affine_b.transform.set_local_pose(
            GeneralPose3(
                ang=shared_rotation,
                lin=Vec3(-3.0, 2.0, 0.0),
                scale=Vec3(1.0, 1.0, 1.0),
            )
        )
        affine_child = affine_a.create_child("affine-child")
        affine_child.transform.set_local_position(Vec3(2.0, 1.0, 0.0))
        affine_world = affine_child.transform.global_affine()

        stack.push(
            ReparentEntityCommand(
                affine_child,
                affine_a.transform,
                affine_b.transform,
            )
        )
        self.assertEqual(affine_child.parent, affine_b)
        _assert_affine_near(
            self,
            affine_child.transform.global_affine(),
            affine_world,
        )

    def test_reparent_rejects_irreducible_local_shear_transactionally(self) -> None:
        axis_parent = self.scene.create_entity("axis-parent")
        axis_parent.transform.set_local_scale(Vec3(2.0, 3.0, 4.0))
        affine_parent = axis_parent.create_child("affine-parent")
        affine_parent.transform.set_local_rotation(_rotation_z(0.5))
        child = affine_parent.create_child("child")
        child.transform.set_local_position(Vec3(2.0, 1.0, 0.0))

        old_parent = child.parent
        old_local = child.transform.local_pose()
        old_world = child.transform.global_affine()
        old_sibling_index = child.sibling_index
        stack = UndoStack()

        with self.assertRaises(RuntimeError):
            stack.push(
                ReparentEntityCommand(
                    child,
                    affine_parent.transform,
                    None,
                )
            )

        self.assertFalse(stack.can_undo)
        self.assertEqual(child.parent, old_parent)
        self.assertEqual(child.sibling_index, old_sibling_index)
        self.assertAlmostEqual(
            child.transform.local_pose().lin.x,
            old_local.lin.x,
        )
        _assert_affine_near(self, child.transform.global_affine(), old_world)

    def test_delete_entity_command_restores_subtree_in_one_undo(self) -> None:
        root = self.scene.create_entity("root")
        child = self.scene.create_entity("child")
        grandchild = self.scene.create_entity("grandchild")
        child.transform.set_parent(root.transform)
        grandchild.transform.set_parent(child.transform)

        root_uuid = root.uuid
        child_uuid = child.uuid
        grandchild_uuid = grandchild.uuid

        stack = UndoStack()
        stack.push(DeleteEntityCommand(self.scene, root))

        self.assertIsNone(self.scene.get_entity(root_uuid))
        self.assertIsNone(self.scene.get_entity(child_uuid))
        self.assertIsNone(self.scene.get_entity(grandchild_uuid))

        stack.undo()

        restored_root = self.scene.get_entity(root_uuid)
        restored_child = self.scene.get_entity(child_uuid)
        restored_grandchild = self.scene.get_entity(grandchild_uuid)
        self.assertIsNotNone(restored_root)
        self.assertIsNotNone(restored_child)
        self.assertIsNotNone(restored_grandchild)
        self.assertEqual(restored_child.transform.parent.entity.uuid, root_uuid)
        self.assertEqual(restored_grandchild.transform.parent.entity.uuid, child_uuid)

        stack.redo()
        self.assertIsNone(self.scene.get_entity(root_uuid))
        self.assertIsNone(self.scene.get_entity(child_uuid))
        self.assertIsNone(self.scene.get_entity(grandchild_uuid))

    def test_duplicate_entity_command_duplicates_subtree(self) -> None:
        root = self.scene.create_entity("root")
        child = self.scene.create_entity("child")
        grandchild = self.scene.create_entity("grandchild")
        child.transform.set_parent(root.transform)
        grandchild.transform.set_parent(child.transform)

        stack = UndoStack()
        cmd = DuplicateEntityCommand(self.scene, root)
        stack.push(cmd)

        duplicated_root = cmd.entity
        self.assertIsNotNone(duplicated_root)
        self.assertEqual(duplicated_root.name, "root_copy")
        self.assertNotEqual(duplicated_root.uuid, root.uuid)

        duplicated_children = list(duplicated_root.transform.children)
        self.assertEqual(len(duplicated_children), 1)
        duplicated_child = duplicated_children[0].entity
        self.assertIsNotNone(duplicated_child)
        self.assertEqual(duplicated_child.name, "child")
        self.assertNotEqual(duplicated_child.uuid, child.uuid)
        self.assertEqual(duplicated_child.transform.parent.entity.uuid, duplicated_root.uuid)

        duplicated_grandchildren = list(duplicated_child.transform.children)
        self.assertEqual(len(duplicated_grandchildren), 1)
        duplicated_grandchild = duplicated_grandchildren[0].entity
        self.assertIsNotNone(duplicated_grandchild)
        self.assertEqual(duplicated_grandchild.name, "grandchild")
        self.assertNotEqual(duplicated_grandchild.uuid, grandchild.uuid)
        self.assertEqual(duplicated_grandchild.transform.parent.entity.uuid, duplicated_child.uuid)

        duplicated_root_uuid = duplicated_root.uuid
        duplicated_child_uuid = duplicated_child.uuid
        duplicated_grandchild_uuid = duplicated_grandchild.uuid

        stack.undo()

        self.assertIsNone(self.scene.get_entity(duplicated_root_uuid))
        self.assertIsNone(self.scene.get_entity(duplicated_child_uuid))
        self.assertIsNone(self.scene.get_entity(duplicated_grandchild_uuid))

        stack.redo()
        self.assertEqual(cmd.entity.uuid, duplicated_root_uuid)
        self.assertIsNotNone(self.scene.get_entity(duplicated_child_uuid))
        self.assertIsNotNone(self.scene.get_entity(duplicated_grandchild_uuid))

    def test_duplicate_entity_command_remaps_python_component_entity_refs(self) -> None:
        class DuplicateEntityRefComponent(PythonComponent):
            inspect_fields = {
                "target": InspectField(path="target", label="Target", kind="entity"),
            }

            def __init__(self) -> None:
                super().__init__()
                self.target = None

        publish_python_component(DuplicateEntityRefComponent, owner="termin-app-tests")

        root = self.scene.create_entity("root")
        child = self.scene.create_entity("child")
        child.transform.set_parent(root.transform)

        component = DuplicateEntityRefComponent()
        component.target = child
        root.add_component(component)

        stack = UndoStack()
        cmd = DuplicateEntityCommand(self.scene, root)
        stack.push(cmd)

        duplicated_root = cmd.entity
        self.assertIsNotNone(duplicated_root)
        duplicated_child = list(duplicated_root.transform.children)[0].entity
        duplicated_component = duplicated_root.get_python_component("DuplicateEntityRefComponent")

        self.assertIsNotNone(duplicated_component)
        self.assertIsNotNone(duplicated_component.target)
        self.assertEqual(duplicated_component.target.uuid, duplicated_child.uuid)
        self.assertNotEqual(duplicated_component.target.uuid, child.uuid)

    def test_entity_property_command_edits_name_and_layer(self) -> None:
        entity = self.scene.create_entity("entity")

        stack = UndoStack()
        stack.push(EntityPropertyEditCommand(entity, "name", "entity", "renamed"))
        stack.push(EntityPropertyEditCommand(entity, "layer", 0, 3))

        self.assertEqual(entity.name, "renamed")
        self.assertEqual(entity.layer, 3)

        stack.undo()
        self.assertEqual(entity.layer, 0)

        stack.undo()
        self.assertEqual(entity.name, "entity")

        stack.redo()
        self.assertEqual(entity.name, "renamed")

    def _create_prefab_instance(self):
        source_scene = TcScene.create("editor-command-prefab-source")
        source_root = source_scene.create_entity("PrefabRoot")
        source_child = source_root.create_child("SourceChild")
        source_probe = _editor_prefab_probe_class()()
        source_child.add_component(source_probe)
        asset = PrefabAsset.from_entity(source_root, name="EditorCommandPrefab")
        source_ids = (source_child.uuid, source_probe.source_id)
        instance = asset.instantiate(scene=self.scene)
        return source_scene, asset, instance, source_ids

    def test_prefab_property_commands_capture_and_restore_override_metadata(self) -> None:
        source_scene, asset, instance, (child_source_id, component_source_id) = (
            self._create_prefab_instance())
        try:
            state = instance.get_component(PrefabInstanceState)
            child = state.entity_for_source(child_source_id)
            component = child.get_tc_component("EditorPrefabProbe")
            field = collect_inspect_fields(component)["weight"]
            stack = UndoStack()

            stack.push(EntityPropertyEditCommand(child, "name", child.name, "Customized"))
            stack.push(ComponentFieldEditCommand(component, field, 1.0, 4.5))

            self.assertEqual(state.property_override_count, 2)
            refresh = asset.apply_to_instance(instance)
            self.assertTrue(refresh.ok)
            self.assertEqual(child.name, "Customized")
            self.assertAlmostEqual(component.get_field("weight"), 4.5)

            stack.undo()
            self.assertEqual(state.property_override_count, 1)
            self.assertAlmostEqual(component.get_field("weight"), 1.0)
            stack.undo()
            self.assertEqual(state.property_override_count, 0)
            self.assertEqual(child.name, "SourceChild")

            stack.redo()
            stack.redo()
            self.assertEqual(state.property_override_count, 2)

            inspector = EntityInspectorController()
            inspector.set_scene(self.scene)
            status = inspector.set_target(child).prefab_status
            self.assertIn(asset.uuid, status)
            self.assertIn("2 property", status)
            self.assertIn("valid", status)

            restored_scene = TcScene.create("editor-command-prefab-restored")
            try:
                self.assertGreater(restored_scene.load_from_data(self.scene.serialize()), 0)
                restored_instance = restored_scene.get_entity(instance.uuid)
                restored_state = restored_instance.get_component(PrefabInstanceState)
                self.assertEqual(restored_state.property_override_count, 2)
                self.assertTrue(asset.apply_to_instance(restored_instance).ok)
                restored_child = restored_state.entity_for_source(child_source_id)
                self.assertEqual(restored_child.name, "Customized")
            finally:
                restored_scene.destroy()
        finally:
            source_scene.destroy()

    def test_prefab_delete_undo_rebinds_mapping_and_refreshes(self) -> None:
        source_scene, asset, instance, (child_source_id, _component_source_id) = (
            self._create_prefab_instance())
        try:
            state = instance.get_component(PrefabInstanceState)
            child = state.entity_for_source(child_source_id)
            child_uuid = child.uuid
            stack = UndoStack()

            stack.push(DeleteEntityCommand(self.scene, child))
            self.assertFalse(state.entity_for_source(child_source_id).valid())
            self.assertIsNotNone(state.get_structural_override(
                PrefabStructuralOverrideKind.SUPPRESS_ENTITY, child_source_id))
            self.assertTrue(asset.apply_to_instance(instance).ok)
            self.assertIsNone(self.scene.get_entity(child_uuid))

            stack.undo()
            restored = state.entity_for_source(child_source_id)
            self.assertTrue(restored.valid())
            self.assertEqual(restored.uuid, child_uuid)
            self.assertIsNone(state.get_structural_override(
                PrefabStructuralOverrideKind.SUPPRESS_ENTITY, child_source_id))
            self.assertTrue(asset.apply_to_instance(instance).ok)
            self.assertEqual(state.entity_for_source(child_source_id), restored)
        finally:
            source_scene.destroy()

    def test_prefab_reparent_to_local_entity_records_placement_with_undo(self) -> None:
        source_scene, asset, instance, (child_source_id, _component_source_id) = (
            self._create_prefab_instance())
        try:
            state = instance.get_component(PrefabInstanceState)
            child = state.entity_for_source(child_source_id)
            local_parent = instance.create_child("LocalParent")
            stack = UndoStack()

            stack.push(ReparentEntityCommand(
                child,
                instance.transform,
                local_parent.transform,
            ))
            self.assertEqual(child.parent, local_parent)
            self.assertIsNotNone(state.get_structural_override(
                PrefabStructuralOverrideKind.PLACE_ENTITY, child_source_id))
            self.assertTrue(asset.apply_to_instance(instance).ok)
            self.assertEqual(child.parent, local_parent)

            stack.undo()
            self.assertEqual(child.parent, instance)
            self.assertIsNone(state.get_structural_override(
                PrefabStructuralOverrideKind.PLACE_ENTITY, child_source_id))
            self.assertTrue(asset.apply_to_instance(instance).ok)
            self.assertEqual(child.parent, instance)
        finally:
            source_scene.destroy()

    def test_prefab_component_remove_undo_rebinds_mapping_after_refresh(self) -> None:
        source_scene, asset, instance, (child_source_id, component_source_id) = (
            self._create_prefab_instance())
        try:
            state = instance.get_component(PrefabInstanceState)
            child = state.entity_for_source(child_source_id)
            stack = UndoStack()

            stack.push(RemoveComponentCommand(child, "EditorPrefabProbe"))
            self.assertIsNone(child.get_tc_component("EditorPrefabProbe"))
            self.assertIsNotNone(state.get_structural_override(
                PrefabStructuralOverrideKind.SUPPRESS_COMPONENT, component_source_id))
            self.assertTrue(asset.apply_to_instance(instance).ok)

            stack.undo()
            restored = child.get_tc_component("EditorPrefabProbe")
            self.assertIsNotNone(restored)
            self.assertEqual(restored.source_id, component_source_id)
            self.assertEqual(
                state.source_for_component(child, restored.source_id),
                component_source_id,
            )
            self.assertIsNone(state.get_structural_override(
                PrefabStructuralOverrideKind.SUPPRESS_COMPONENT, component_source_id))
            self.assertTrue(asset.apply_to_instance(instance).ok)
        finally:
            source_scene.destroy()

    def test_entity_property_command_edits_visibility(self) -> None:
        entity = self.scene.create_entity("entity")
        stack = UndoStack()

        stack.push(EntityPropertyEditCommand(entity, "visible", True, False))
        self.assertFalse(entity.visible)

        stack.undo()
        self.assertTrue(entity.visible)

    def test_recursive_layer_command_restores_descendant_layers(self) -> None:
        root = self.scene.create_entity("root")
        child = self.scene.create_entity("child")
        grandchild = self.scene.create_entity("grandchild")
        child.transform.set_parent(root.transform)
        grandchild.transform.set_parent(child.transform)
        child.layer = 2
        grandchild.layer = 4

        stack = UndoStack()
        stack.push(RecursiveLayerChangeCommand([(child, 2), (grandchild, 4)], 7))

        self.assertEqual(child.layer, 7)
        self.assertEqual(grandchild.layer, 7)

        stack.undo()
        self.assertEqual(child.layer, 2)
        self.assertEqual(grandchild.layer, 4)

    def test_scene_property_command_edits_render_state(self) -> None:
        rs = scene_render_state(self.scene)
        old_color = rs.background_color.copy()
        new_color = np.array([0.2, 0.3, 0.4, 1.0], dtype=np.float32)

        stack = UndoStack()
        stack.push(ScenePropertyEditCommand(self.scene, "background_color", old_color, new_color))

        np.testing.assert_allclose(rs.background_color, new_color)

        stack.undo()
        np.testing.assert_allclose(rs.background_color, old_color)

    def test_scene_property_command_merges_same_property(self) -> None:
        rs = scene_render_state(self.scene)
        old_value = rs.ambient_intensity

        stack = UndoStack()
        stack.push(ScenePropertyEditCommand(self.scene, "ambient_intensity", old_value, 0.5))
        stack.push(ScenePropertyEditCommand(self.scene, "ambient_intensity", 0.5, 0.75), merge=True)

        self.assertEqual(len(stack), 1)
        self.assertAlmostEqual(rs.ambient_intensity, 0.75)

        stack.undo()
        self.assertAlmostEqual(rs.ambient_intensity, old_value)

    def test_skybox_type_command_edits_render_state(self) -> None:
        rs = scene_render_state(self.scene)
        old_type = rs.skybox_type
        new_type = "solid" if old_type != "solid" else "gradient"

        stack = UndoStack()
        stack.push(SkyboxTypeEditCommand(self.scene, old_type, new_type))

        self.assertEqual(rs.skybox_type, new_type)

        stack.undo()
        self.assertEqual(rs.skybox_type, old_type)


if __name__ == "__main__":
    unittest.main()
