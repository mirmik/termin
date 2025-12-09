# termin/visualization/resources.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов
    from termin.visualization.core.material import Material
    from termin.visualization.core.mesh import MeshDrawable
    from termin.visualization.render.texture import Texture
    from termin.visualization.core.entity import Component
    from PyQt6.QtCore import QFileSystemWatcher


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
        self.meshes: Dict[str, "MeshDrawable"] = {}
        self.textures: Dict[str, "Texture"] = {}
        self.components: Dict[str, type["Component"]] = {}

        # Отслеживание файлов
        self._file_watcher: "QFileSystemWatcher | None" = None
        self._file_to_materials: Dict[str, Set[str]] = {}  # path -> set of material names
        self._file_to_textures: Dict[str, Set[str]] = {}   # path -> set of texture names
        self._on_resource_reloaded: Callable[[str, str], None] | None = None  # (type, name)

    @classmethod
    def instance(cls) -> "ResourceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # --------- File Watching ---------

    def enable_file_watching(self, on_resource_reloaded: Callable[[str, str], None] | None = None) -> None:
        """
        Включает отслеживание изменений в файлах ресурсов.

        Args:
            on_resource_reloaded: Callback вызываемый после перезагрузки ресурса.
                                  Аргументы: (resource_type, resource_name)
        """
        if self._file_watcher is not None:
            return

        from PyQt6.QtCore import QFileSystemWatcher

        self._file_watcher = QFileSystemWatcher()
        self._file_watcher.fileChanged.connect(self._on_file_changed)
        self._on_resource_reloaded = on_resource_reloaded

        # Добавляем уже зарегистрированные файлы
        for name, mat in self.materials.items():
            self._watch_material(name, mat)

        for name, tex in self.textures.items():
            self._watch_texture(name, tex)

    def disable_file_watching(self) -> None:
        """Отключает отслеживание файлов."""
        if self._file_watcher is not None:
            self._file_watcher.fileChanged.disconnect(self._on_file_changed)
            self._file_watcher = None
        self._file_to_materials.clear()
        self._file_to_textures.clear()
        self._on_resource_reloaded = None

    def _watch_material(self, name: str, mat: "Material") -> None:
        """Добавляет файлы материала в отслеживание."""
        if self._file_watcher is None:
            return

        paths_to_watch: List[str] = []

        # source_path материала (.material файл)
        if mat.source_path:
            paths_to_watch.append(mat.source_path)

        # shader_path (.shader файл)
        shader_path = getattr(mat, 'shader_path', None)
        if shader_path:
            paths_to_watch.append(shader_path)

        for path in paths_to_watch:
            if path not in self._file_to_materials:
                self._file_to_materials[path] = set()
                self._file_watcher.addPath(path)
            self._file_to_materials[path].add(name)

    def _unwatch_material(self, name: str) -> None:
        """Удаляет материал из отслеживания."""
        if self._file_watcher is None:
            return

        paths_to_remove = []
        for path, names in self._file_to_materials.items():
            if name in names:
                names.discard(name)
                if not names:
                    paths_to_remove.append(path)

        for path in paths_to_remove:
            del self._file_to_materials[path]
            self._file_watcher.removePath(path)

    def _watch_texture(self, name: str, tex: "Texture") -> None:
        """Добавляет файл текстуры в отслеживание."""
        if self._file_watcher is None:
            return

        source_path = getattr(tex, 'source_path', None)
        if not source_path:
            return

        if source_path not in self._file_to_textures:
            self._file_to_textures[source_path] = set()
            self._file_watcher.addPath(source_path)
        self._file_to_textures[source_path].add(name)

    def _on_file_changed(self, path: str) -> None:
        """Обработчик изменения файла."""
        import os

        # QFileSystemWatcher может удалить путь после изменения (особенно на Linux)
        # Нужно переподписаться
        if self._file_watcher is not None and os.path.exists(path):
            if path not in self._file_watcher.files():
                self._file_watcher.addPath(path)

        # Перезагружаем материалы
        if path in self._file_to_materials:
            material_names = list(self._file_to_materials[path])
            for name in material_names:
                self._reload_material(name)

        # Перезагружаем текстуры
        if path in self._file_to_textures:
            texture_names = list(self._file_to_textures[path])
            for name in texture_names:
                self._reload_texture(name)

    def _reload_material(self, name: str) -> None:
        """Перезагружает материал из файла."""
        mat = self.materials.get(name)
        if mat is None:
            return

        source_path = mat.source_path
        if not source_path:
            return

        try:
            from termin.visualization.core.material import Material

            if source_path.endswith('.material'):
                new_mat = Material.load_from_material_file(source_path)
            elif source_path.endswith('.shader'):
                from termin.visualization.render.shader_parser import (
                    parse_shader_text,
                    ShaderMultyPhaseProgramm,
                )
                with open(source_path, "r", encoding="utf-8") as f:
                    shader_text = f.read()
                tree = parse_shader_text(shader_text)
                program = ShaderMultyPhaseProgramm.from_tree(tree)
                new_mat = Material.from_parsed(program, source_path=source_path)
            else:
                return

            # Обновляем материал in-place
            new_mat.name = name
            self.materials[name] = new_mat

            # Переподписываемся на файлы нового материала
            self._unwatch_material(name)
            self._watch_material(name, new_mat)

            print(f"[ResourceManager] Reloaded material: {name}")

            if self._on_resource_reloaded:
                self._on_resource_reloaded("material", name)

        except Exception as e:
            print(f"[ResourceManager] Failed to reload material {name}: {e}")

    def _reload_texture(self, name: str) -> None:
        """Перезагружает текстуру из файла."""
        tex = self.textures.get(name)
        if tex is None:
            return

        source_path = getattr(tex, 'source_path', None)
        if not source_path:
            return

        try:
            # Инвалидируем текстуру - она перезагрузится при следующем использовании
            tex.invalidate()

            print(f"[ResourceManager] Reloaded texture: {name}")

            if self._on_resource_reloaded:
                self._on_resource_reloaded("texture", name)

        except Exception as e:
            print(f"[ResourceManager] Failed to reload texture {name}: {e}")

    def scan_project_resources(self, project_path: str) -> dict:
        """
        Сканирует директорию проекта и загружает все ресурсы.

        Ищет и загружает:
        - .material файлы
        - .shader файлы (создаёт материалы из них)

        Args:
            project_path: Путь к корневой директории проекта

        Returns:
            Статистика: {"materials": int, "shaders": int, "errors": int}
        """
        import os
        from pathlib import Path

        stats = {"materials": 0, "shaders": 0, "errors": 0}
        project_path = Path(project_path)

        if not project_path.exists():
            return stats

        # Находим все .material и .shader файлы
        material_files = list(project_path.rglob("*.material"))
        shader_files = list(project_path.rglob("*.shader"))

        # Загружаем материалы
        for mat_path in material_files:
            try:
                self._load_material_file(str(mat_path))
                stats["materials"] += 1
            except Exception as e:
                print(f"[ResourceManager] Failed to load material {mat_path}: {e}")
                stats["errors"] += 1

        # Загружаем шейдеры как материалы
        for shader_path in shader_files:
            try:
                self._load_shader_file(str(shader_path))
                stats["shaders"] += 1
            except Exception as e:
                print(f"[ResourceManager] Failed to load shader {shader_path}: {e}")
                stats["errors"] += 1

        return stats

    def _load_material_file(self, file_path: str) -> None:
        """Загружает .material файл и регистрирует его."""
        from pathlib import Path
        from termin.visualization.core.material import Material

        path = Path(file_path)
        name = path.stem

        # Проверяем, не загружен ли уже
        if name in self.materials:
            return

        mat = Material.load_from_material_file(file_path)
        mat.name = name
        self.register_material(name, mat)

    def _load_shader_file(self, file_path: str) -> None:
        """Загружает .shader файл и создаёт материал из него."""
        from pathlib import Path
        from termin.visualization.core.material import Material
        from termin.visualization.render.shader_parser import (
            parse_shader_text,
            ShaderMultyPhaseProgramm,
        )

        path = Path(file_path)
        name = path.stem

        # Проверяем, не загружен ли уже
        if name in self.materials:
            return

        with open(file_path, "r", encoding="utf-8") as f:
            shader_text = f.read()

        tree = parse_shader_text(shader_text)
        program = ShaderMultyPhaseProgramm.from_tree(tree)
        mat = Material.from_parsed(program, source_path=file_path)
        mat.name = name
        mat.shader_path = file_path
        self.register_material(name, mat)

    # --------- Материалы ---------
    def register_material(self, name: str, mat: "Material"):
        self.materials[name] = mat
        self._watch_material(name, mat)

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
