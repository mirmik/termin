<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/mesh.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;GPU mesh helper built on top of :mod:`termin.mesh` geometry.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from typing import Dict, Optional<br>
<br>
from termin.mesh.mesh import Mesh2, Mesh3<br>
from .entity import RenderContext<br>
from .backends.base import MeshHandle<br>
<br>
<br>
class MeshDrawable:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Рендер-ресурс для 3D-меша.<br>
<br>
&#9;Держит ссылку на CPU-геометрию (Mesh3), умеет грузить её в GPU через<br>
&#9;graphics backend, хранит GPU-хендлы per-context, а также метаданные<br>
&#9;ресурса: имя и source_id (путь / идентификатор в системе ресурсов).<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;RESOURCE_KIND = &quot;mesh&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;mesh: Mesh3,<br>
&#9;&#9;*,<br>
&#9;&#9;source_id: Optional[str] = None,<br>
&#9;&#9;name: Optional[str] = None,<br>
&#9;):<br>
&#9;&#9;self._mesh: Mesh3 = mesh<br>
<br>
&#9;&#9;# если нормали ещё не посчитаны — посчитаем здесь, а не в Mesh3<br>
&#9;&#9;if self._mesh.vertex_normals is None:<br>
&#9;&#9;&#9;self._mesh.compute_vertex_normals()<br>
<br>
&#9;&#9;# GPU-хендлы на разных контекстах<br>
&#9;&#9;self._context_resources: Dict[int, MeshHandle] = {}<br>
<br>
&#9;&#9;# ресурсные метаданные (чтоб Mesh3 о них не знал)<br>
&#9;&#9;self._source_id: Optional[str] = source_id<br>
&#9;&#9;# name по умолчанию можно взять из source_id, если имя не задано явно<br>
&#9;&#9;self.name: Optional[str] = name or source_id<br>
<br>
&#9;# --------- интерфейс ресурса ---------<br>
<br>
&#9;@property<br>
&#9;def resource_kind(self) -&gt; str:<br>
&#9;&#9;return self.RESOURCE_KIND<br>
<br>
&#9;@property<br>
&#9;def resource_id(self) -&gt; Optional[str]:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;То, что кладём в сериализацию и по чему грузим обратно.<br>
&#9;&#9;Обычно это путь к файлу или GUID.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return self._source_id<br>
<br>
&#9;def set_source_id(self, source_id: str):<br>
&#9;&#9;self._source_id = source_id<br>
&#9;&#9;# если имени ещё не было — логично синхронизировать<br>
&#9;&#9;if self.name is None:<br>
&#9;&#9;&#9;self.name = source_id<br>
<br>
&#9;# --------- доступ к геометрии ---------<br>
<br>
&#9;@property<br>
&#9;def mesh(self) -&gt; Mesh3:<br>
&#9;&#9;return self._mesh<br>
<br>
&#9;@mesh.setter<br>
&#9;def mesh(self, value: Mesh3):<br>
&#9;&#9;# при смене геометрии надо будет перевыгрузить в GPU<br>
&#9;&#9;self.delete()<br>
&#9;&#9;self._mesh = value<br>
&#9;&#9;if self._mesh.vertex_normals is None:<br>
&#9;&#9;&#9;self._mesh.compute_vertex_normals()<br>
<br>
&#9;# --------- GPU lifecycle ---------<br>
<br>
&#9;def upload(self, context: RenderContext):<br>
&#9;&#9;ctx = context.context_key<br>
&#9;&#9;if ctx in self._context_resources:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;# backend знает, как из Mesh3 сделать GPU-буферы<br>
&#9;&#9;handle = context.graphics.create_mesh(self._mesh)<br>
&#9;&#9;self._context_resources[ctx] = handle<br>
<br>
&#9;def draw(self, context: RenderContext):<br>
&#9;&#9;ctx = context.context_key<br>
&#9;&#9;if ctx not in self._context_resources:<br>
&#9;&#9;&#9;self.upload(context)<br>
&#9;&#9;handle = self._context_resources[ctx]<br>
&#9;&#9;handle.draw()<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;for handle in self._context_resources.values():<br>
&#9;&#9;&#9;handle.delete()<br>
&#9;&#9;self._context_resources.clear()<br>
<br>
&#9;# --------- сериализация / десериализация ---------<br>
<br>
&#9;def serialize(self) -&gt; dict:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает словарь с идентификатором ресурса.<br>
<br>
&#9;&#9;По-хорошему, source_id должен выставлять загрузчик ресурсов<br>
&#9;&#9;(например, путь к файлу или GUID). Mesh3 при этом ни о чём<br>
&#9;&#9;таком знать не обязан.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if self._source_id is not None:<br>
&#9;&#9;&#9;return {&quot;mesh&quot;: self._source_id}<br>
<br>
&#9;&#9;# Для совместимости со старым кодом: если Mesh3 всё-таки<br>
&#9;&#9;# имеет поле source_path — используем его, но это считается<br>
&#9;&#9;# legacy и лучше постепенно от него избавляться.<br>
&#9;&#9;if hasattr(self._mesh, &quot;source_path&quot;):<br>
&#9;&#9;&#9;return {&quot;mesh&quot;: getattr(self._mesh, &quot;source_path&quot;)}<br>
<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;&quot;MeshDrawable.serialize: не задан source_id и у mesh нет source_path. &quot;<br>
&#9;&#9;&#9;&quot;Нечего сохранять в качестве идентификатора ресурса.&quot;<br>
&#9;&#9;)<br>
<br>
&#9;@classmethod<br>
&#9;def deserialize(cls, data: dict, context) -&gt; &quot;MeshDrawable&quot;:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Восстановление drawable по идентификатору меша.<br>
<br>
&#9;&#9;Предполагается, что `context.load_mesh(mesh_id)` вернёт Mesh3.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;mesh_id = data[&quot;mesh&quot;]<br>
&#9;&#9;mesh = context.load_mesh(mesh_id)  # должен вернуть Mesh3<br>
&#9;&#9;return cls(mesh, source_id=mesh_id, name=mesh_id)<br>
<br>
&#9;# --------- утилиты для инспектора / дебага ---------<br>
<br>
&#9;@staticmethod<br>
&#9;def from_vertices_indices(vertices, indices) -&gt; &quot;MeshDrawable&quot;:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Быстрая обёртка поверх Mesh3 для случаев, когда<br>
&#9;&#9;геометрия создаётся на лету.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;mesh = Mesh3(vertices=vertices, triangles=indices)<br>
&#9;&#9;return MeshDrawable(mesh)<br>
<br>
&#9;def interleaved_buffer(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Проброс к геометрии. Формат буфера и layout определяет Mesh3.<br>
&#9;&#9;Это всё ещё геометрическая часть, не завязанная на конкретный API.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return self._mesh.interleaved_buffer()<br>
<br>
&#9;def get_vertex_layout(self):<br>
&#9;&#9;return self._mesh.get_vertex_layout()<br>
<br>
<br>
class Mesh2Drawable:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Рендер-ресурс для 2D-меша (линии/треугольники в плоскости).<br>
&#9;Аналогично MeshDrawable, но поверх Mesh2.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;RESOURCE_KIND = &quot;mesh2&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;mesh: Mesh2,<br>
&#9;&#9;*,<br>
&#9;&#9;source_id: Optional[str] = None,<br>
&#9;&#9;name: Optional[str] = None,<br>
&#9;):<br>
&#9;&#9;self._mesh: Mesh2 = mesh<br>
&#9;&#9;self._context_resources: Dict[int, MeshHandle] = {}<br>
&#9;&#9;self._source_id: Optional[str] = source_id<br>
&#9;&#9;self.name: Optional[str] = name or source_id<br>
<br>
&#9;@property<br>
&#9;def resource_kind(self) -&gt; str:<br>
&#9;&#9;return self.RESOURCE_KIND<br>
<br>
&#9;@property<br>
&#9;def resource_id(self) -&gt; Optional[str]:<br>
&#9;&#9;return self._source_id<br>
<br>
&#9;def set_source_id(self, source_id: str):<br>
&#9;&#9;self._source_id = source_id<br>
&#9;&#9;if self.name is None:<br>
&#9;&#9;&#9;self.name = source_id<br>
<br>
&#9;@property<br>
&#9;def mesh(self) -&gt; Mesh2:<br>
&#9;&#9;return self._mesh<br>
<br>
&#9;@mesh.setter<br>
&#9;def mesh(self, value: Mesh2):<br>
&#9;&#9;self.delete()<br>
&#9;&#9;self._mesh = value<br>
<br>
&#9;def upload(self, context: RenderContext):<br>
&#9;&#9;ctx = context.context_key<br>
&#9;&#9;if ctx in self._context_resources:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;handle = context.graphics.create_mesh(self._mesh)<br>
&#9;&#9;self._context_resources[ctx] = handle<br>
<br>
&#9;def draw(self, context: RenderContext):<br>
&#9;&#9;ctx = context.context_key<br>
&#9;&#9;if ctx not in self._context_resources:<br>
&#9;&#9;&#9;self.upload(context)<br>
&#9;&#9;handle = self._context_resources[ctx]<br>
&#9;&#9;handle.draw()<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;for handle in self._context_resources.values():<br>
&#9;&#9;&#9;handle.delete()<br>
&#9;&#9;self._context_resources.clear()<br>
<br>
&#9;def serialize(self) -&gt; dict:<br>
&#9;&#9;if self._source_id is not None:<br>
&#9;&#9;&#9;return {&quot;mesh&quot;: self._source_id}<br>
&#9;&#9;if hasattr(self._mesh, &quot;source_path&quot;):<br>
&#9;&#9;&#9;return {&quot;mesh&quot;: getattr(self._mesh, &quot;source_path&quot;)}<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;&quot;Mesh2Drawable.serialize: не задан source_id и нет mesh.source_path.&quot;<br>
&#9;&#9;)<br>
<br>
&#9;@classmethod<br>
&#9;def deserialize(cls, data: dict, context) -&gt; &quot;Mesh2Drawable&quot;:<br>
&#9;&#9;mesh_id = data[&quot;mesh&quot;]<br>
&#9;&#9;mesh = context.load_mesh(mesh_id)  # должен вернуть Mesh2<br>
&#9;&#9;return cls(mesh, source_id=mesh_id, name=mesh_id)<br>
<br>
&#9;@staticmethod<br>
&#9;def from_vertices_indices(vertices, indices) -&gt; &quot;Mesh2Drawable&quot;:<br>
&#9;&#9;mesh = Mesh2(vertices=vertices, indices=indices)<br>
&#9;&#9;return Mesh2Drawable(mesh)<br>
<br>
&#9;def interleaved_buffer(self):<br>
&#9;&#9;return self._mesh.interleaved_buffer()<br>
<br>
&#9;def get_vertex_layout(self):<br>
&#9;&#9;return self._mesh.get_vertex_layout()<br>
<!-- END SCAT CODE -->
</body>
</html>
