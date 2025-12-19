# ===== termin/editor/editor_tree.py =====
from PyQt6.QtCore import Qt, QAbstractItemModel, QModelIndex, pyqtSignal
from PyQt6.QtGui import QColor

from termin.visualization.core.scene import Scene
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.editor.drag_drop import (
    EditorMimeTypes,
    create_entity_mime_data,
    parse_entity_mime_data,
    parse_asset_path_mime_data,
)


class NodeWrapper:
    """
    Узел дерева. Держит только Entity
    (root держит obj=None).
    """
    def __init__(self, obj: Entity | None, parent=None):
        self.obj = obj
        self.parent = parent
        self.children: list[NodeWrapper] = []

    @property
    def name(self) -> str:
        if isinstance(self.obj, Entity):
            return f"Entity: {self.obj.name}"
        return "Scene"


class SceneTreeModel(QAbstractItemModel):
    """
    Дерево: иерархия Entity, повторяющая иерархию Transform3.
    Transform-узлы в дереве НЕ показываем.
    """

    # Signal emitted when entity should be reparented via drag-drop
    # Args: (entity_to_move: Entity, new_parent_entity: Entity | None)
    entity_reparent_requested = pyqtSignal(Entity, object)

    # Signal emitted when prefab should be instantiated via drag-drop
    # Args: (prefab_path: str, parent_entity: Entity | None)
    prefab_drop_requested = pyqtSignal(str, object)

    # Signal emitted when FBX should be instantiated via drag-drop
    # Args: (fbx_path: str, parent_entity: Entity | None)
    fbx_drop_requested = pyqtSignal(str, object)

    # Signal emitted when GLB should be instantiated via drag-drop
    # Args: (glb_path: str, parent_entity: Entity | None)
    glb_drop_requested = pyqtSignal(str, object)

    def __init__(self, scene: Scene):
        super().__init__()
        self.scene = scene
        self.root = NodeWrapper(None)

        # карта Entity -> NodeWrapper, для быстрого поиска индекса
        self._obj_to_node: dict[Entity, NodeWrapper] = {}

        self._build_hierarchy()

    # ------------------------------------------------------
    # Build Tree from scene
    # ------------------------------------------------------
    def _build_hierarchy(self):
        # чистим на случай пересборки
        self.root.children.clear()
        self._obj_to_node.clear()

        # Сначала создаём узлы для всех сущностей
        for ent in self.scene.entities:
            self._get_or_create_node(ent)

        # Теперь связываем родителей и детей
        for ent in self.scene.entities:
            node = self._obj_to_node[ent]

            parent_tf = ent.transform.parent
            parent_ent = parent_tf.entity if parent_tf is not None else None

            # если трансформ родителя не привязан к Entity – считаем, что это корень
            if isinstance(parent_ent, Entity) and parent_ent in self._obj_to_node:
                parent_node = self._obj_to_node[parent_ent]
            else:
                parent_node = self.root

            node.parent = parent_node
            parent_node.children.append(node)

    def _get_or_create_node(self, ent: Entity) -> NodeWrapper:
        node = self._obj_to_node.get(ent)
        if node is None:
            node = NodeWrapper(ent, parent=None)
            self._obj_to_node[ent] = node
        return node

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

        node: NodeWrapper = index.internalPointer()
        parent = node.parent
        if parent is None or parent is self.root:
            return QModelIndex()

        grand = parent.parent or self.root
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
        node: NodeWrapper = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            return node.name
        if role == Qt.ItemDataRole.ForegroundRole:
            # Blue color for prefab instances
            if isinstance(node.obj, Entity):
                from termin.visualization.core.prefab_instance_marker import PrefabInstanceMarker
                if node.obj.get_component(PrefabInstanceMarker) is not None:
                    return QColor(70, 130, 220)  # Steel blue
        return None

    # ==============================================================
    #   Поиск индекса по объекту сцены
    # ==============================================================

    def index_for_object(self, obj) -> QModelIndex:
        """
        Возвращает QModelIndex для данного Entity, если он есть в дереве.
        Transform3 здесь не учитываем, дерево чисто по сущностям.
        """
        if not isinstance(obj, Entity):
            # если вдруг прилетел Transform3 – попробуем найти его владельца
            if isinstance(obj, Transform3) and obj.entity is not None:
                obj = obj.entity
            else:
                return QModelIndex()

        node = self._obj_to_node.get(obj)
        if node is None:
            return QModelIndex()

        # строим путь от этого узла до root
        path_nodes = []
        cur = node
        while cur is not None and cur is not self.root:
            path_nodes.append(cur)
            cur = cur.parent

        path_nodes.reverse()

        parent_index = QModelIndex()
        parent_node = self.root

        for n in path_nodes:
            row = parent_node.children.index(n)
            idx = self.index(row, 0, parent_index)
            parent_index = idx
            parent_node = n

        return parent_index

    # ==============================================================
    # Drag-drop support
    # ==============================================================

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags including drag-drop capability."""
        default_flags = super().flags(index)

        if not index.isValid():
            # Root can accept drops (to move to top level)
            return default_flags | Qt.ItemFlag.ItemIsDropEnabled

        node: NodeWrapper = index.internalPointer()
        if isinstance(node.obj, Entity):
            # Entities can be dragged and can accept drops
            return (
                default_flags
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
            )

        return default_flags

    def supportedDropActions(self) -> Qt.DropAction:
        """Support move action for reparenting and copy for prefab instantiation."""
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def mimeTypes(self) -> list[str]:
        """Return supported MIME types for drag-drop."""
        return [EditorMimeTypes.ENTITY, EditorMimeTypes.ASSET_PATH]

    def mimeData(self, indexes: list[QModelIndex]):
        """Create MIME data for dragged entities."""
        from PyQt6.QtCore import QMimeData

        if not indexes:
            return None

        # Take the first valid entity
        for index in indexes:
            if not index.isValid():
                continue
            node: NodeWrapper = index.internalPointer()
            if isinstance(node.obj, Entity):
                return create_entity_mime_data(node.obj)

        return None

    def canDropMimeData(
        self,
        data,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        """Check if drop is allowed at this location."""
        # Handle prefab/fbx asset drop (CopyAction)
        if data.hasFormat(EditorMimeTypes.ASSET_PATH):
            path = parse_asset_path_mime_data(data)
            if path:
                lower_path = path.lower()
                if lower_path.endswith(".prefab") or lower_path.endswith(".fbx") or lower_path.endswith(".glb"):
                    return True
            return False

        # Handle entity reparent (MoveAction)
        if action != Qt.DropAction.MoveAction:
            return False

        if not data.hasFormat(EditorMimeTypes.ENTITY):
            return False

        # Parse the dragged entity data
        entity_data = parse_entity_mime_data(data)
        if entity_data is None:
            return False

        entity_name = entity_data.get("entity_name")
        if entity_name is None:
            return False

        # Find the dragged entity
        dragged_entity = None
        for ent in self.scene.entities:
            if ent.name == entity_name:
                dragged_entity = ent
                break

        if dragged_entity is None:
            return False

        # Get target entity (parent of drop location)
        target_entity = None
        if parent.isValid():
            node: NodeWrapper = parent.internalPointer()
            target_entity = node.obj if isinstance(node.obj, Entity) else None

        # Can't drop on self
        if target_entity is dragged_entity:
            return False

        # Can't drop on a descendant
        if target_entity is not None:
            check = target_entity.transform.parent
            while check is not None:
                if check.entity is dragged_entity:
                    return False
                check = check.parent

        return True

    def dropMimeData(
        self,
        data,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        """Handle drop - emit signal for controller to handle reparenting or prefab instantiation."""
        if not self.canDropMimeData(data, action, row, column, parent):
            return False

        # Get target entity (common for both cases)
        target_entity = None
        if parent.isValid():
            node: NodeWrapper = parent.internalPointer()
            target_entity = node.obj if isinstance(node.obj, Entity) else None

        # Handle prefab/fbx asset drop
        if data.hasFormat(EditorMimeTypes.ASSET_PATH):
            path = parse_asset_path_mime_data(data)
            if path:
                lower_path = path.lower()
                if lower_path.endswith(".prefab"):
                    self.prefab_drop_requested.emit(path, target_entity)
                    return True
                if lower_path.endswith(".fbx"):
                    self.fbx_drop_requested.emit(path, target_entity)
                    return True
                if lower_path.endswith(".glb"):
                    self.glb_drop_requested.emit(path, target_entity)
                    return True
            return False

        # Handle entity reparent
        entity_data = parse_entity_mime_data(data)
        if entity_data is None:
            return False

        entity_name = entity_data.get("entity_name")

        # Find the dragged entity
        dragged_entity = None
        for ent in self.scene.entities:
            if ent.name == entity_name:
                dragged_entity = ent
                break

        if dragged_entity is None:
            return False

        # Emit signal for controller to handle with undo support
        self.entity_reparent_requested.emit(dragged_entity, target_entity)

        return True
