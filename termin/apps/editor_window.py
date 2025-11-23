import os
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt

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

        self.topSplitter = self.findChild(type(self.topSplitter), "topSplitter")
        self.verticalSplitter = self.findChild(type(self.verticalSplitter), "verticalSplitter")

        # --- Fix splitter behaviour ---
        self._fix_splitters()

        # --- Scene tree ---
        self.sceneTree.setModel(SceneTreeModel(scene))
        self.sceneTree.expandAll()
        self.sceneTree.clicked.connect(self.on_tree_click)

        # --- Render viewport ---
        self._init_viewport()

    # ----------------------------------------------------
    def _fix_splitters(self):
        # сглаживание resize
        self.topSplitter.setOpaqueResize(False)
        self.verticalSplitter.setOpaqueResize(False)

        # запрет схлопывания
        self.topSplitter.setCollapsible(0, False)
        self.topSplitter.setCollapsible(1, False)
        self.topSplitter.setCollapsible(2, False)

        self.verticalSplitter.setCollapsible(0, False)
        self.verticalSplitter.setCollapsible(1, False)

        # стартовые размеры
        self.topSplitter.setSizes([300, 1000, 300])
        self.verticalSplitter.setSizes([600, 200])

    # ----------------------------------------------------
    def _init_viewport(self):
        layout = self.viewportContainer.layout()

        self.viewport_window = self.world.create_window(
            width=900,
            height=800,
            title="viewport",
            parent=self.viewportContainer
        )

        self.viewport_window.add_viewport(self.scene, self.camera)

        gl_widget = self.viewport_window.handle.widget
        gl_widget.setFocusPolicy(Qt.StrongFocus)
        gl_widget.setMinimumSize(50, 50)

        layout.addWidget(gl_widget)

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
