from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex

from termin.visualization.scene import Scene
from termin.visualization.entity import Entity
from termin.kinematic.transform import Transform3


class NodeWrapper:
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

    def _build_hierarchy(self):
        for ent in self.scene.entities:
            self._add_entity_recursive(ent, self.root)

    def _add_entity_recursive(self, ent: Entity, parent_node: NodeWrapper):
        ent_node = NodeWrapper(ent, parent_node)
        parent_node.children.append(ent_node)
        self._add_transform_recursive(ent.transform, ent_node)

    def _add_transform_recursive(self, trans: Transform3, parent_node: NodeWrapper):
        tnode = NodeWrapper(trans, parent_node)
        parent_node.children.append(tnode)

        for child in trans.children:
            self._add_transform_recursive(child, tnode)

    # ==============================================================
    # Qt model interface
    # ==============================================================

    def index(self, row, column, parent):
        parent_node = self.root if not parent.isValid() else parent.internalPointer()
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
        node = self.root if not parent.isValid() else parent.internalPointer()
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
