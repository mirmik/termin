import os
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow

from termin.visualization.entity import Entity
from termin.kinematic.transform import Transform3

from editor_tree import SceneTreeModel


class EditorWindow(QMainWindow):
    def __init__(self, world, scene, camera):
        super().__init__()

        ui_path = os.path.join(os.path.dirname(__file__), "editor.ui")
        uic.loadUi(ui_path, self)

        self.world = world
        self.scene = scene
        self.camera = camera

        # --- UI elements ---
        self.sceneTree = self.findChild(type(self.sceneTree), "sceneTree")
        self.viewportContainer = self.findChild(type(self.viewportContainer), "viewportContainer")
        self.inspectorLabel = self.findChild(type(self.inspectorLabel), "inspectorLabel")

        # --- Scene tree ---
        self.sceneTree.setModel(SceneTreeModel(scene))
        self.sceneTree.expandAll()
        self.sceneTree.clicked.connect(self.on_tree_click)

        # --- Render viewport ---
        layout = self.viewportContainer.layout()

        self.viewport_window = world.create_window(
            width=900,
            height=800,
            title="viewport",
            parent=self.viewportContainer
        )
        self.viewport_window.add_viewport(scene, camera)
        layout.addWidget(self.viewport_window.handle.widget)

    # ----------------------------------------------------
    # Inspector
    # ----------------------------------------------------
    def on_tree_click(self, index):
        node = index.internalPointer()
        obj = node.obj

        if isinstance(obj, Entity):
            self.inspectorLabel.setText(f"Entity: {obj.name}")
        elif isinstance(obj, Transform3):
            pose = obj.global_pose()
            self.inspectorLabel.setText(
                f"Transform\npos={pose.lin}\nrot={pose.ang}"
            )
        else:
            self.inspectorLabel.setText(str(obj))
