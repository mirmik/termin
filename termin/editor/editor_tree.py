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

    # Signal emitted when entity enabled state changes via checkbox
    # Args: (entity: Entity, enabled: bool)
    entity_enabled_changed = pyqtSignal(Entity, bool)

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
                # Gray color for disabled entities
                if not node.obj.enabled:
                    return QColor(128, 128, 128)
        if role == Qt.ItemDataRole.CheckStateRole:
            if isinstance(node.obj, Entity):
                return Qt.CheckState.Checked if node.obj.enabled else Qt.CheckState.Unchecked
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        node: NodeWrapper = index.internalPointer()
        if role == Qt.ItemDataRole.CheckStateRole and isinstance(node.obj, Entity):
            enabled = (value == Qt.CheckState.Checked)
            node.obj.enabled = enabled
            self.dataChanged.emit(index, index, [role, Qt.ItemDataRole.ForegroundRole])
            self.entity_enabled_changed.emit(node.obj, enabled)
            return True
        return False

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
    # Incremental updates
    # ==============================================================

    def add_entity_hierarchy(self, entity: Entity) -> QModelIndex:
        """
        Add an entity and all its children to the tree.
        Returns the QModelIndex of the root entity.
        """
        index = self.add_entity(entity)

        # Recursively add children
        for child_tf in entity.transform.children:
            child_ent = child_tf.entity
            if child_ent is not None:
                self.add_entity_hierarchy(child_ent)

        return index

    def add_entity(self, entity: Entity) -> QModelIndex:
        """
        Add a new entity to the tree (without children).
        Returns the QModelIndex of the new node.
        """
        if entity in self._obj_to_node:
            # Already exists
            return self.index_for_object(entity)

        # Find parent node
        parent_tf = entity.transform.parent
        parent_ent = parent_tf.entity if parent_tf is not None else None

        if isinstance(parent_ent, Entity) and parent_ent in self._obj_to_node:
            parent_node = self._obj_to_node[parent_ent]
        else:
            parent_node = self.root

        parent_index = self.index_for_object(parent_ent) if parent_ent else QModelIndex()

        # Insert new node
        row = len(parent_node.children)
        self.beginInsertRows(parent_index, row, row)

        node = NodeWrapper(entity, parent=parent_node)
        self._obj_to_node[entity] = node
        parent_node.children.append(node)

        self.endInsertRows()

        return self.index_for_object(entity)

    def remove_entity(self, entity: Entity) -> bool:
        """
        Remove an entity from the tree.
        Returns True if removed successfully.
        """
        node = self._obj_to_node.get(entity)
        if node is None:
            return False

        parent_node = node.parent
        if parent_node is None:
            return False

        # Get parent index
        if parent_node is self.root:
            parent_index = QModelIndex()
        else:
            parent_index = self.index_for_object(parent_node.obj)

        row = parent_node.children.index(node)

        self.beginRemoveRows(parent_index, row, row)

        parent_node.children.remove(node)
        del self._obj_to_node[entity]

        # Also remove all descendants from the map
        self._remove_descendants_from_map(node)

        self.endRemoveRows()

        return True

    def _remove_descendants_from_map(self, node: NodeWrapper) -> None:
        """Remove all descendant entities from _obj_to_node."""
        for child in node.children:
            if child.obj is not None:
                self._obj_to_node.pop(child.obj, None)
            self._remove_descendants_from_map(child)

    def move_entity(self, entity: Entity, new_parent: Entity | None) -> bool:
        """
        Move an entity to a new parent.
        Returns True if moved successfully.
        """
        node = self._obj_to_node.get(entity)
        if node is None:
            return False

        old_parent_node = node.parent
        if old_parent_node is None:
            return False

        # Determine new parent node
        if new_parent is not None and new_parent in self._obj_to_node:
            new_parent_node = self._obj_to_node[new_parent]
        else:
            new_parent_node = self.root

        # Already at the right parent?
        if old_parent_node is new_parent_node:
            return True

        # Get indices
        if old_parent_node is self.root:
            old_parent_index = QModelIndex()
        else:
            old_parent_index = self.index_for_object(old_parent_node.obj)

        if new_parent_node is self.root:
            new_parent_index = QModelIndex()
        else:
            new_parent_index = self.index_for_object(new_parent_node.obj)

        old_row = old_parent_node.children.index(node)
        new_row = len(new_parent_node.children)

        # Use beginMoveRows for efficient move
        if not self.beginMoveRows(old_parent_index, old_row, old_row,
                                   new_parent_index, new_row):
            return False

        old_parent_node.children.remove(node)
        node.parent = new_parent_node
        new_parent_node.children.append(node)

        self.endMoveRows()

        return True

    def update_entity(self, entity: Entity) -> None:
        """
        Notify that an entity's data has changed (e.g., name).
        """
        index = self.index_for_object(entity)
        if index.isValid():
            self.dataChanged.emit(index, index)

    # ==============================================================
    # Drag-drop support
    # ==============================================================

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags including drag-drop capability and checkbox."""
        default_flags = super().flags(index)

        if not index.isValid():
            # Root can accept drops (to move to top level)
            return default_flags | Qt.ItemFlag.ItemIsDropEnabled

        node: NodeWrapper = index.internalPointer()
        if isinstance(node.obj, Entity):
            # Entities can be dragged, accept drops, and have enabled checkbox
            return (
                default_flags
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
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
