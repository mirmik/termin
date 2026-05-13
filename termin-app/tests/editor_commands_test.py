import unittest

import numpy as np

from termin.editor_core.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    EntityPropertyEditCommand,
    RenameEntityCommand,
    ReparentEntityCommand,
    RecursiveLayerChangeCommand,
    ScenePropertyEditCommand,
    SkyboxTypeEditCommand,
    TransformEditCommand,
)
from termin.editor_core.undo_stack import UndoStack
from termin.geombase import GeneralPose3
from termin.scene import TcScene
from termin.visualization.core.scene import scene_render_state


class TestEditorUndoCommands(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = TcScene.create("editor-command-test")

    def tearDown(self) -> None:
        self.scene.destroy()

    def test_transform_command_survives_delete_restore(self) -> None:
        entity = self.scene.create_entity("entity")
        uuid = entity.uuid
        old_pose = entity.transform.local_pose()
        new_pose = GeneralPose3(
            lin=np.array([1.0, 2.0, 3.0]),
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
