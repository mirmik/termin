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
from tcbase import log


class NodeWrapper:
    """
    Узел дерева. Держит только Entity
    (root держит obj=None).
    """
    def __init__(self, obj: Entity | None, parent=None):
        self.obj = obj
        self.parent = parent
        self.children: list[NodeWrapper] = []

    def is_valid_entity(self) -> bool:
        """Check if this node holds a valid entity."""
        if self.obj is None:
            return False
        if not isinstance(self.obj, Entity):
            return False
        try:
            return self.obj.valid()
        except Exception:
            return False

    @property
    def name(self) -> str:
        if self.obj is None:
            return "Scene"
        if not isinstance(self.obj, Entity):
            return "<unknown>"
        try:
            if not self.obj.valid():
                return "<invalid>"
            return self.obj.name
        except Exception as e:
            log.error(f"[NodeWrapper.name] Exception: {e}")
            return "<error>"


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

    def __init__(self, scene: Scene | None = None):
        super().__init__()
        self.scene: Scene | None = scene
        self.root = NodeWrapper(None)

        # карта Entity -> NodeWrapper, для быстрого поиска индекса
        self._obj_to_node: dict[Entity, NodeWrapper] = {}

        if scene is not None and self._is_scene_valid(scene):
            self._build_hierarchy()

    # ------------------------------------------------------
    # Safety helpers
    # ------------------------------------------------------

    def _is_scene_valid(self, scene: Scene | None) -> bool:
        """Check if scene is valid and alive."""
        if scene is None:
            return False
        try:
            return scene.is_alive()
        except Exception:
            return False

    def _get_node_from_index(self, index: QModelIndex) -> NodeWrapper | None:
        """Safely get NodeWrapper from QModelIndex."""
        if not index.isValid():
            return self.root
        try:
            ptr = index.internalPointer()
            if ptr is None:
                return None
            if not isinstance(ptr, NodeWrapper):
                return None
            return ptr
        except Exception:
            return None

    # ------------------------------------------------------
    # Build Tree from scene
    # ------------------------------------------------------

    def _build_hierarchy(self):
        # чистим на случай пересборки
        self.root.children.clear()
        self._obj_to_node.clear()

        if not self._is_scene_valid(self.scene):
            return

        # Сначала создаём узлы для всех сущностей
        try:
            entities = self.scene.entities
        except Exception as e:
            log.error(f"[_build_hierarchy] Failed to get entities: {e}")
            return

        for ent in entities:
            try:
                if not isinstance(ent, Entity):
                    continue
                if not ent.valid():
                    continue
                self._get_or_create_node(ent)
            except Exception as e:
                log.error(f"[_build_hierarchy] Error creating node: {e}")

        # Теперь связываем родителей и детей
        for ent in entities:
            try:
                if not isinstance(ent, Entity):
                    continue
                if not ent.valid():
                    continue
                node = self._obj_to_node.get(ent)
                if node is None:
                    continue

                transform = ent.transform
                if transform is None or not transform.valid():
                    node.parent = self.root
                    self.root.children.append(node)
                    continue

                parent_tf = transform.parent
                parent_ent = parent_tf.entity if parent_tf is not None else None

                # если трансформ родителя не привязан к Entity – считаем, что это корень
                if isinstance(parent_ent, Entity) and parent_ent.valid() and parent_ent in self._obj_to_node:
                    parent_node = self._obj_to_node[parent_ent]
                else:
                    parent_node = self.root

                node.parent = parent_node
                parent_node.children.append(node)
            except Exception as e:
                log.error(f"[_build_hierarchy] Error linking node: {e}")

    def _get_or_create_node(self, ent: Entity) -> NodeWrapper:
        node = self._obj_to_node.get(ent)
        if node is None:
            node = NodeWrapper(ent, parent=None)
            self._obj_to_node[ent] = node
        return node

    def clear_refs(self) -> None:
        """Clear all entity references to prevent access to destroyed objects."""
        self.beginResetModel()
        self._clear_node_refs(self.root)
        self.root.children.clear()
        self._obj_to_node.clear()
        self.scene = None
        self.endResetModel()

    def _clear_node_refs(self, node: NodeWrapper) -> None:
        """Recursively clear entity references in nodes."""
        for child in node.children:
            self._clear_node_refs(child)
        node.obj = None
        node.parent = None
        node.children.clear()

    def rebuild_for_scene(self, scene: Scene | None) -> None:
        """
        Rebuild model for a new scene, reusing the same model instance.
        Properly notifies Qt about structure changes.
        """
        self.beginResetModel()

        # Clear old references (children first, then parents)
        self._clear_node_refs(self.root)
        self.root.children.clear()
        self._obj_to_node.clear()

        # Set new scene and rebuild
        self.scene = scene
        if self._is_scene_valid(scene):
            self._build_hierarchy()

        self.endResetModel()

    # ==============================================================
    # Qt model interface
    # ==============================================================

    def index(self, row, column, parent):
        parent_node = self._get_node_from_index(parent)
        if parent_node is None:
            return QModelIndex()
        if row < 0 or row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index):
        node = self._get_node_from_index(index)
        if node is None or node is self.root:
            return QModelIndex()

        parent = node.parent
        if parent is None or parent is self.root:
            return QModelIndex()

        grand = parent.parent or self.root
        try:
            row = grand.children.index(parent)
        except ValueError:
            return QModelIndex()
        return self.createIndex(row, 0, parent)

    def rowCount(self, parent):
        node = self._get_node_from_index(parent)
        if node is None:
            return 0
        return len(node.children)

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        node = self._get_node_from_index(index)
        if node is None:
            return None

        try:
            if role == Qt.ItemDataRole.DisplayRole:
                return node.name

            if role == Qt.ItemDataRole.ForegroundRole:
                if not node.is_valid_entity():
                    return None
                ent = node.obj
                if ent.has_component_type("PrefabInstanceMarker"):
                    return QColor(70, 130, 220)  # Steel blue
                if not ent.enabled:
                    return QColor(128, 128, 128)

            if role == Qt.ItemDataRole.CheckStateRole:
                if not node.is_valid_entity():
                    return None
                return Qt.CheckState.Checked if node.obj.enabled else Qt.CheckState.Unchecked

        except Exception as e:
            log.error(f"[SceneTreeModel.data] Exception: {e}")
            return None

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        node = self._get_node_from_index(index)
        if node is None:
            return False

        if role == Qt.ItemDataRole.CheckStateRole:
            if not node.is_valid_entity():
                return False
            try:
                # PyQt6: value can be int or Qt.CheckState
                if isinstance(value, int):
                    enabled = (value == Qt.CheckState.Checked.value)
                else:
                    enabled = (value == Qt.CheckState.Checked)
                node.obj.enabled = enabled
                self.dataChanged.emit(index, index, [role, Qt.ItemDataRole.ForegroundRole])
                self.entity_enabled_changed.emit(node.obj, enabled)
                return True
            except Exception as e:
                log.error(f"[SceneTreeModel.setData] Exception: {e}")
                return False

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
            try:
                row = parent_node.children.index(n)
            except ValueError:
                return QModelIndex()
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
        if not isinstance(entity, Entity) or not entity.valid():
            return QModelIndex()

        index = self.add_entity(entity)

        # Recursively add children
        try:
            for child_tf in entity.transform.children:
                child_ent = child_tf.entity
                if child_ent is not None and child_ent.valid():
                    self.add_entity_hierarchy(child_ent)
        except Exception as e:
            log.error(f"[add_entity_hierarchy] Exception: {e}")

        return index

    def add_entity(self, entity: Entity) -> QModelIndex:
        """
        Add a new entity to the tree (without children).
        Returns the QModelIndex of the new node.
        """
        if not isinstance(entity, Entity) or not entity.valid():
            return QModelIndex()

        if entity in self._obj_to_node:
            # Already exists
            return self.index_for_object(entity)

        try:
            # Find parent node
            parent_tf = entity.transform.parent
            parent_ent = parent_tf.entity if parent_tf is not None else None

            if isinstance(parent_ent, Entity) and parent_ent.valid() and parent_ent in self._obj_to_node:
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
        except Exception as e:
            log.error(f"[add_entity] Exception: {e}")
            return QModelIndex()

    def remove_entity(self, entity: Entity) -> bool:
        """
        Remove an entity from the tree.
        Returns True if removed successfully.
        """
        if not isinstance(entity, Entity):
            return False

        node = self._obj_to_node.get(entity)
        if node is None:
            return False

        parent_node = node.parent
        if parent_node is None:
            return False

        try:
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
        except Exception as e:
            log.error(f"[remove_entity] Exception: {e}")
            return False

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
        if not isinstance(entity, Entity) or not entity.valid():
            return False

        node = self._obj_to_node.get(entity)
        if node is None:
            return False

        old_parent_node = node.parent
        if old_parent_node is None:
            return False

        try:
            # Determine new parent node
            if new_parent is not None and isinstance(new_parent, Entity) and new_parent.valid() and new_parent in self._obj_to_node:
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
        except Exception as e:
            log.error(f"[move_entity] Exception: {e}")
            return False

    def update_entity(self, entity: Entity) -> None:
        """
        Notify that an entity's data has changed (e.g., name).
        """
        if not isinstance(entity, Entity):
            return
        index = self.index_for_object(entity)
        if index.isValid():
            self.dataChanged.emit(index, index)

    # ==============================================================
    # Drag-drop support
    # ==============================================================

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags including drag-drop capability and checkbox."""
        default_flags = super().flags(index)

        node = self._get_node_from_index(index)
        if node is None:
            return default_flags

        if node is self.root:
            # Root can accept drops (to move to top level)
            return default_flags | Qt.ItemFlag.ItemIsDropEnabled

        if node.is_valid_entity():
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
        if not indexes:
            return None

        # Take the first valid entity
        for index in indexes:
            node = self._get_node_from_index(index)
            if node is not None and node.is_valid_entity():
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

        if not self._is_scene_valid(self.scene):
            return False

        # Parse the dragged entity data
        entity_data = parse_entity_mime_data(data)
        if entity_data is None:
            return False

        entity_uuid = entity_data.get("entity_uuid")
        if entity_uuid is None:
            return False

        # Find the dragged entity by UUID
        try:
            dragged_entity = self.scene.get_entity(entity_uuid)
        except Exception:
            return False
        if dragged_entity is None or not dragged_entity.valid():
            return False

        # Get target entity (parent of drop location)
        target_entity = None
        target_node = self._get_node_from_index(parent)
        if target_node is not None and target_node.is_valid_entity():
            target_entity = target_node.obj

        # Can't drop on self
        if target_entity is dragged_entity:
            return False

        # Can't drop on a descendant
        if target_entity is not None:
            try:
                check = target_entity.transform.parent
                while check is not None:
                    check_entity = check.entity
                    if check_entity is not None and check_entity.valid() and check_entity is dragged_entity:
                        return False
                    check = check.parent
            except Exception:
                return False

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
        target_node = self._get_node_from_index(parent)
        if target_node is not None and target_node.is_valid_entity():
            target_entity = target_node.obj

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

        if not self._is_scene_valid(self.scene):
            return False

        # Handle entity reparent
        entity_data = parse_entity_mime_data(data)
        if entity_data is None:
            return False

        entity_uuid = entity_data.get("entity_uuid")
        if entity_uuid is None:
            return False

        # Find the dragged entity by UUID
        try:
            dragged_entity = self.scene.get_entity(entity_uuid)
        except Exception:
            return False
        if dragged_entity is None or not dragged_entity.valid():
            return False

        # Emit signal for controller to handle with undo support
        self.entity_reparent_requested.emit(dragged_entity, target_entity)

        return True
