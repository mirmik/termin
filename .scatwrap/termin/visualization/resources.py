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
&#9;from .material import Material<br>
&#9;from .mesh import MeshDrawable<br>
&#9;from .texture import Texture<br>
&#9;from .entity import Component<br>
<br>
<br>
<br>
@dataclass<br>
class ResourceManager:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Хранилище ресурсов, привязанное к конкретному редактору/сцене.<br>
&#9;Никаких глобальных синглтонов.<br>
&#9;&quot;&quot;&quot;<br>
&#9;materials: Dict[str, &quot;Material&quot;] = field(default_factory=dict)<br>
&#9;meshes: Dict[str, &quot;MeshDrawable&quot;] = field(default_factory=dict)<br>
&#9;textures: Dict[str, &quot;Texture&quot;] = field(default_factory=dict)<br>
&#9;components: Dict[str, type[&quot;Component&quot;]] = field(default_factory=dict)<br>
<br>
&#9;# --------- Материалы ---------<br>
&#9;def register_material(self, name: str, mat: &quot;Material&quot;):<br>
&#9;&#9;self.materials[name] = mat<br>
<br>
&#9;def get_material(self, name: str) -&gt; Optional[&quot;Material&quot;]:<br>
&#9;&#9;return self.materials.get(name)<br>
<br>
&#9;def list_material_names(self) -&gt; list[str]:<br>
&#9;&#9;return sorted(self.materials.keys())<br>
<br>
&#9;def find_material_name(self, mat: &quot;Material&quot;) -&gt; Optional[str]:<br>
&#9;&#9;for n, m in self.materials.items():<br>
&#9;&#9;&#9;if m is mat:<br>
&#9;&#9;&#9;&#9;return n<br>
&#9;&#9;return None<br>
<br>
&#9;# --------- Меши ---------<br>
&#9;def register_mesh(self, name: str, mesh: &quot;MeshDrawable&quot;):<br>
&#9;&#9;self.meshes[name] = mesh<br>
<br>
&#9;def get_mesh(self, name: str) -&gt; Optional[&quot;MeshDrawable&quot;]:<br>
&#9;&#9;return self.meshes.get(name)<br>
<br>
&#9;def list_mesh_names(self) -&gt; list[str]:<br>
&#9;&#9;return sorted(self.meshes.keys())<br>
<br>
&#9;def find_mesh_name(self, mesh: &quot;MeshDrawable&quot;) -&gt; Optional[str]:<br>
&#9;&#9;for n, m in self.meshes.items():<br>
&#9;&#9;&#9;if m is mesh:<br>
&#9;&#9;&#9;&#9;return n<br>
&#9;&#9;return None<br>
<br>
&#9;# --------- Компоненты (на будущее) ---------<br>
&#9;def register_component(self, name: str, cls: type[&quot;Component&quot;]):<br>
&#9;&#9;self.components[name] = cls<br>
<br>
&#9;def get_component(self, name: str) -&gt; Optional[type[&quot;Component&quot;]]:<br>
&#9;&#9;return self.components.get(name)<br>
<br>
&#9;def list_component_names(self) -&gt; list[str]:<br>
&#9;&#9;return sorted(self.components.keys())<br>
<!-- END SCAT CODE -->
</body>
</html>
