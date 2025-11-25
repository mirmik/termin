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
    """
    Хранилище ресурсов, привязанное к конкретному редактору/сцене.
    Никаких глобальных синглтонов.
    """
    materials: Dict[str, "Material"] = field(default_factory=dict)
    meshes: Dict[str, "MeshDrawable"] = field(default_factory=dict)
    textures: Dict[str, "Texture"] = field(default_factory=dict)
    components: Dict[str, type["Component"]] = field(default_factory=dict)

    # --------- Материалы ---------
    def register_material(self, name: str, mat: "Material"):
        self.materials[name] = mat

    def get_material(self, name: str) -> Optional["Material"]:
        return self.materials.get(name)

    def list_material_names(self) -> list[str]:
        return sorted(self.materials.keys())

    def find_material_name(self, mat: "Material") -> Optional[str]:
        for n, m in self.materials.items():
            if m is mat:
                return n
        return None

    # --------- Компоненты (на будущее) ---------
    def register_component(self, name: str, cls: type["Component"]):
        self.components[name] = cls

    def get_component(self, name: str) -> Optional[type["Component"]]:
        return self.components.get(name)

    def list_component_names(self) -> list[str]:
        return sorted(self.components.keys())
