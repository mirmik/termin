import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QWidget,
    QVBoxLayout, QSplitter, QLabel, QFileSystemModel
)
from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex

from termin.visualization.scene import Scene
from termin.visualization.entity import Entity
from termin.kinematic.transform import Transform3


# ==========================================================
#   Tree Model for Scene Entity / Transform hierarchy
# ==========================================================

class NodeWrapper:
    """Обёртка: либо Transform, либо Entity."""
    def __init__(self, obj, parent=None):
        self.obj = obj
        self.parent = parent
        self.children = []

    @property
    def name(self):
        if isinstance(self.obj, Entity):
            return f"Entity: {self.obj.name}"
        if isinstance(self.obj, Transform3):
            return f"Transform: {self.obj.name}"
        return str(self.obj)


class SceneTreeModel(QAbstractItemModel):
    def __init__(self, scene: Scene):
        super().__init__()
        self.scene = scene
        self.root = NodeWrapper("SceneRoot")
        self._build_hierarchy()

    # ------------------------------------------------------
    # Build Tree from scene
    # ------------------------------------------------------
    def _build_hierarchy(self):
        for ent in self.scene.entities:
            self._add_entity_recursive(ent, self.root)

    def _add_entity_recursive(self, ent: Entity, parent_node: NodeWrapper):
        ent_node = NodeWrapper(ent, parent_node)
        parent_node.children.append(ent_node)

        trans = ent.transform
        self._add_transform_recursive(trans, ent_node)

    def _add_transform_recursive(self, trans: Transform3, parent_node: NodeWrapper):
        tnode = NodeWrapper(trans, parent_node)
        parent_node.children.append(tnode)

        for child_trans in trans.children:
            self._add_transform_recursive(child_trans, tnode)

    # ------------------------------------------------------
    # QAbstractItemModel required methods
    # ------------------------------------------------------
    def index(self, row, column, parent):
        if not parent.isValid():
            parent_node = self.root
        else:
            parent_node = parent.internalPointer()

        if row < 0 or row >= len(parent_node.children):
            return QModelIndex()

        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        node = index.internalPointer()
        if node.parent is None or node.parent is self.root:
            return QModelIndex()

        parent = node.parent
        grand = parent.parent
        row = grand.children.index(parent)
        return self.createIndex(row, 0, parent)

    def rowCount(self, parent):
        if not parent.isValid():
            node = self.root
        else:
            node = parent.internalPointer()
        return len(node.children)

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role == Qt.DisplayRole:
            return node.name
        return None


# ==========================================================
#       Editor Main Window
# ==========================================================

class EditorWindow(QMainWindow):
    def __init__(self, world, scene, camera):
        super().__init__()
        self.world = world
        self.scene = scene
        self.camera = camera

        self.setWindowTitle("Mini Unity Editor")
        self.resize(1300, 800)

        # ----- Splitter -----
        splitter = QSplitter(self)
        self.setCentralWidget(splitter)

        # ----- Left: Scene Tree -----
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeView()
        self.tree.setModel(SceneTreeModel(scene))
        self.tree.expandAll()

        left_layout.addWidget(self.tree)
        splitter.addWidget(left_panel)

        # ----- Center: Render View -----
        render_parent = QWidget()
        render_layout = QVBoxLayout(render_parent)
        render_layout.setContentsMargins(0, 0, 0, 0)

        # создаём окно рендера с parent=render_parent
        self.viewport_window = world.create_window(
            width=900, height=800,
            title="viewport",
            parent=render_parent
        )
        self.viewport_window.add_viewport(scene, camera)

        # ВАЖНО: QtGLWindowHandle.widget — это настоящий QWidget!
        render_layout.addWidget(self.viewport_window.handle.widget)

        splitter.addWidget(render_parent)

        # ----- Right panel: Inspector -----
        self.inspector = QLabel("Inspector", alignment=Qt.AlignTop)
        splitter.addWidget(self.inspector)

        # Немного пропорций сплиттера
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        self.tree.clicked.connect(self.on_tree_click)

    def on_tree_click(self, index):
        node = index.internalPointer()
        obj = node.obj

        if hasattr(obj, "ang"):  # Pose3 inside Transform
            self.inspector.setText(f"Transform\npos={obj.lin}\nrot={obj.ang}")
        else:
            self.inspector.setText(str(obj))


# ==========================================================
#               RUNNING THE EDITOR
# ==========================================================

def run_editor(world, scene, camera):
    app = QApplication(sys.argv)
    win = EditorWindow(world, scene, camera)
    win.resize(800, 600)
    win.show()
    sys.exit(app.exec_())

from termin.mesh.mesh import CubeMesh
from termin.visualization.entity import Entity
from termin.visualization.components import MeshRenderer
from termin.visualization.world import VisualizationWorld
from termin.visualization.mesh import MeshDrawable
from termin.visualization.material import Material
import numpy as np
from termin.geombase.pose3 import Pose3
from termin.visualization.skybox import SkyBoxEntity
from termin.visualization.camera import PerspectiveCameraComponent, OrbitCameraController

def build_scene(world):

    cube_mesh = CubeMesh()
    drawable = MeshDrawable(cube_mesh)
    material = Material(color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))
    entity = Entity(pose=Pose3.identity(), name="cube")
    entity.add_component(MeshRenderer(drawable, material))
    scene = Scene()
    scene.add(entity)

    skybox = SkyBoxEntity()
    scene.add(skybox)
    world.add_scene(scene)

    camera_entity = Entity(name="camera")
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera

from termin.visualization.backends import QtWindowBackend, OpenGLGraphicsBackend, set_default_graphics_backend, set_default_window_backend

# Example usage:
if __name__ == "__main__":
    set_default_graphics_backend(OpenGLGraphicsBackend())
    set_default_window_backend(QtWindowBackend())

    from termin.visualization.world import VisualizationWorld

    world = VisualizationWorld()
    scene, cam = build_scene(world)

    # Launch Qt editor with this scene
    run_editor(world, scene, cam)