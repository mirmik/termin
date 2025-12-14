# termin/visualization/resources.py
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # только для типов, чтобы не ловить циклы импортов
    from termin.visualization.core.material import Material
    from termin.visualization.core.material_handle import MaterialKeeper
    from termin.visualization.core.mesh import MeshDrawable
    from termin.visualization.core.mesh_handle import MeshKeeper
    from termin.visualization.core.texture_handle import TextureKeeper
    from termin.visualization.render.texture import Texture
    from termin.visualization.core.entity import Component
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm
    from termin.voxels.grid import VoxelGrid


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
    # Воксели
    ("termin.voxels.voxelizer_component", "VoxelizerComponent"),
    ("termin.voxels.display_component", "VoxelDisplayComponent"),
]

# Список встроенных FramePass'ов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
_BUILTIN_FRAME_PASSES: List[Tuple[str, str]] = [
    # Основные пассы
    ("termin.visualization.render.framegraph.passes.color", "ColorPass"),
    ("termin.visualization.render.framegraph.passes.skybox", "SkyBoxPass"),
    ("termin.visualization.render.framegraph.passes.depth", "DepthPass"),
    ("termin.visualization.render.framegraph.passes.shadow", "ShadowPass"),
    ("termin.visualization.render.framegraph.passes.canvas", "CanvasPass"),
    ("termin.visualization.render.framegraph.passes.present", "PresentToScreenPass"),
    ("termin.visualization.render.framegraph.passes.present", "BlitPass"),
    # ID/Picking
    ("termin.visualization.render.framegraph.passes.id_pass", "IdPass"),
    ("termin.visualization.render.framegraph.passes.gizmo", "GizmoPass"),
    # Post-processing
    ("termin.visualization.render.postprocess", "PostProcessPass"),
    # Debug
    ("termin.visualization.render.framegraph.passes.frame_debugger", "FrameDebuggerPass"),
]

# Список встроенных PostEffect'ов для предрегистрации.
# Формат: (имя_модуля, имя_класса)
_BUILTIN_POST_EFFECTS: List[Tuple[str, str]] = [
    ("termin.visualization.render.posteffects.blur", "GaussianBlurPass"),
    ("termin.visualization.render.posteffects.highlight", "HighlightEffect"),
    ("termin.visualization.render.posteffects.fog", "FogEffect"),
    ("termin.visualization.render.posteffects.gray", "GrayscaleEffect"),
]


class ResourceManager:
    """
    Глобальный менеджер ресурсов редактора.
    """

    _instance: "ResourceManager | None" = None
    _creating_singleton: bool = False

    def __init__(self):
        if not ResourceManager._creating_singleton:
            raise RuntimeError(
                "ResourceManager is a singleton. Use ResourceManager.instance() instead of ResourceManager()."
            )

        self.materials: Dict[str, "Material"] = {}
        self.shaders: Dict[str, "ShaderMultyPhaseProgramm"] = {}
        self.meshes: Dict[str, "MeshDrawable"] = {}
        self.textures: Dict[str, "Texture"] = {}
        self.voxel_grids: Dict[str, "VoxelGrid"] = {}  # VoxelGrid instances by name
        self.components: Dict[str, type["Component"]] = {}
        self.frame_passes: Dict[str, type] = {}  # FramePass classes by name
        self.post_effects: Dict[str, type] = {}  # PostEffect classes by name
        self.pipelines: Dict[str, "RenderPipeline"] = {}  # RenderPipeline instances by name

        # MaterialKeeper'ы — владельцы материалов по имени
        self._material_keepers: Dict[str, "MaterialKeeper"] = {}

        # MeshKeeper'ы — владельцы мешей по имени
        self._mesh_keepers: Dict[str, "MeshKeeper"] = {}

        # TextureKeeper'ы — владельцы текстур по имени
        self._texture_keepers: Dict[str, "TextureKeeper"] = {}

        # VoxelGridKeeper'ы — владельцы воксельных сеток по имени
        self._voxel_grid_keepers: Dict[str, "VoxelGridKeeper"] = {}

    @classmethod
    def instance(cls) -> "ResourceManager":
        if cls._instance is None:
            cls._creating_singleton = True
            try:
                cls._instance = cls()
            finally:
                cls._creating_singleton = False
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
                MaterialProperty("u_albedo_texture", "Texture", None),
                MaterialProperty("u_ambient", "Float", 0.1, 0.0, 1.0),
                MaterialProperty("u_shininess", "Float", 32.0, 1.0, 128.0),
            ],
        )

        program = ShaderMultyPhaseProgramm(program="DefaultShader", phases=[phase])
        self.shaders["DefaultShader"] = program

    def register_builtin_materials(self) -> None:
        """Регистрирует встроенные материалы."""
        if "DefaultMaterial" in self.materials:
            return

        from termin.visualization.core.material import Material
        from termin.visualization.render.texture import get_white_texture

        # Убедимся что DefaultShader зарегистрирован
        self.register_default_shader()

        shader = self.shaders.get("DefaultShader")
        if shader is None:
            return

        # Создаём DefaultMaterial с циановым цветом и белой текстурой
        white_tex = get_white_texture()
        mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
        mat.name = "DefaultMaterial"
        mat.color = (0.3, 0.85, 0.9, 1.0)  # Умеренно-яркий циан
        self.register_material("DefaultMaterial", mat)

    def register_builtin_meshes(self) -> List[str]:
        """
        Регистрирует встроенные примитивные меши.

        Returns:
            Список имён зарегистрированных мешей.
        """
        from termin.visualization.core.mesh import MeshDrawable
        from termin.mesh.mesh import (
            TexturedCubeMesh,
            UVSphereMesh,
            PlaneMesh,
            CylinderMesh,
        )

        registered = []

        # Куб с корректными UV (текстура на каждой грани)
        if "Cube" not in self.meshes:
            cube = MeshDrawable(TexturedCubeMesh(size=1.0))
            self.register_mesh("Cube", cube)
            registered.append("Cube")

        # Сфера
        if "Sphere" not in self.meshes:
            sphere = MeshDrawable(UVSphereMesh(radius=0.5, n_meridians=32, n_parallels=16))
            self.register_mesh("Sphere", sphere)
            registered.append("Sphere")

        # Плоскость
        if "Plane" not in self.meshes:
            plane = MeshDrawable(PlaneMesh(width=1.0, depth=1.0))
            self.register_mesh("Plane", plane)
            registered.append("Plane")

        # Цилиндр
        if "Cylinder" not in self.meshes:
            cylinder = MeshDrawable(CylinderMesh(radius=0.5, height=1.0))
            self.register_mesh("Cylinder", cylinder)
            registered.append("Cylinder")

        return registered

    # --------- MeshKeeper'ы ---------
    def get_or_create_mesh_keeper(self, name: str) -> "MeshKeeper":
        """
        Получить или создать MeshKeeper по имени.

        Используется MeshHandle для получения keeper'а.
        """
        from termin.visualization.core.mesh_handle import MeshKeeper

        if name not in self._mesh_keepers:
            self._mesh_keepers[name] = MeshKeeper(name)
        return self._mesh_keepers[name]

    def get_mesh_keeper(self, name: str) -> Optional["MeshKeeper"]:
        """Получить MeshKeeper по имени или None."""
        return self._mesh_keepers.get(name)

    # --------- Меши ---------
    def register_mesh(self, name: str, mesh: "MeshDrawable", source_path: str | None = None):
        """
        Регистрирует меш через keeper.

        Args:
            name: Имя меша
            mesh: Меш
            source_path: Путь к файлу-источнику
        """
        # Устанавливаем имя на меш (чтобы setter в инспекторе мог его использовать)
        mesh.name = name

        keeper = self.get_or_create_mesh_keeper(name)
        keeper.set_mesh(mesh, source_path)

        # Для обратной совместимости сохраняем и в старый dict
        self.meshes[name] = mesh

    def get_mesh(self, name: str) -> Optional["MeshDrawable"]:
        """Получить меш по имени."""
        keeper = self._mesh_keepers.get(name)
        if keeper is not None:
            return keeper.mesh
        return self.meshes.get(name)

    def list_mesh_names(self) -> list[str]:
        return sorted(self.meshes.keys())

    def find_mesh_name(self, mesh: "MeshDrawable") -> Optional[str]:
        for n, m in self.meshes.items():
            if m is mesh:
                return n
        return None

    def unregister_mesh(self, name: str) -> None:
        """Удаляет меш и очищает keeper."""
        keeper = self._mesh_keepers.get(name)
        if keeper is not None:
            keeper.clear()
            del self._mesh_keepers[name]
        if name in self.meshes:
            del self.meshes[name]

    # --------- VoxelGridKeeper'ы ---------
    def get_or_create_voxel_grid_keeper(self, name: str) -> "VoxelGridKeeper":
        """
        Получить или создать VoxelGridKeeper по имени.

        Используется VoxelGridHandle для получения keeper'а.
        """
        from termin.visualization.core.voxel_grid_handle import VoxelGridKeeper

        if name not in self._voxel_grid_keepers:
            self._voxel_grid_keepers[name] = VoxelGridKeeper(name)
        return self._voxel_grid_keepers[name]

    def get_voxel_grid_keeper(self, name: str) -> Optional["VoxelGridKeeper"]:
        """Получить VoxelGridKeeper по имени или None."""
        return self._voxel_grid_keepers.get(name)

    # --------- Воксельные сетки ---------
    def register_voxel_grid(self, name: str, grid: "VoxelGrid", source_path: str | None = None) -> None:
        """
        Регистрирует воксельную сетку через keeper.

        Args:
            name: Имя сетки
            grid: VoxelGrid
            source_path: Путь к файлу-источнику
        """
        grid.name = name
        keeper = self.get_or_create_voxel_grid_keeper(name)
        keeper.set_grid(grid, source_path)

        # Для обратной совместимости сохраняем и в старый dict
        self.voxel_grids[name] = grid

    def get_voxel_grid(self, name: str) -> Optional["VoxelGrid"]:
        """Получить воксельную сетку по имени."""
        keeper = self._voxel_grid_keepers.get(name)
        if keeper is not None:
            return keeper.grid
        return self.voxel_grids.get(name)

    def list_voxel_grid_names(self) -> list[str]:
        """Список имён всех воксельных сеток."""
        return sorted(self.voxel_grids.keys())

    def find_voxel_grid_name(self, grid: "VoxelGrid") -> Optional[str]:
        """Найти имя воксельной сетки."""
        for n, g in self.voxel_grids.items():
            if g is grid:
                return n
        return None

    def unregister_voxel_grid(self, name: str) -> None:
        """Удаляет воксельную сетку."""
        keeper = self._voxel_grid_keepers.get(name)
        if keeper is not None:
            keeper.clear()
            del self._voxel_grid_keepers[name]
        if name in self.voxel_grids:
            del self.voxel_grids[name]

    # --------- TextureKeeper'ы ---------
    def get_or_create_texture_keeper(self, name: str) -> "TextureKeeper":
        """
        Получить или создать TextureKeeper по имени.

        Используется TextureHandle для получения keeper'а.
        """
        from termin.visualization.core.texture_handle import TextureKeeper

        if name not in self._texture_keepers:
            self._texture_keepers[name] = TextureKeeper(name)
        return self._texture_keepers[name]

    def get_texture_keeper(self, name: str) -> Optional["TextureKeeper"]:
        """Получить TextureKeeper по имени или None."""
        return self._texture_keepers.get(name)

    # --------- Текстуры ---------
    def register_texture(self, name: str, texture: "Texture", source_path: str | None = None):
        """
        Регистрирует текстуру через keeper.

        Args:
            name: Имя текстуры
            texture: Текстура
            source_path: Путь к файлу-источнику
        """
        if source_path and texture.source_path is None:
            texture.source_path = source_path

        keeper = self.get_or_create_texture_keeper(name)
        keeper.set_texture(texture, source_path)

        # Для обратной совместимости сохраняем и в старый dict
        self.textures[name] = texture

    def get_texture(self, name: str) -> Optional["Texture"]:
        """Получить текстуру по имени."""
        keeper = self._texture_keepers.get(name)
        if keeper is not None:
            return keeper.texture
        return self.textures.get(name)

    def list_texture_names(self) -> list[str]:
        """Список имён всех текстур."""
        names = set(self._texture_keepers.keys()) | set(self.textures.keys())
        return sorted(names)

    def find_texture_name(self, texture: "Texture") -> Optional[str]:
        """Найти имя зарегистрированной текстуры."""
        for name, keeper in self._texture_keepers.items():
            if keeper.texture is texture:
                return name
        for n, t in self.textures.items():
            if t is texture:
                return n
        return None

    def unregister_texture(self, name: str) -> None:
        """Удаляет текстуру и очищает keeper."""
        keeper = self._texture_keepers.get(name)
        if keeper is not None:
            keeper.clear()
            del self._texture_keepers[name]
        if name in self.textures:
            del self.textures[name]

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

    # --------- FramePass'ы ---------
    def register_frame_pass(self, name: str, cls: type):
        """Регистрирует класс FramePass по имени."""
        self.frame_passes[name] = cls

    def get_frame_pass(self, name: str) -> Optional[type]:
        """Получить класс FramePass по имени."""
        return self.frame_passes.get(name)

    def list_frame_pass_names(self) -> list[str]:
        """Список имён всех зарегистрированных FramePass'ов."""
        return sorted(self.frame_passes.keys())

    def register_builtin_frame_passes(self) -> List[str]:
        """
        Регистрирует все встроенные FramePass'ы из _BUILTIN_FRAME_PASSES.

        Returns:
            Список имён успешно зарегистрированных FramePass'ов.
        """
        import importlib

        registered = []

        for module_name, class_name in _BUILTIN_FRAME_PASSES:
            if class_name in self.frame_passes:
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.frame_passes[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                print(f"Warning: Failed to register frame pass {class_name} from {module_name}: {e}")

        return registered

    def scan_frame_passes(self, paths: list[str]) -> list[str]:
        """
        Сканирует директории/модули/файлы и загружает все FramePass подклассы.

        Args:
            paths: Список путей к директориям, .py файлам или имён модулей.

        Returns:
            Список имён загруженных FramePass'ов.
        """
        import importlib
        import importlib.util
        import os
        import sys

        loaded = []

        for path in paths:
            if os.path.isfile(path) and path.endswith(".py"):
                loaded.extend(self._scan_file_for_frame_passes(path))
            elif os.path.isdir(path):
                loaded.extend(self._scan_directory_for_frame_passes(path))
            else:
                loaded.extend(self._scan_module_for_frame_passes(path))

        return loaded

    def _scan_file_for_frame_passes(self, filepath: str) -> list[str]:
        """Загружает FramePass'ы из одного .py файла."""
        import importlib.util
        import os
        import sys

        before = set(self.frame_passes.keys())

        filename = os.path.basename(filepath)
        module_name = f"_dynamic_frame_passes_.{os.path.splitext(filename)[0]}_{id(filepath)}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                return []

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Ищем классы, наследующиеся от FramePass
            from termin.visualization.render.framegraph.core import FramePass

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, FramePass)
                    and attr is not FramePass
                    and attr_name not in self.frame_passes
                ):
                    self.frame_passes[attr_name] = attr

        except Exception as e:
            print(f"Warning: Failed to load frame passes from {filepath}: {e}")
            return []

        after = set(self.frame_passes.keys())
        return list(after - before)

    def _scan_directory_for_frame_passes(self, directory: str) -> list[str]:
        """Сканирует директорию и загружает все FramePass'ы."""
        import os

        loaded = []

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]

            for filename in files:
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue

                filepath = os.path.join(root, filename)
                loaded.extend(self._scan_file_for_frame_passes(filepath))

        return loaded

    def _scan_module_for_frame_passes(self, module_name: str) -> list[str]:
        """Загружает FramePass'ы из модуля."""
        import importlib
        import pkgutil

        loaded = []
        before = set(self.frame_passes.keys())

        try:
            module = importlib.import_module(module_name)

            from termin.visualization.render.framegraph.core import FramePass

            # Ищем классы в самом модуле
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, FramePass)
                    and attr is not FramePass
                    and attr_name not in self.frame_passes
                ):
                    self.frame_passes[attr_name] = attr

            # Если это пакет, сканируем подмодули
            if hasattr(module, "__path__"):
                for importer, name, is_pkg in pkgutil.walk_packages(
                    module.__path__, prefix=module_name + "."
                ):
                    try:
                        submodule = importlib.import_module(name)
                        for attr_name in dir(submodule):
                            attr = getattr(submodule, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, FramePass)
                                and attr is not FramePass
                                and attr_name not in self.frame_passes
                            ):
                                self.frame_passes[attr_name] = attr
                    except Exception as e:
                        print(f"Warning: Failed to import {name}: {e}")

            after = set(self.frame_passes.keys())
            loaded = list(after - before)

        except Exception as e:
            print(f"Warning: Failed to import module {module_name}: {e}")

        return loaded

    # --------- PostEffect'ы ---------
    def register_post_effect(self, name: str, cls: type):
        """Регистрирует класс PostEffect по имени."""
        self.post_effects[name] = cls

    def get_post_effect(self, name: str) -> Optional[type]:
        """Получить класс PostEffect по имени."""
        return self.post_effects.get(name)

    def list_post_effect_names(self) -> list[str]:
        """Список имён всех зарегистрированных PostEffect'ов."""
        return sorted(self.post_effects.keys())

    def register_builtin_post_effects(self) -> List[str]:
        """
        Регистрирует все встроенные PostEffect'ы из _BUILTIN_POST_EFFECTS.

        Returns:
            Список имён успешно зарегистрированных PostEffect'ов.
        """
        import importlib

        registered = []

        for module_name, class_name in _BUILTIN_POST_EFFECTS:
            if class_name in self.post_effects:
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.post_effects[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                print(f"Warning: Failed to register post effect {class_name} from {module_name}: {e}")

        return registered

    # --------- Pipelines ---------
    def register_pipeline(self, name: str, pipeline: "RenderPipeline"):
        """Регистрирует RenderPipeline по имени."""
        self.pipelines[name] = pipeline

    def get_pipeline(self, name: str) -> Optional["RenderPipeline"]:
        """Получить RenderPipeline по имени."""
        return self.pipelines.get(name)

    def list_pipeline_names(self) -> list[str]:
        """Список имён всех зарегистрированных пайплайнов."""
        return sorted(self.pipelines.keys())

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
        Восстанавливает ресурсы из сериализованных данных в синглтон.

        Добавляет десериализованные ресурсы к существующему синглтону,
        не перезаписывая уже загруженные ресурсы (например, из файлов проекта).
        """
        from termin.visualization.core.material import Material
        from termin.visualization.core.mesh import MeshDrawable

        rm = cls.instance()

        # Материалы - добавляем только если ещё нет
        for name, mat_data in data.get("materials", {}).items():
            if name not in rm.materials:
                mat = Material.deserialize(mat_data)
                mat.name = name
                rm.register_material(name, mat)

        # Меши - добавляем только если ещё нет
        for name, mesh_data in data.get("meshes", {}).items():
            if name not in rm.meshes:
                drawable = MeshDrawable.deserialize(mesh_data, context)
                if drawable is not None:
                    rm.register_mesh(name, drawable)

        # Текстуры - TODO: добавить Texture.deserialize()
        # for name, tex_data in data.get("textures", {}).items():
        #     if name not in rm.textures:
        #         tex = Texture.deserialize(tex_data, context)
        #         if tex is not None:
        #             rm.register_texture(name, tex)

        return rm
