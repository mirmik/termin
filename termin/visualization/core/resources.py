# termin/visualization/resources.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов
    from termin.visualization.core.material import Material
    from termin.visualization.core.mesh import MeshDrawable
    from termin.visualization.render.texture import Texture
    from termin.visualization.core.entity import Component



class ResourceManager:
    """
    Глобальный менеджер ресурсов редактора.
    """

    _instance: "ResourceManager | None" = None

    def __init__(self):
        self.materials: Dict[str, "Material"] = {}
        self.meshes: Dict[str, "MeshDrawable"] = {}
        self.textures: Dict[str, "Texture"] = {}
        self.components: Dict[str, type["Component"]] = {}

    @classmethod
    def instance(cls) -> "ResourceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

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

    # --------- Меши ---------
    def register_mesh(self, name: str, mesh: "MeshDrawable"):
        self.meshes[name] = mesh

    def get_mesh(self, name: str) -> Optional["MeshDrawable"]:
        return self.meshes.get(name)

    def list_mesh_names(self) -> list[str]:
        return sorted(self.meshes.keys())

    def find_mesh_name(self, mesh: "MeshDrawable") -> Optional[str]:
        for n, m in self.meshes.items():
            if m is mesh:
                return n
        return None

    # --------- Компоненты (на будущее) ---------
    def register_component(self, name: str, cls: type["Component"]):
        self.components[name] = cls

    def get_component(self, name: str) -> Optional[type["Component"]]:
        return self.components.get(name)

    def list_component_names(self) -> list[str]:
        return sorted(self.components.keys())
