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
    &quot;&quot;&quot;<br>
    Рендер-ресурс для 3D-меша.<br>
<br>
    Держит ссылку на CPU-геометрию (Mesh3), умеет грузить её в GPU через<br>
    graphics backend, хранит GPU-хендлы per-context, а также метаданные<br>
    ресурса: имя и source_id (путь / идентификатор в системе ресурсов).<br>
    &quot;&quot;&quot;<br>
<br>
    RESOURCE_KIND = &quot;mesh&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        mesh: Mesh3,<br>
        *,<br>
        source_id: Optional[str] = None,<br>
        name: Optional[str] = None,<br>
    ):<br>
        self._mesh: Mesh3 = mesh<br>
<br>
        # если нормали ещё не посчитаны — посчитаем здесь, а не в Mesh3<br>
        if self._mesh.vertex_normals is None:<br>
            self._mesh.compute_vertex_normals()<br>
<br>
        # GPU-хендлы на разных контекстах<br>
        self._context_resources: Dict[int, MeshHandle] = {}<br>
<br>
        # ресурсные метаданные (чтоб Mesh3 о них не знал)<br>
        self._source_id: Optional[str] = source_id<br>
        # name по умолчанию можно взять из source_id, если имя не задано явно<br>
        self.name: Optional[str] = name or source_id<br>
<br>
    # --------- интерфейс ресурса ---------<br>
<br>
    @property<br>
    def resource_kind(self) -&gt; str:<br>
        return self.RESOURCE_KIND<br>
<br>
    @property<br>
    def resource_id(self) -&gt; Optional[str]:<br>
        &quot;&quot;&quot;<br>
        То, что кладём в сериализацию и по чему грузим обратно.<br>
        Обычно это путь к файлу или GUID.<br>
        &quot;&quot;&quot;<br>
        return self._source_id<br>
<br>
    def set_source_id(self, source_id: str):<br>
        self._source_id = source_id<br>
        # если имени ещё не было — логично синхронизировать<br>
        if self.name is None:<br>
            self.name = source_id<br>
<br>
    # --------- доступ к геометрии ---------<br>
<br>
    @property<br>
    def mesh(self) -&gt; Mesh3:<br>
        return self._mesh<br>
<br>
    @mesh.setter<br>
    def mesh(self, value: Mesh3):<br>
        # при смене геометрии надо будет перевыгрузить в GPU<br>
        self.delete()<br>
        self._mesh = value<br>
        if self._mesh.vertex_normals is None:<br>
            self._mesh.compute_vertex_normals()<br>
<br>
    # --------- GPU lifecycle ---------<br>
<br>
    def upload(self, context: RenderContext):<br>
        ctx = context.context_key<br>
        if ctx in self._context_resources:<br>
            return<br>
        # backend знает, как из Mesh3 сделать GPU-буферы<br>
        handle = context.graphics.create_mesh(self._mesh)<br>
        self._context_resources[ctx] = handle<br>
<br>
    def draw(self, context: RenderContext):<br>
        ctx = context.context_key<br>
        if ctx not in self._context_resources:<br>
            self.upload(context)<br>
        handle = self._context_resources[ctx]<br>
        handle.draw()<br>
<br>
    def delete(self):<br>
        for handle in self._context_resources.values():<br>
            handle.delete()<br>
        self._context_resources.clear()<br>
<br>
    # --------- сериализация / десериализация ---------<br>
<br>
    def serialize(self) -&gt; dict:<br>
        &quot;&quot;&quot;<br>
        Возвращает словарь с идентификатором ресурса.<br>
<br>
        По-хорошему, source_id должен выставлять загрузчик ресурсов<br>
        (например, путь к файлу или GUID). Mesh3 при этом ни о чём<br>
        таком знать не обязан.<br>
        &quot;&quot;&quot;<br>
        if self._source_id is not None:<br>
            return {&quot;mesh&quot;: self._source_id}<br>
<br>
        # Для совместимости со старым кодом: если Mesh3 всё-таки<br>
        # имеет поле source_path — используем его, но это считается<br>
        # legacy и лучше постепенно от него избавляться.<br>
        if hasattr(self._mesh, &quot;source_path&quot;):<br>
            return {&quot;mesh&quot;: getattr(self._mesh, &quot;source_path&quot;)}<br>
<br>
        raise ValueError(<br>
            &quot;MeshDrawable.serialize: не задан source_id и у mesh нет source_path. &quot;<br>
            &quot;Нечего сохранять в качестве идентификатора ресурса.&quot;<br>
        )<br>
<br>
    @classmethod<br>
    def deserialize(cls, data: dict, context) -&gt; &quot;MeshDrawable&quot;:<br>
        &quot;&quot;&quot;<br>
        Восстановление drawable по идентификатору меша.<br>
<br>
        Предполагается, что `context.load_mesh(mesh_id)` вернёт Mesh3.<br>
        &quot;&quot;&quot;<br>
        mesh_id = data[&quot;mesh&quot;]<br>
        mesh = context.load_mesh(mesh_id)  # должен вернуть Mesh3<br>
        return cls(mesh, source_id=mesh_id, name=mesh_id)<br>
<br>
    # --------- утилиты для инспектора / дебага ---------<br>
<br>
    @staticmethod<br>
    def from_vertices_indices(vertices, indices) -&gt; &quot;MeshDrawable&quot;:<br>
        &quot;&quot;&quot;<br>
        Быстрая обёртка поверх Mesh3 для случаев, когда<br>
        геометрия создаётся на лету.<br>
        &quot;&quot;&quot;<br>
        mesh = Mesh3(vertices=vertices, triangles=indices)<br>
        return MeshDrawable(mesh)<br>
<br>
    def interleaved_buffer(self):<br>
        &quot;&quot;&quot;<br>
        Проброс к геометрии. Формат буфера и layout определяет Mesh3.<br>
        Это всё ещё геометрическая часть, не завязанная на конкретный API.<br>
        &quot;&quot;&quot;<br>
        return self._mesh.interleaved_buffer()<br>
<br>
    def get_vertex_layout(self):<br>
        return self._mesh.get_vertex_layout()<br>
<br>
<br>
class Mesh2Drawable:<br>
    &quot;&quot;&quot;<br>
    Рендер-ресурс для 2D-меша (линии/треугольники в плоскости).<br>
    Аналогично MeshDrawable, но поверх Mesh2.<br>
    &quot;&quot;&quot;<br>
<br>
    RESOURCE_KIND = &quot;mesh2&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        mesh: Mesh2,<br>
        *,<br>
        source_id: Optional[str] = None,<br>
        name: Optional[str] = None,<br>
    ):<br>
        self._mesh: Mesh2 = mesh<br>
        self._context_resources: Dict[int, MeshHandle] = {}<br>
        self._source_id: Optional[str] = source_id<br>
        self.name: Optional[str] = name or source_id<br>
<br>
    @property<br>
    def resource_kind(self) -&gt; str:<br>
        return self.RESOURCE_KIND<br>
<br>
    @property<br>
    def resource_id(self) -&gt; Optional[str]:<br>
        return self._source_id<br>
<br>
    def set_source_id(self, source_id: str):<br>
        self._source_id = source_id<br>
        if self.name is None:<br>
            self.name = source_id<br>
<br>
    @property<br>
    def mesh(self) -&gt; Mesh2:<br>
        return self._mesh<br>
<br>
    @mesh.setter<br>
    def mesh(self, value: Mesh2):<br>
        self.delete()<br>
        self._mesh = value<br>
<br>
    def upload(self, context: RenderContext):<br>
        ctx = context.context_key<br>
        if ctx in self._context_resources:<br>
            return<br>
        handle = context.graphics.create_mesh(self._mesh)<br>
        self._context_resources[ctx] = handle<br>
<br>
    def draw(self, context: RenderContext):<br>
        ctx = context.context_key<br>
        if ctx not in self._context_resources:<br>
            self.upload(context)<br>
        handle = self._context_resources[ctx]<br>
        handle.draw()<br>
<br>
    def delete(self):<br>
        for handle in self._context_resources.values():<br>
            handle.delete()<br>
        self._context_resources.clear()<br>
<br>
    def serialize(self) -&gt; dict:<br>
        if self._source_id is not None:<br>
            return {&quot;mesh&quot;: self._source_id}<br>
        if hasattr(self._mesh, &quot;source_path&quot;):<br>
            return {&quot;mesh&quot;: getattr(self._mesh, &quot;source_path&quot;)}<br>
        raise ValueError(<br>
            &quot;Mesh2Drawable.serialize: не задан source_id и нет mesh.source_path.&quot;<br>
        )<br>
<br>
    @classmethod<br>
    def deserialize(cls, data: dict, context) -&gt; &quot;Mesh2Drawable&quot;:<br>
        mesh_id = data[&quot;mesh&quot;]<br>
        mesh = context.load_mesh(mesh_id)  # должен вернуть Mesh2<br>
        return cls(mesh, source_id=mesh_id, name=mesh_id)<br>
<br>
    @staticmethod<br>
    def from_vertices_indices(vertices, indices) -&gt; &quot;Mesh2Drawable&quot;:<br>
        mesh = Mesh2(vertices=vertices, indices=indices)<br>
        return Mesh2Drawable(mesh)<br>
<br>
    def interleaved_buffer(self):<br>
        return self._mesh.interleaved_buffer()<br>
<br>
    def get_vertex_layout(self):<br>
        return self._mesh.get_vertex_layout()<br>
<!-- END SCAT CODE -->
</body>
</html>
