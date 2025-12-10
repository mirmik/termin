# termin/visualization/resources.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов
    from termin.visualization.core.material import Material
    from termin.visualization.core.material_handle import MaterialKeeper
    from termin.visualization.core.mesh import MeshDrawable
    from termin.visualization.render.texture import Texture
    from termin.visualization.core.entity import Component
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm
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
        self.shaders: Dict[str, "ShaderMultyPhaseProgramm"] = {}
        self.meshes: Dict[str, "MeshDrawable"] = {}
        self.textures: Dict[str, "Texture"] = {}
        self.components: Dict[str, type["Component"]] = {}

        # MaterialKeeper'ы — владельцы материалов по имени
        self._material_keepers: Dict[str, "MaterialKeeper"] = {}

        # Отслеживание файлов
        self._file_watcher: "QFileSystemWatcher | None" = None
        self._project_path: str | None = None
        self._watched_dirs: Set[str] = set()
        self._file_to_materials: Dict[str, Set[str]] = {}  # path -> set of material names
        self._file_to_textures: Dict[str, Set[str]] = {}   # path -> set of texture names
        self._on_resource_reloaded: Callable[[str, str], None] | None = None  # (type, name)

    @classmethod
    def instance(cls) -> "ResourceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # --------- File Watching ---------

    def enable_file_watching(
        self,
        project_path: str | None = None,
        on_resource_reloaded: Callable[[str, str], None] | None = None,
    ) -> None:
        """
        Включает отслеживание изменений в директории проекта.

        Args:
            project_path: Путь к директории проекта для отслеживания.
            on_resource_reloaded: Callback вызываемый после перезагрузки ресурса.
                                  Аргументы: (resource_type, resource_name)
        """
        if self._file_watcher is not None:
            return

        from PyQt6.QtCore import QFileSystemWatcher

        self._file_watcher = QFileSystemWatcher()
        self._file_watcher.directoryChanged.connect(self._on_directory_changed)
        self._file_watcher.fileChanged.connect(self._on_file_changed)
        self._on_resource_reloaded = on_resource_reloaded

        if project_path:
            self.watch_project_directory(project_path)

    def watch_project_directory(self, project_path: str) -> None:
        """
        Добавляет директорию проекта в отслеживание.

        Рекурсивно добавляет все поддиректории.
        """
        if self._file_watcher is None:
            return

        import os
        from pathlib import Path

        self._project_path = project_path
        project = Path(project_path)

        if not project.exists():
            return

        # Добавляем корневую директорию и все поддиректории
        for root, dirs, files in os.walk(project_path):
            # Пропускаем скрытые и служебные директории
            dirs[:] = [d for d in dirs if not d.startswith(('.', '__'))]

            if root not in self._watched_dirs:
                self._file_watcher.addPath(root)
                self._watched_dirs.add(root)

            # Добавляем файлы ресурсов в отслеживание
            for filename in files:
                if filename.endswith(('.material', '.shader', '.png', '.jpg', '.jpeg')):
                    file_path = os.path.join(root, filename)
                    if file_path not in self._file_watcher.files():
                        self._file_watcher.addPath(file_path)

        # Строим маппинг файл -> материалы
        self._rebuild_file_mappings()

    def _rebuild_file_mappings(self) -> None:
        """Перестраивает маппинг файлов к ресурсам."""
        self._file_to_materials.clear()
        self._file_to_textures.clear()

        for name, mat in self.materials.items():
            # source_path материала
            if mat.source_path:
                if mat.source_path not in self._file_to_materials:
                    self._file_to_materials[mat.source_path] = set()
                self._file_to_materials[mat.source_path].add(name)

            # shader_path
            shader_path = getattr(mat, 'shader_path', None)
            if shader_path:
                if shader_path not in self._file_to_materials:
                    self._file_to_materials[shader_path] = set()
                self._file_to_materials[shader_path].add(name)

        for name, tex in self.textures.items():
            source_path = getattr(tex, 'source_path', None)
            if source_path:
                if source_path not in self._file_to_textures:
                    self._file_to_textures[source_path] = set()
                self._file_to_textures[source_path].add(name)

    def disable_file_watching(self) -> None:
        """Отключает отслеживание файлов."""
        if self._file_watcher is not None:
            self._file_watcher.directoryChanged.disconnect(self._on_directory_changed)
            self._file_watcher.fileChanged.disconnect(self._on_file_changed)
            self._file_watcher = None
        self._project_path = None
        self._watched_dirs.clear()
        self._file_to_materials.clear()
        self._file_to_textures.clear()
        self._on_resource_reloaded = None

    def _on_directory_changed(self, path: str) -> None:
        """Обработчик изменения директории (новые/удалённые файлы)."""
        import os

        if self._file_watcher is None:
            return

        # Проверяем новые файлы в директории
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)

            if os.path.isdir(file_path):
                # Новая поддиректория — добавляем в отслеживание
                if file_path not in self._watched_dirs and not filename.startswith(('.', '__')):
                    self._file_watcher.addPath(file_path)
                    self._watched_dirs.add(file_path)
            elif filename.endswith(('.material', '.shader')):
                # Новый файл ресурса — загружаем
                if file_path not in self._file_watcher.files():
                    self._file_watcher.addPath(file_path)

                name = os.path.splitext(filename)[0]
                try:
                    if filename.endswith('.material'):
                        if name not in self.materials:
                            self._load_material_file(file_path)
                            print(f"[ResourceManager] Loaded new material: {name}")
                            if self._on_resource_reloaded:
                                self._on_resource_reloaded("material", name)
                    elif filename.endswith('.shader'):
                        if name not in self.shaders:
                            self._load_shader_file(file_path)
                            print(f"[ResourceManager] Loaded new shader: {name}")
                            if self._on_resource_reloaded:
                                self._on_resource_reloaded("shader", name)
                except Exception as e:
                    print(f"[ResourceManager] Failed to load {file_path}: {e}")

    def _on_file_changed(self, path: str) -> None:
        """Обработчик изменения файла."""
        import os

        # QFileSystemWatcher может удалить путь после изменения (особенно на Linux)
        # Нужно переподписаться
        if self._file_watcher is not None and os.path.exists(path):
            if path not in self._file_watcher.files():
                self._file_watcher.addPath(path)

        # Перезагружаем материалы, связанные с этим файлом
        if path in self._file_to_materials:
            material_names = list(self._file_to_materials[path])
            for name in material_names:
                self._reload_material(name)
        elif path.endswith('.material'):
            name = os.path.splitext(os.path.basename(path))[0]
            if name in self.materials:
                self._reload_material(name)
        elif path.endswith('.shader'):
            name = os.path.splitext(os.path.basename(path))[0]
            if name in self.shaders:
                self._reload_shader(name, path)

        # Перезагружаем текстуры
        if path in self._file_to_textures:
            texture_names = list(self._file_to_textures[path])
            for name in texture_names:
                self._reload_texture(name)

    def _reload_material(self, name: str) -> None:
        """Перезагружает материал из файла через keeper."""
        keeper = self._material_keepers.get(name)
        if keeper is None or keeper.source_path is None:
            return

        source_path = keeper.source_path
        if not source_path.endswith('.material'):
            return

        try:
            from termin.visualization.core.material import Material

            new_mat = Material.load_from_material_file(source_path)

            # Обновляем через keeper (сохраняет идентичность объекта)
            keeper.update_material(new_mat)

            # Обновляем и в старом dict для совместимости
            if keeper.material is not None:
                self.materials[name] = keeper.material

            print(f"[ResourceManager] Reloaded material: {name}")

            if self._on_resource_reloaded:
                self._on_resource_reloaded("material", name)

        except Exception as e:
            print(f"[ResourceManager] Failed to reload material {name}: {e}")

    def _reload_shader(self, name: str, file_path: str) -> None:
        """Перезагружает шейдер из файла."""
        try:
            from termin.visualization.render.shader_parser import (
                parse_shader_text,
                ShaderMultyPhaseProgramm,
            )

            with open(file_path, "r", encoding="utf-8") as f:
                shader_text = f.read()

            tree = parse_shader_text(shader_text)
            program = ShaderMultyPhaseProgramm.from_tree(tree)
            self.register_shader(name, program, source_path=file_path)

            print(f"[ResourceManager] Reloaded shader: {name}")

            if self._on_resource_reloaded:
                self._on_resource_reloaded("shader", name)

        except Exception as e:
            print(f"[ResourceManager] Failed to reload shader {name}: {e}")

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
        - .py файлы с компонентами

        Args:
            project_path: Путь к корневой директории проекта

        Returns:
            Статистика: {"materials": int, "shaders": int, "components": int, "errors": int}
        """
        import os
        from pathlib import Path

        stats = {"materials": 0, "shaders": 0, "components": 0, "errors": 0}
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

        try:
            loaded_components = self.scan_components([str(project_path)])
            stats["components"] += len(loaded_components)
        except Exception as e:
            print(f"[ResourceManager] Failed to load components from {project_path}: {e}")
            stats["errors"] += 1

        return stats

    def _load_material_file(self, file_path: str) -> None:
        """Загружает .material файл и регистрирует его."""
        from pathlib import Path
        from termin.visualization.core.material import Material

        path = Path(file_path)
        name = path.stem

        # Проверяем keeper — если материал уже есть, не загружаем
        keeper = self.get_or_create_keeper(name)
        if keeper.has_material:
            return

        mat = Material.load_from_material_file(file_path)
        mat.name = name
        self.register_material(name, mat, source_path=file_path)

    def _load_shader_file(self, file_path: str) -> None:
        """Загружает .shader файл и регистрирует шейдер."""
        from pathlib import Path
        from termin.visualization.render.shader_parser import (
            parse_shader_text,
            ShaderMultyPhaseProgramm,
        )

        path = Path(file_path)
        name = path.stem

        # Проверяем, не загружен ли уже
        if name in self.shaders:
            return

        with open(file_path, "r", encoding="utf-8") as f:
            shader_text = f.read()

        tree = parse_shader_text(shader_text)
        program = ShaderMultyPhaseProgramm.from_tree(tree)
        self.register_shader(name, program, source_path=file_path)

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

        # Обновляем маппинг файлов если отслеживание включено
        if self._file_watcher is not None:
            self._rebuild_file_mappings()

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
