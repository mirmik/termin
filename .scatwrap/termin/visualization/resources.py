<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/resources.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# termin/visualization/resources.py<br>
from __future__ import annotations<br>
<br>
from dataclasses import dataclass, field<br>
from typing import Dict, Optional, TYPE_CHECKING<br>
<br>
if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов<br>
    from .material import Material<br>
    from .mesh import MeshDrawable<br>
    from .texture import Texture<br>
    from .entity import Component<br>
<br>
<br>
<br>
@dataclass<br>
class ResourceManager:<br>
    &quot;&quot;&quot;<br>
    Хранилище ресурсов, привязанное к конкретному редактору/сцене.<br>
    Никаких глобальных синглтонов.<br>
    &quot;&quot;&quot;<br>
    materials: Dict[str, &quot;Material&quot;] = field(default_factory=dict)<br>
    meshes: Dict[str, &quot;MeshDrawable&quot;] = field(default_factory=dict)<br>
    textures: Dict[str, &quot;Texture&quot;] = field(default_factory=dict)<br>
    components: Dict[str, type[&quot;Component&quot;]] = field(default_factory=dict)<br>
<br>
    # --------- Материалы ---------<br>
    def register_material(self, name: str, mat: &quot;Material&quot;):<br>
        self.materials[name] = mat<br>
<br>
    def get_material(self, name: str) -&gt; Optional[&quot;Material&quot;]:<br>
        return self.materials.get(name)<br>
<br>
    def list_material_names(self) -&gt; list[str]:<br>
        return sorted(self.materials.keys())<br>
<br>
    def find_material_name(self, mat: &quot;Material&quot;) -&gt; Optional[str]:<br>
        for n, m in self.materials.items():<br>
            if m is mat:<br>
                return n<br>
        return None<br>
<br>
    # --------- Меши ---------<br>
    def register_mesh(self, name: str, mesh: &quot;MeshDrawable&quot;):<br>
        self.meshes[name] = mesh<br>
<br>
    def get_mesh(self, name: str) -&gt; Optional[&quot;MeshDrawable&quot;]:<br>
        return self.meshes.get(name)<br>
<br>
    def list_mesh_names(self) -&gt; list[str]:<br>
        return sorted(self.meshes.keys())<br>
<br>
    def find_mesh_name(self, mesh: &quot;MeshDrawable&quot;) -&gt; Optional[str]:<br>
        for n, m in self.meshes.items():<br>
            if m is mesh:<br>
                return n<br>
        return None<br>
<br>
    # --------- Компоненты (на будущее) ---------<br>
    def register_component(self, name: str, cls: type[&quot;Component&quot;]):<br>
        self.components[name] = cls<br>
<br>
    def get_component(self, name: str) -&gt; Optional[type[&quot;Component&quot;]]:<br>
        return self.components.get(name)<br>
<br>
    def list_component_names(self) -&gt; list[str]:<br>
        return sorted(self.components.keys())<br>
<!-- END SCAT CODE -->
</body>
</html>
