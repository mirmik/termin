import unittest

import numpy as np

from termin.editor.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    RenameEntityCommand,
    ReparentEntityCommand,
    TransformEditCommand,
)
from termin.editor.undo_stack import UndoStack
from termin.geombase import GeneralPose3
from termin.scene import TcScene


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


if __name__ == "__main__":
    unittest.main()
