<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/apps/editor_tree.py</title>
</head>
<body>
<pre><code>
# ===== termin/apps/editor_tree.py =====
from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex

from termin.visualization.scene import Scene
from termin.visualization.entity import Entity
from termin.kinematic.transform import Transform3


class NodeWrapper:
    &quot;&quot;&quot;
    Узел дерева. Держит только Entity
    (root держит obj=None).
    &quot;&quot;&quot;
    def __init__(self, obj: Entity | None, parent=None):
        self.obj = obj
        self.parent = parent
        self.children: list[NodeWrapper] = []

    @property
    def name(self) -&gt; str:
        if isinstance(self.obj, Entity):
            return f&quot;Entity: {self.obj.name}&quot;
        return &quot;Scene&quot;


class SceneTreeModel(QAbstractItemModel):
    &quot;&quot;&quot;
    Дерево: иерархия Entity, повторяющая иерархию Transform3.
    Transform-узлы в дереве НЕ показываем.
    &quot;&quot;&quot;

    def __init__(self, scene: Scene):
        super().__init__()
        self.scene = scene
        self.root = NodeWrapper(None)

        # карта Entity -&gt; NodeWrapper, для быстрого поиска индекса
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

            parent_tf = getattr(ent.transform, &quot;parent&quot;, None)
            parent_ent = getattr(parent_tf, &quot;entity&quot;, None) if parent_tf is not None else None

            # если трансформ родителя не привязан к Entity – считаем, что это корень
            if isinstance(parent_ent, Entity) and parent_ent in self._obj_to_node:
                parent_node = self._obj_to_node[parent_ent]
            else:
                parent_node = self.root

            node.parent = parent_node
            parent_node.children.append(node)

    def _get_or_create_node(self, ent: Entity) -&gt; NodeWrapper:
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
        if row &lt; 0 or row &gt;= len(parent_node.children):
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
        if role == Qt.DisplayRole:
            return node.name
        return None

    # ==============================================================
    #   Поиск индекса по объекту сцены
    # ==============================================================

    def index_for_object(self, obj) -&gt; QModelIndex:
        &quot;&quot;&quot;
        Возвращает QModelIndex для данного Entity, если он есть в дереве.
        Transform3 здесь не учитываем, дерево чисто по сущностям.
        &quot;&quot;&quot;
        if not isinstance(obj, Entity):
            # если вдруг прилетел Transform3 – попробуем найти его владельца
            if isinstance(obj, Transform3) and getattr(obj, &quot;entity&quot;, None) is not None:
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

</code></pre>
</body>
</html>
