# termin/visualization/resources.py
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов
    from termin.visualization.core.material import Material
    from termin.visualization.core.material_handle import MaterialKeeper
    from termin.visualization.core.mesh import MeshDrawable
    from termin.visualization.render.texture import Texture
    from termin.visualization.core.entity import Component
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm


# Список стандартных компонентов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
_BUILTIN_COMPONENTS: List[Tuple[str, str]] = [
    # Рендеринг
    ("termin.visualization.render.components.mesh_renderer", "MeshRenderer"),
    ("termin.visualization.render.components.line_renderer", "LineRenderer"),
    ("termin.visualization.render.components.light_component", "LightComponent"),
    # Камера
    ("termin.visualization.core.camera", "CameraComponent"),
    ("termin.visualization.core.camera", "CameraController"),
    # Анимация
    ("termin.visualization.animation.player", "AnimationPlayer"),
    ("termin.visualization.components.rotator", "RotatorComponent"),
    # Физика
    ("termin.physics.physics_world_component", "PhysicsWorldComponent"),
    ("termin.physics.rigid_body_component", "RigidBodyComponent"),
    # Коллайдеры
    ("termin.colliders.collider_component", "ColliderComponent"),
]


class ResourceManager:
    """
    Глобальный менеджер ресурсов редактора.
    """

    _instance: "ResourceManager | None" = None

    def __init__(self):
        self.materials: Dict[str, "Material"] = {}
        self.shaders: Dict[str, "ShaderMultyPhaseProgramm"] = {}
        self.meshes: Dict[str, "MeshDrawable"] = {}
        self.textures: Dict[str, "Texture"] = {}
        self.components: Dict[str, type["Component"]] = {}

        # MaterialKeeper'ы — владельцы материалов по имени
        self._material_keepers: Dict[str, "MaterialKeeper"] = {}

    @classmethod
    def instance(cls) -> "ResourceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # --------- MaterialKeeper'ы ---------
    def get_or_create_keeper(self, name: str) -> "MaterialKeeper":
        """
        Получить или создать MaterialKeeper для имени.

        Всегда возвращает keeper — создаёт новый если не существует.
        """
        from termin.visualization.core.material_handle import MaterialKeeper

        if name not in self._material_keepers:
            self._material_keepers[name] = MaterialKeeper(name)
        return self._material_keepers[name]

    def get_keeper(self, name: str) -> Optional["MaterialKeeper"]:
        """Получить MaterialKeeper по имени или None."""
        return self._material_keepers.get(name)

    def list_keeper_names(self) -> list[str]:
        """Список имён всех keeper'ов."""
        return sorted(self._material_keepers.keys())

    # --------- Материалы ---------
    def register_material(self, name: str, mat: "Material", source_path: str | None = None):
        """
        Регистрирует материал через keeper.

        Args:
            name: Имя материала
            mat: Материал
            source_path: Путь к файлу-источнику
        """
        keeper = self.get_or_create_keeper(name)
        keeper.set_material(mat, source_path)

        # Для обратной совместимости сохраняем и в старый dict
        self.materials[name] = mat

    def get_material(self, name: str) -> Optional["Material"]:
        """Получить материал по имени."""
        keeper = self._material_keepers.get(name)
        if keeper is not None:
            return keeper.material
        return self.materials.get(name)

    def list_material_names(self) -> list[str]:
        # Объединяем имена из keeper'ов и старого dict
        names = set(self._material_keepers.keys()) | set(self.materials.keys())
        return sorted(names)

    def find_material_name(self, mat: "Material") -> Optional[str]:
        # Сначала ищем в keeper'ах
        for name, keeper in self._material_keepers.items():
            if keeper.material is mat:
                return name
        # Затем в старом dict
        for n, m in self.materials.items():
            if m is mat:
                return n
        return None

    # --------- Шейдеры ---------
    def register_shader(self, name: str, shader: "ShaderMultyPhaseProgramm", source_path: str | None = None):
        """Регистрирует шейдер программу."""
        self.shaders[name] = shader
        # Сохраняем путь к исходнику если есть
        if source_path:
            shader.source_path = source_path

    def get_shader(self, name: str) -> Optional["ShaderMultyPhaseProgramm"]:
        return self.shaders.get(name)

    def list_shader_names(self) -> list[str]:
        return sorted(self.shaders.keys())

    def register_default_shader(self) -> None:
        """Регистрирует встроенный DefaultShader."""
        if "DefaultShader" in self.shaders:
            return

        from termin.visualization.render.materials.default_material import (
            DEFAULT_VERT,
            DEFAULT_FRAG,
        )
        from termin.visualization.render.shader_parser import (
            ShaderMultyPhaseProgramm,
            ShaderPhase,
            ShasderStage,
            MaterialProperty,
        )

        # Создаём ShaderMultyPhaseProgramm для DefaultShader
        vertex_stage = ShasderStage("vertex", DEFAULT_VERT)
        fragment_stage = ShasderStage("fragment", DEFAULT_FRAG)

        phase = ShaderPhase(
            phase_mark="opaque",
            priority=0,
            gl_depth_mask=True,
            gl_depth_test=True,
            gl_blend=False,
            gl_cull=True,
            stages={"vertex": vertex_stage, "fragment": fragment_stage},
            uniforms=[
                MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
                MaterialProperty("u_ambient", "Float", 0.1, 0.0, 1.0),
                MaterialProperty("u_shininess", "Float", 32.0, 1.0, 128.0),
            ],
        )

        program = ShaderMultyPhaseProgramm(program="DefaultShader", phases=[phase])
        self.shaders["DefaultShader"] = program

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

    # --------- Компоненты ---------
    def register_component(self, name: str, cls: type["Component"]):
        self.components[name] = cls

    def get_component(self, name: str) -> Optional[type["Component"]]:
        return self.components.get(name)

    def list_component_names(self) -> list[str]:
        return sorted(self.components.keys())

    def register_builtin_components(self) -> List[str]:
        """
        Регистрирует все встроенные компоненты из _BUILTIN_COMPONENTS.

        Вызывается при инициализации редактора, чтобы гарантировать
        доступность стандартных компонентов независимо от порядка импортов.

        Returns:
            Список имён успешно зарегистрированных компонентов.
        """
        import importlib

        registered = []

        for module_name, class_name in _BUILTIN_COMPONENTS:
            if class_name in self.components:
                # Уже зарегистрирован (например, через __init_subclass__)
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.components[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                print(f"Warning: Failed to register component {class_name} from {module_name}: {e}")

        return registered

    def scan_components(self, paths: list[str]) -> list[str]:
        """
        Сканирует директории/модули/файлы и загружает все Component подклассы.

        Args:
            paths: Список путей к директориям, .py файлам или имён модулей.
                   Примеры:
                   - "termin.visualization.components" (модуль)
                   - "/home/user/my_components" (директория)
                   - "/home/user/rotator.py" (файл)

        Returns:
            Список имён загруженных компонентов.
        """
        import importlib
        import importlib.util
        import os
        import sys

        loaded = []

        for path in paths:
            if os.path.isfile(path) and path.endswith(".py"):
                # Загружаем отдельный .py файл
                loaded.extend(self._scan_file(path))
            elif os.path.isdir(path):
                # Сканируем директорию
                loaded.extend(self._scan_directory(path))
            else:
                # Пробуем как имя модуля
                loaded.extend(self._scan_module(path))

        return loaded

    def _scan_file(self, filepath: str) -> list[str]:
        """Загружает компоненты из одного .py файла."""
        import importlib.util
        import os
        import sys

        before = set(self.components.keys())

        filename = os.path.basename(filepath)
        module_name = f"_dynamic_components_.{os.path.splitext(filename)[0]}_{id(filepath)}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                return []

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        except Exception as e:
            print(f"Warning: Failed to load {filepath}: {e}")
            return []

        after = set(self.components.keys())
        return list(after - before)

    def _scan_module(self, module_name: str) -> list[str]:
        """Загружает модуль и все его подмодули."""
        import importlib
        import pkgutil

        loaded = []
        before = set(self.components.keys())

        try:
            module = importlib.import_module(module_name)

            # Если это пакет, сканируем подмодули
            if hasattr(module, "__path__"):
                for importer, name, is_pkg in pkgutil.walk_packages(
                    module.__path__, prefix=module_name + "."
                ):
                    try:
                        importlib.import_module(name)
                    except Exception as e:
                        print(f"Warning: Failed to import {name}: {e}")

            after = set(self.components.keys())
            loaded = list(after - before)

        except Exception as e:
            print(f"Warning: Failed to import module {module_name}: {e}")

        return loaded

    def _scan_directory(self, directory: str) -> list[str]:
        """Сканирует директорию и загружает все .py файлы как модули."""
        import importlib.util
        import os
        import sys

        loaded = []
        before = set(self.components.keys())

        for root, dirs, files in os.walk(directory):
            # Пропускаем __pycache__ и скрытые директории
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]

            for filename in files:
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue

                filepath = os.path.join(root, filename)
                module_name = os.path.splitext(filename)[0]

                # Создаём уникальное имя модуля
                rel_path = os.path.relpath(filepath, directory)
                unique_name = f"_dynamic_components_.{rel_path.replace(os.sep, '.')[:-3]}"

                try:
                    spec = importlib.util.spec_from_file_location(unique_name, filepath)
                    if spec is None or spec.loader is None:
                        continue

                    module = importlib.util.module_from_spec(spec)
                    sys.modules[unique_name] = module
                    spec.loader.exec_module(module)

                except Exception as e:
                    print(f"Warning: Failed to load {filepath}: {e}")

        after = set(self.components.keys())
        loaded = list(after - before)

        return loaded

    # --------- Сериализация ---------

    def serialize(self) -> dict:
        """
        Сериализует все ресурсы ResourceManager.
        """
        return {
            "materials": {name: mat.serialize() for name, mat in self.materials.items()},
            "meshes": {name: mesh.serialize() for name, mesh in self.meshes.items()},
            "textures": {name: self._serialize_texture(tex) for name, tex in self.textures.items()},
        }

    def _serialize_texture(self, tex: "Texture") -> dict:
        """Сериализует текстуру."""
        source_path = tex.source_path if tex.source_path else None
        if source_path:
            return {"type": "file", "source_path": source_path}
        return {"type": "unknown"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "ResourceManager":
        """
        Восстанавливает ResourceManager из сериализованных данных.
        """
        from termin.visualization.core.material import Material
        from termin.visualization.core.mesh import MeshDrawable

        rm = cls()

        # Материалы
        for name, mat_data in data.get("materials", {}).items():
            mat = Material.deserialize(mat_data)
            mat.name = name
            rm.register_material(name, mat)

        # Меши
        for name, mesh_data in data.get("meshes", {}).items():
            drawable = MeshDrawable.deserialize(mesh_data, context)
            if drawable is not None:
                rm.register_mesh(name, drawable)

        # Текстуры - TODO: добавить Texture.deserialize()
        # for name, tex_data in data.get("textures", {}).items():
        #     tex = Texture.deserialize(tex_data, context)
        #     if tex is not None:
        #         rm.register_texture(name, tex)

        return rm
