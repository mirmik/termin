import unittest

from termin.bootstrap import bootstrap_player, shutdown_player
from termin.editor_core.python_executor import EditorPythonExecutor
from termin.editor_core.scene_edit_service import EditorSceneEditService
from termin.editor_core.undo_stack import UndoStack
from termin.geombase import Quat, Vec3
from termin.scene import TcScene


class TestEditorSceneEditService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bootstrap_player()

    @classmethod
    def tearDownClass(cls) -> None:
        shutdown_player()

    def setUp(self) -> None:
        self.scene = TcScene.create("editor-scene-edit-service-test")
        self.entity = self.scene.create_entity("entity")
        self.selected_entity = self.entity
        self.undo_stack = UndoStack()
        self.render_updates = 0
        self.service = EditorSceneEditService(
            get_selected_entity=lambda: self.selected_entity,
            push_undo_command=lambda command, merge: self.undo_stack.push(
                command, merge=merge
            ),
            request_viewport_update=self._request_viewport_update,
        )

    def tearDown(self) -> None:
        self.scene.destroy()

    def _request_viewport_update(self) -> None:
        self.render_updates += 1

    def test_selected_local_transform_round_trips_through_undo_and_redo(self) -> None:
        result = self.service.set_selected_local_transform(
            position=(1.0, 2.0, 3.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            scale=Vec3(2.0, 3.0, 4.0),
        )

        self.assertTrue(result["changed"])
        self.assertTrue(result["local_space"])
        self.assertEqual(result["entity_uuid"], self.entity.uuid)
        self.assertEqual(result["position"], (1.0, 2.0, 3.0))
        self.assertEqual(result["scale"], (2.0, 3.0, 4.0))
        self.assertEqual(self.render_updates, 1)
        self.assertEqual(len(self.undo_stack), 1)

        self.undo_stack.undo()
        self.assertEqual(tuple(self.entity.transform.local_pose().lin), (0.0, 0.0, 0.0))
        self.undo_stack.redo()
        self.assertEqual(tuple(self.entity.transform.local_pose().lin), (1.0, 2.0, 3.0))

    def test_repeated_merged_edits_share_one_undo_entry(self) -> None:
        self.service.set_selected_local_transform(position=(1.0, 0.0, 0.0), merge=True)
        self.service.set_selected_local_transform(position=(2.0, 0.0, 0.0), merge=True)

        self.assertEqual(len(self.undo_stack), 1)
        self.assertEqual(tuple(self.entity.transform.local_pose().lin), (2.0, 0.0, 0.0))
        self.undo_stack.undo()
        self.assertEqual(tuple(self.entity.transform.local_pose().lin), (0.0, 0.0, 0.0))

    def test_explicit_entity_preserves_omitted_local_values(self) -> None:
        initial_pose = self.entity.transform.local_pose()
        self.service.set_entity_local_transform(
            self.entity,
            rotation=Quat(0.0, 0.0, 1.0, 0.0),
        )

        pose = self.entity.transform.local_pose()
        self.assertEqual(tuple(pose.lin), tuple(initial_pose.lin))
        self.assertEqual(tuple(pose.scale), tuple(initial_pose.scale))
        self.assertEqual((pose.ang.x, pose.ang.y, pose.ang.z, pose.ang.w), (0.0, 0.0, 1.0, 0.0))

    def test_service_reports_missing_selection_and_invalid_values(self) -> None:
        self.selected_entity = None
        with self.assertRaisesRegex(RuntimeError, "selected entity is unavailable"):
            self.service.set_selected_local_transform(position=(1.0, 2.0, 3.0))

        self.selected_entity = self.entity
        with self.assertRaisesRegex(RuntimeError, "position must be Vec3"):
            self.service.set_selected_local_transform(position=(1.0, 2.0))
        with self.assertRaisesRegex(RuntimeError, "zero quaternion"):
            self.service.set_selected_local_transform(rotation=(0.0, 0.0, 0.0, 0.0))

    def test_executor_exposes_public_scene_edit_service(self) -> None:
        executor = EditorPythonExecutor(lambda: {"scene_edit": self.service})

        result = executor.execute_script(
            "state = scene_edit.set_selected_local_transform(position=(4, 5, 6))\n"
            "print(state['position'])"
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.output, "(4.0, 5.0, 6.0)\n")
        self.assertEqual(len(self.undo_stack), 1)
        self.assertEqual(self.render_updates, 1)
