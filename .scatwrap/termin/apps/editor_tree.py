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
&#9;&quot;&quot;&quot;<br>
&#9;Узел дерева. Держит только Entity<br>
&#9;(root держит obj=None).<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, obj: Entity | None, parent=None):<br>
&#9;&#9;self.obj = obj<br>
&#9;&#9;self.parent = parent<br>
&#9;&#9;self.children: list[NodeWrapper] = []<br>
<br>
&#9;@property<br>
&#9;def name(self) -&gt; str:<br>
&#9;&#9;if isinstance(self.obj, Entity):<br>
&#9;&#9;&#9;return f&quot;Entity: {self.obj.name}&quot;<br>
&#9;&#9;return &quot;Scene&quot;<br>
<br>
<br>
class SceneTreeModel(QAbstractItemModel):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Дерево: иерархия Entity, повторяющая иерархию Transform3.<br>
&#9;Transform-узлы в дереве НЕ показываем.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, scene: Scene):<br>
&#9;&#9;super().__init__()<br>
&#9;&#9;self.scene = scene<br>
&#9;&#9;self.root = NodeWrapper(None)<br>
<br>
&#9;&#9;# карта Entity -&gt; NodeWrapper, для быстрого поиска индекса<br>
&#9;&#9;self._obj_to_node: dict[Entity, NodeWrapper] = {}<br>
<br>
&#9;&#9;self._build_hierarchy()<br>
<br>
&#9;# ------------------------------------------------------<br>
&#9;# Build Tree from scene<br>
&#9;# ------------------------------------------------------<br>
&#9;def _build_hierarchy(self):<br>
&#9;&#9;# чистим на случай пересборки<br>
&#9;&#9;self.root.children.clear()<br>
&#9;&#9;self._obj_to_node.clear()<br>
<br>
&#9;&#9;# Сначала создаём узлы для всех сущностей<br>
&#9;&#9;for ent in self.scene.entities:<br>
&#9;&#9;&#9;self._get_or_create_node(ent)<br>
<br>
&#9;&#9;# Теперь связываем родителей и детей<br>
&#9;&#9;for ent in self.scene.entities:<br>
&#9;&#9;&#9;node = self._obj_to_node[ent]<br>
<br>
&#9;&#9;&#9;parent_tf = getattr(ent.transform, &quot;parent&quot;, None)<br>
&#9;&#9;&#9;parent_ent = getattr(parent_tf, &quot;entity&quot;, None) if parent_tf is not None else None<br>
<br>
&#9;&#9;&#9;# если трансформ родителя не привязан к Entity – считаем, что это корень<br>
&#9;&#9;&#9;if isinstance(parent_ent, Entity) and parent_ent in self._obj_to_node:<br>
&#9;&#9;&#9;&#9;parent_node = self._obj_to_node[parent_ent]<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;parent_node = self.root<br>
<br>
&#9;&#9;&#9;node.parent = parent_node<br>
&#9;&#9;&#9;parent_node.children.append(node)<br>
<br>
&#9;def _get_or_create_node(self, ent: Entity) -&gt; NodeWrapper:<br>
&#9;&#9;node = self._obj_to_node.get(ent)<br>
&#9;&#9;if node is None:<br>
&#9;&#9;&#9;node = NodeWrapper(ent, parent=None)<br>
&#9;&#9;&#9;self._obj_to_node[ent] = node<br>
&#9;&#9;return node<br>
<br>
&#9;# ==============================================================<br>
&#9;# Qt model interface<br>
&#9;# ==============================================================<br>
<br>
&#9;def index(self, row, column, parent):<br>
&#9;&#9;parent_node = self.root if not parent.isValid() else parent.internalPointer()<br>
&#9;&#9;if row &lt; 0 or row &gt;= len(parent_node.children):<br>
&#9;&#9;&#9;return QModelIndex()<br>
&#9;&#9;return self.createIndex(row, column, parent_node.children[row])<br>
<br>
&#9;def parent(self, index):<br>
&#9;&#9;if not index.isValid():<br>
&#9;&#9;&#9;return QModelIndex()<br>
<br>
&#9;&#9;node: NodeWrapper = index.internalPointer()<br>
&#9;&#9;parent = node.parent<br>
&#9;&#9;if parent is None or parent is self.root:<br>
&#9;&#9;&#9;return QModelIndex()<br>
<br>
&#9;&#9;grand = parent.parent or self.root<br>
&#9;&#9;row = grand.children.index(parent)<br>
&#9;&#9;return self.createIndex(row, 0, parent)<br>
<br>
&#9;def rowCount(self, parent):<br>
&#9;&#9;node = self.root if not parent.isValid() else parent.internalPointer()<br>
&#9;&#9;return len(node.children)<br>
<br>
&#9;def columnCount(self, parent):<br>
&#9;&#9;return 1<br>
<br>
&#9;def data(self, index, role):<br>
&#9;&#9;if not index.isValid():<br>
&#9;&#9;&#9;return None<br>
&#9;&#9;node: NodeWrapper = index.internalPointer()<br>
&#9;&#9;if role == Qt.DisplayRole:<br>
&#9;&#9;&#9;return node.name<br>
&#9;&#9;return None<br>
<br>
&#9;# ==============================================================<br>
&#9;#   Поиск индекса по объекту сцены<br>
&#9;# ==============================================================<br>
<br>
&#9;def index_for_object(self, obj) -&gt; QModelIndex:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает QModelIndex для данного Entity, если он есть в дереве.<br>
&#9;&#9;Transform3 здесь не учитываем, дерево чисто по сущностям.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if not isinstance(obj, Entity):<br>
&#9;&#9;&#9;# если вдруг прилетел Transform3 – попробуем найти его владельца<br>
&#9;&#9;&#9;if isinstance(obj, Transform3) and getattr(obj, &quot;entity&quot;, None) is not None:<br>
&#9;&#9;&#9;&#9;obj = obj.entity<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;return QModelIndex()<br>
<br>
&#9;&#9;node = self._obj_to_node.get(obj)<br>
&#9;&#9;if node is None:<br>
&#9;&#9;&#9;return QModelIndex()<br>
<br>
&#9;&#9;# строим путь от этого узла до root<br>
&#9;&#9;path_nodes = []<br>
&#9;&#9;cur = node<br>
&#9;&#9;while cur is not None and cur is not self.root:<br>
&#9;&#9;&#9;path_nodes.append(cur)<br>
&#9;&#9;&#9;cur = cur.parent<br>
<br>
&#9;&#9;path_nodes.reverse()<br>
<br>
&#9;&#9;parent_index = QModelIndex()<br>
&#9;&#9;parent_node = self.root<br>
<br>
&#9;&#9;for n in path_nodes:<br>
&#9;&#9;&#9;row = parent_node.children.index(n)<br>
&#9;&#9;&#9;idx = self.index(row, 0, parent_index)<br>
&#9;&#9;&#9;parent_index = idx<br>
&#9;&#9;&#9;parent_node = n<br>
<br>
&#9;&#9;return parent_index<br>
<!-- END SCAT CODE -->
</body>
</html>
