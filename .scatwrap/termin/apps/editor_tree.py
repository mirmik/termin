<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/apps/editor_tree.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# ===== termin/apps/editor_tree.py =====<br>
from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex<br>
<br>
from termin.visualization.scene import Scene<br>
from termin.visualization.entity import Entity<br>
from termin.kinematic.transform import Transform3<br>
<br>
<br>
class NodeWrapper:<br>
    &quot;&quot;&quot;<br>
    Узел дерева. Держит только Entity<br>
    (root держит obj=None).<br>
    &quot;&quot;&quot;<br>
    def __init__(self, obj: Entity | None, parent=None):<br>
        self.obj = obj<br>
        self.parent = parent<br>
        self.children: list[NodeWrapper] = []<br>
<br>
    @property<br>
    def name(self) -&gt; str:<br>
        if isinstance(self.obj, Entity):<br>
            return f&quot;Entity: {self.obj.name}&quot;<br>
        return &quot;Scene&quot;<br>
<br>
<br>
class SceneTreeModel(QAbstractItemModel):<br>
    &quot;&quot;&quot;<br>
    Дерево: иерархия Entity, повторяющая иерархию Transform3.<br>
    Transform-узлы в дереве НЕ показываем.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, scene: Scene):<br>
        super().__init__()<br>
        self.scene = scene<br>
        self.root = NodeWrapper(None)<br>
<br>
        # карта Entity -&gt; NodeWrapper, для быстрого поиска индекса<br>
        self._obj_to_node: dict[Entity, NodeWrapper] = {}<br>
<br>
        self._build_hierarchy()<br>
<br>
    # ------------------------------------------------------<br>
    # Build Tree from scene<br>
    # ------------------------------------------------------<br>
    def _build_hierarchy(self):<br>
        # чистим на случай пересборки<br>
        self.root.children.clear()<br>
        self._obj_to_node.clear()<br>
<br>
        # Сначала создаём узлы для всех сущностей<br>
        for ent in self.scene.entities:<br>
            self._get_or_create_node(ent)<br>
<br>
        # Теперь связываем родителей и детей<br>
        for ent in self.scene.entities:<br>
            node = self._obj_to_node[ent]<br>
<br>
            parent_tf = getattr(ent.transform, &quot;parent&quot;, None)<br>
            parent_ent = getattr(parent_tf, &quot;entity&quot;, None) if parent_tf is not None else None<br>
<br>
            # если трансформ родителя не привязан к Entity – считаем, что это корень<br>
            if isinstance(parent_ent, Entity) and parent_ent in self._obj_to_node:<br>
                parent_node = self._obj_to_node[parent_ent]<br>
            else:<br>
                parent_node = self.root<br>
<br>
            node.parent = parent_node<br>
            parent_node.children.append(node)<br>
<br>
    def _get_or_create_node(self, ent: Entity) -&gt; NodeWrapper:<br>
        node = self._obj_to_node.get(ent)<br>
        if node is None:<br>
            node = NodeWrapper(ent, parent=None)<br>
            self._obj_to_node[ent] = node<br>
        return node<br>
<br>
    # ==============================================================<br>
    # Qt model interface<br>
    # ==============================================================<br>
<br>
    def index(self, row, column, parent):<br>
        parent_node = self.root if not parent.isValid() else parent.internalPointer()<br>
        if row &lt; 0 or row &gt;= len(parent_node.children):<br>
            return QModelIndex()<br>
        return self.createIndex(row, column, parent_node.children[row])<br>
<br>
    def parent(self, index):<br>
        if not index.isValid():<br>
            return QModelIndex()<br>
<br>
        node: NodeWrapper = index.internalPointer()<br>
        parent = node.parent<br>
        if parent is None or parent is self.root:<br>
            return QModelIndex()<br>
<br>
        grand = parent.parent or self.root<br>
        row = grand.children.index(parent)<br>
        return self.createIndex(row, 0, parent)<br>
<br>
    def rowCount(self, parent):<br>
        node = self.root if not parent.isValid() else parent.internalPointer()<br>
        return len(node.children)<br>
<br>
    def columnCount(self, parent):<br>
        return 1<br>
<br>
    def data(self, index, role):<br>
        if not index.isValid():<br>
            return None<br>
        node: NodeWrapper = index.internalPointer()<br>
        if role == Qt.DisplayRole:<br>
            return node.name<br>
        return None<br>
<br>
    # ==============================================================<br>
    #   Поиск индекса по объекту сцены<br>
    # ==============================================================<br>
<br>
    def index_for_object(self, obj) -&gt; QModelIndex:<br>
        &quot;&quot;&quot;<br>
        Возвращает QModelIndex для данного Entity, если он есть в дереве.<br>
        Transform3 здесь не учитываем, дерево чисто по сущностям.<br>
        &quot;&quot;&quot;<br>
        if not isinstance(obj, Entity):<br>
            # если вдруг прилетел Transform3 – попробуем найти его владельца<br>
            if isinstance(obj, Transform3) and getattr(obj, &quot;entity&quot;, None) is not None:<br>
                obj = obj.entity<br>
            else:<br>
                return QModelIndex()<br>
<br>
        node = self._obj_to_node.get(obj)<br>
        if node is None:<br>
            return QModelIndex()<br>
<br>
        # строим путь от этого узла до root<br>
        path_nodes = []<br>
        cur = node<br>
        while cur is not None and cur is not self.root:<br>
            path_nodes.append(cur)<br>
            cur = cur.parent<br>
<br>
        path_nodes.reverse()<br>
<br>
        parent_index = QModelIndex()<br>
        parent_node = self.root<br>
<br>
        for n in path_nodes:<br>
            row = parent_node.children.index(n)<br>
            idx = self.index(row, 0, parent_index)<br>
            parent_index = idx<br>
            parent_node = n<br>
<br>
        return parent_index<br>
<!-- END SCAT CODE -->
</body>
</html>
