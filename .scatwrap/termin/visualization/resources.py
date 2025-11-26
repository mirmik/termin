<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/resources.py</title>
</head>
<body>
<pre><code>
# termin/visualization/resources.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов
    from .material import Material
    from .mesh import MeshDrawable
    from .texture import Texture
    from .entity import Component



@dataclass
class ResourceManager:
    &quot;&quot;&quot;
    Хранилище ресурсов, привязанное к конкретному редактору/сцене.
    Никаких глобальных синглтонов.
    &quot;&quot;&quot;
    materials: Dict[str, &quot;Material&quot;] = field(default_factory=dict)
    meshes: Dict[str, &quot;MeshDrawable&quot;] = field(default_factory=dict)
    textures: Dict[str, &quot;Texture&quot;] = field(default_factory=dict)
    components: Dict[str, type[&quot;Component&quot;]] = field(default_factory=dict)

    # --------- Материалы ---------
    def register_material(self, name: str, mat: &quot;Material&quot;):
        self.materials[name] = mat

    def get_material(self, name: str) -&gt; Optional[&quot;Material&quot;]:
        return self.materials.get(name)

    def list_material_names(self) -&gt; list[str]:
        return sorted(self.materials.keys())

    def find_material_name(self, mat: &quot;Material&quot;) -&gt; Optional[str]:
        for n, m in self.materials.items():
            if m is mat:
                return n
        return None

    # --------- Меши ---------
    def register_mesh(self, name: str, mesh: &quot;MeshDrawable&quot;):
        self.meshes[name] = mesh

    def get_mesh(self, name: str) -&gt; Optional[&quot;MeshDrawable&quot;]:
        return self.meshes.get(name)

    def list_mesh_names(self) -&gt; list[str]:
        return sorted(self.meshes.keys())

    def find_mesh_name(self, mesh: &quot;MeshDrawable&quot;) -&gt; Optional[str]:
        for n, m in self.meshes.items():
            if m is mesh:
                return n
        return None

    # --------- Компоненты (на будущее) ---------
    def register_component(self, name: str, cls: type[&quot;Component&quot;]):
        self.components[name] = cls

    def get_component(self, name: str) -&gt; Optional[type[&quot;Component&quot;]]:
        return self.components.get(name)

    def list_component_names(self) -&gt; list[str]:
        return sorted(self.components.keys())

</code></pre>
</body>
</html>
