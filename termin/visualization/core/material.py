"""Material keeps shader reference and static uniform parameters."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING, Union

import numpy as np

from termin.visualization.render.shader import ShaderProgram
from termin.visualization.core.texture_handle import TextureHandle
from termin.visualization.platform.backends.base import GraphicsBackend

if TYPE_CHECKING:
    from termin.visualization.render.renderpass import RenderState
    from termin.visualization.render.shader_parser import (
        ShaderPhase as ParsedShaderPhase,
        ShaderMultyPhaseProgramm,
        UniformProperty,
    )


def _rgba(vec: Iterable[float]) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float32)
    if arr.shape != (4,):
        raise ValueError("Color must be an RGBA quadruplet.")
    return arr


class MaterialPhase:
    """
    Фаза материала: шейдер, состояние рендера и статические параметры.
    """

    def __init__(
        self,
        shader_programm: ShaderProgram,
        render_state: Optional["RenderState"] = None,
        phase_mark: str = "opaque",
        priority: int = 0,
        color: np.ndarray | None = None,
        textures: Dict[str, TextureHandle] | None = None,
        uniforms: Dict[str, Any] | None = None,
    ):
        if render_state is None:
            from termin.visualization.render.renderpass import RenderState

            render_state = RenderState()
        self.shader_programm = shader_programm
        self.render_state = render_state
        self.phase_mark = phase_mark
        self.priority = int(priority)
        self.color = _rgba(color) if color is not None else None
        self.textures = textures if textures is not None else {}
        self.uniforms = uniforms if uniforms is not None else {}
        if self.color is not None and self.uniforms.get("u_color") is None:
            self.uniforms["u_color"] = self.color

    def set_param(self, name: str, value: Any):
        self.uniforms[name] = value

    def update_color(self, rgba):
        rgba_array = _rgba(rgba)
        self.color = rgba_array
        self.uniforms["u_color"] = rgba_array

    _DEBUG_APPLY = False  # Debug: log uniform uploads

    def apply(
        self,
        model: np.ndarray,
        view: np.ndarray,
        projection: np.ndarray,
        graphics: GraphicsBackend,
        context_key: int | None = None,
    ):
        self.shader_programm.ensure_ready(graphics)
        self.shader_programm.use()
        self.shader_programm.set_uniform_matrix4("u_model", model)
        self.shader_programm.set_uniform_matrix4("u_view", view)
        self.shader_programm.set_uniform_matrix4("u_projection", projection)

        texture_slots = enumerate(self.textures.items())
        for unit, (uniform_name, texture) in texture_slots:
            texture.bind(graphics, unit, context_key=context_key)
            self.shader_programm.set_uniform_int(uniform_name, unit)

        for name, value in self.uniforms.items():
            if self._DEBUG_APPLY and name in ("u_fill_percent", "u_color_below", "u_color_above", "u_bounds_min", "u_bounds_max", "u_slice_axis"):
                print(f"[MaterialPhase.apply] {name}={value}")
            self.shader_programm.set_uniform_auto(name, value)

    def serialize(self) -> dict:
        """Сериализует фазу материала."""
        def serialize_uniform_value(val):
            if isinstance(val, np.ndarray):
                return val.tolist()
            return val

        return {
            "phase_mark": self.phase_mark,
            "priority": self.priority,
            "color": self.color.tolist() if self.color is not None else None,
            "uniforms": {k: serialize_uniform_value(v) for k, v in self.uniforms.items()},
            "textures": {k: tex.source_path for k, tex in self.textures.items()},
            "render_state": {
                "depth_test": self.render_state.depth_test,
                "depth_write": self.render_state.depth_write,
                "blend": self.render_state.blend,
                "cull": self.render_state.cull,
            },
            "shader": {
                "vertex": self.shader_programm.vertex_source,
                "fragment": self.shader_programm.fragment_source,
                "geometry": self.shader_programm.geometry_source,
            },
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "MaterialPhase":
        """Десериализует фазу материала."""
        from termin.visualization.render.renderpass import RenderState

        shader = ShaderProgram(
            vertex_source=data["shader"]["vertex"],
            fragment_source=data["shader"]["fragment"],
            geometry_source=data["shader"].get("geometry"),
        )

        rs_data = data.get("render_state", {})
        render_state = RenderState(
            depth_test=rs_data.get("depth_test", True),
            depth_write=rs_data.get("depth_write", True),
            blend=rs_data.get("blend", False),
            cull=rs_data.get("cull", True),
        )

        color = None
        if data.get("color") is not None:
            color = np.array(data["color"], dtype=np.float32)

        uniforms = {}
        for k, v in data.get("uniforms", {}).items():
            if isinstance(v, list):
                uniforms[k] = np.array(v, dtype=np.float32)
            else:
                uniforms[k] = v

        textures = {}
        if context is not None:
            for k, path in data.get("textures", {}).items():
                textures[k] = context.load_texture(path)

        return cls(
            shader_programm=shader,
            render_state=render_state,
            phase_mark=data.get("phase_mark", "opaque"),
            priority=data.get("priority", 0),
            color=color,
            textures=textures,
            uniforms=uniforms,
        )

    @classmethod
    def from_shader_phase(
        cls,
        shader_phase: "ParsedShaderPhase",
        color: np.ndarray | None = None,
        textures: Dict[str, TextureHandle] | None = None,
        extra_uniforms: Dict[str, Any] | None = None,
    ) -> "MaterialPhase":
        """
        Создаёт MaterialPhase из распаршенной ShaderPhase.

        Параметры:
            shader_phase: Распаршенная фаза из shader_parser
            color: Цвет материала (опционально, переопределяет u_color из uniforms)
            textures: Дополнительные текстуры
            extra_uniforms: Дополнительные uniforms (переопределяют defaults)

        Возвращает:
            MaterialPhase с настроенными шейдером, RenderState и uniforms
        """
        from termin.visualization.render.renderpass import RenderState

        # 1. Собираем ShaderProgram из stages
        stages = shader_phase.stages
        vertex_source = stages.get("vertex")
        fragment_source = stages.get("fragment")
        geometry_source = stages.get("geometry")

        if vertex_source is None:
            raise ValueError(f"Фаза {shader_phase.phase_mark!r} не имеет vertex стадии")
        if fragment_source is None:
            raise ValueError(f"Фаза {shader_phase.phase_mark!r} не имеет fragment стадии")

        # Извлекаем source из ShasderStage
        vs = vertex_source.source if hasattr(vertex_source, 'source') else str(vertex_source)
        fs = fragment_source.source if hasattr(fragment_source, 'source') else str(fragment_source)
        gs = None
        if geometry_source is not None:
            gs = geometry_source.source if hasattr(geometry_source, 'source') else str(geometry_source)

        shader = ShaderProgram(
            vertex_source=vs,
            fragment_source=fs,
            geometry_source=gs,
        )

        # 2. Собираем RenderState из gl-флагов
        render_state = RenderState(
            depth_write=shader_phase.gl_depth_mask if shader_phase.gl_depth_mask is not None else True,
            depth_test=shader_phase.gl_depth_test if shader_phase.gl_depth_test is not None else True,
            blend=shader_phase.gl_blend if shader_phase.gl_blend is not None else False,
            cull=shader_phase.gl_cull if shader_phase.gl_cull is not None else True,
        )

        # 3. Собираем uniforms из MaterialProperty defaults
        uniforms: Dict[str, Any] = {}
        for prop in shader_phase.uniforms:
            if prop.default is not None:
                # Конвертируем tuple в numpy array для векторных типов
                if prop.property_type in ("Vec2", "Vec3", "Vec4", "Color"):
                    uniforms[prop.name] = np.array(prop.default, dtype=np.float32)
                else:
                    uniforms[prop.name] = prop.default

        # 3.5. Собираем текстуры: для Texture properties без заданной текстуры — белая 1x1
        from termin.visualization.core.texture_handle import get_white_texture_handle

        final_textures: Dict[str, TextureHandle] = {}
        for prop in shader_phase.uniforms:
            if prop.property_type == "Texture":
                # Если текстура не задана явно — используем белую
                if textures is None or prop.name not in textures:
                    final_textures[prop.name] = get_white_texture_handle()

        # Добавляем явно заданные текстуры (перезаписывают белые)
        if textures is not None:
            final_textures.update(textures)

        # 4. Применяем extra_uniforms
        if extra_uniforms:
            uniforms.update(extra_uniforms)

        # 5. Определяем color
        final_color = color
        if final_color is None and "u_color" in uniforms:
            val = uniforms["u_color"]
            if isinstance(val, np.ndarray):
                final_color = val
            elif isinstance(val, (tuple, list)) and len(val) == 4:
                final_color = np.array(val, dtype=np.float32)

        return cls(
            shader_programm=shader,
            render_state=render_state,
            phase_mark=shader_phase.phase_mark,
            priority=shader_phase.priority,
            color=final_color,
            textures=final_textures,
            uniforms=uniforms,
        )

    def copy(self) -> "MaterialPhase":
        """
        Создаёт копию фазы материала.

        Стратегия копирования:
        - shader_programm: переиспользуется (шейдеры неизменяемые)
        - render_state: переиспользуется (неизменяемый)
        - color: копируется (numpy array)
        - textures: копируется dict (TextureHandle переиспользуются)
        - uniforms: глубокое копирование (могут содержать numpy arrays)
        """
        return MaterialPhase(
            shader_programm=self.shader_programm,  # переиспользуем
            render_state=self.render_state,  # переиспользуем
            phase_mark=self.phase_mark,
            priority=self.priority,
            color=self.color.copy() if self.color is not None else None,
            textures=dict(self.textures),  # shallow copy, TextureHandle переиспользуются
            uniforms=deepcopy(self.uniforms),  # deep copy для numpy arrays
        )


class Material:
    """Collection of shader parameters applied before drawing a mesh."""

    # Атрибуты класса с дефолтными значениями
    shader_name: str = "DefaultShader"

    def __init__(
        self,
        shader: ShaderProgram = None,
        color: np.ndarray | None = None,
        textures: Dict[str, TextureHandle] | None = None,
        uniforms: Dict[str, Any] | None = None,
        name: str | None = None,
        render_state: Optional["RenderState"] = None,
        phase_mark: str = "opaque",
        priority: int = 0,
        source_path: str | None = None,
        shader_name: str = "DefaultShader",
    ):
        if shader is None:
            shader = ShaderProgram.default_shader()

        if color is not None:
            base_color = _rgba(color)
        else:
            base_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)

        self.name = name
        self.source_path = source_path
        self.shader_name = shader_name

        phase = MaterialPhase(
            shader_programm=shader,
            render_state=render_state,
            phase_mark=phase_mark,
            priority=priority,
            color=base_color,
            textures=textures,
            uniforms=uniforms,
        )
        self.phases: List[MaterialPhase] = [phase]

    @property
    def _default_phase(self) -> MaterialPhase:
        return self.phases[0]

    @property
    def shader(self) -> ShaderProgram:
        return self._default_phase.shader_programm if "phases" in self.__dict__ else self.__dict__.get("_pre_shader")  # type: ignore[return-value]

    @shader.setter
    def shader(self, shader: ShaderProgram):
        if "phases" not in self.__dict__:
            self.__dict__["_pre_shader"] = shader
            return
        self._default_phase.shader_programm = shader

    @property
    def color(self) -> Optional[np.ndarray]:
        if "phases" not in self.__dict__:
            return self.__dict__.get("_pre_color")  # type: ignore[return-value]
        return self._default_phase.color

    @color.setter
    def color(self, rgba: Optional[np.ndarray]):
        if "phases" not in self.__dict__:
            self.__dict__["_pre_color"] = rgba
            return
        if rgba is None:
            self._default_phase.color = None
            self._default_phase.uniforms.pop("u_color", None)
        else:
            self._default_phase.color = _rgba(rgba)
            self._default_phase.uniforms["u_color"] = self._default_phase.color

    @property
    def textures(self) -> Dict[str, TextureHandle]:
        if "phases" not in self.__dict__:
            return self.__dict__.get("_pre_textures", {})  # type: ignore[return-value]
        return self._default_phase.textures

    @textures.setter
    def textures(self, value: Dict[str, TextureHandle]):
        if "phases" not in self.__dict__:
            self.__dict__["_pre_textures"] = value
            return
        self._default_phase.textures = value

    @property
    def uniforms(self) -> Dict[str, Any]:
        if "phases" not in self.__dict__:
            return self.__dict__.get("_pre_uniforms", {})  # type: ignore[return-value]
        return self._default_phase.uniforms

    @uniforms.setter
    def uniforms(self, value: Dict[str, Any]):
        if "phases" not in self.__dict__:
            self.__dict__["_pre_uniforms"] = value
            return
        self._default_phase.uniforms = value

    def set_param(self, name: str, value: Any):
        """Удобный метод задания параметров шейдера."""
        self._default_phase.set_param(name, value)

    def update_color(self, rgba):
        self._default_phase.update_color(rgba)

    def apply(self, model: np.ndarray, view: np.ndarray, projection: np.ndarray, graphics: GraphicsBackend, context_key: int | None = None):
        """Bind shader, upload MVP matrices and all statically defined uniforms."""
        self._default_phase.apply(model, view, projection, graphics, context_key=context_key)

    def update_from(self, other: "Material") -> None:
        """
        Обновляет данные материала из другого материала.

        Используется для hot-reload: сохраняет идентичность объекта,
        но обновляет все его данные.
        """
        self.phases = other.phases
        self.shader_name = other.shader_name
        # name и source_path не меняем — они идентифицируют материал

    def copy(self, name: str | None = None) -> "Material":
        """
        Создаёт копию материала.

        Стратегия копирования:
        - phases: копируются (каждая фаза копируется через MaterialPhase.copy())
        - shader_name: копируется
        - name: задаётся явно или генерируется из оригинала
        - source_path: не копируется (копия не связана с файлом)

        Шейдеры и render_state переиспользуются (они неизменяемые).
        Uniforms и color копируются глубоко.

        Args:
            name: Имя для копии. Если None, генерируется "{original_name}_copy".

        Returns:
            Новый экземпляр Material с скопированными данными.
        """
        mat = Material.__new__(Material)

        if name is not None:
            mat.name = name
        elif self.name:
            mat.name = f"{self.name}_copy"
        else:
            mat.name = "copy"

        mat.source_path = None  # копия не связана с файлом
        mat.shader_name = self.shader_name
        mat.phases = [phase.copy() for phase in self.phases]

        return mat

    def set_shader(self, program: "ShaderMultyPhaseProgramm", shader_name: str) -> None:
        """
        Устанавливает новый шейдер, пересоздавая phases.

        Сохраняет существующие uniforms и textures, применяя их к новым phases
        если соответствующие параметры существуют в новом шейдере.

        Args:
            program: Новая ShaderMultyPhaseProgramm
            shader_name: Имя шейдера
        """
        # Сохраняем текущие uniforms и textures
        old_uniforms: Dict[str, Any] = {}
        old_textures: Dict[str, Any] = {}
        for phase in self.phases:
            old_uniforms.update(phase.uniforms)
            old_textures.update(phase.textures)

        # Пересоздаём phases из нового шейдера
        self.phases = []
        for shader_phase in program.phases:
            phase = MaterialPhase.from_shader_phase(
                shader_phase=shader_phase,
                color=(1.0, 1.0, 1.0, 1.0),
                textures={},
                extra_uniforms={},
            )
            self.phases.append(phase)

        # Применяем сохранённые uniforms к новым phases
        for phase in self.phases:
            for name, value in old_uniforms.items():
                if name in phase.uniforms:
                    phase.uniforms[name] = value
            for name, value in old_textures.items():
                if name in phase.textures:
                    phase.textures[name] = value

        self.shader_name = shader_name

    # --- Serialization ---

    def direct_serialize(self) -> dict:
        """
        Сериализует материал.

        Если материал загружен из .material файла, возвращает ссылку на файл.
        Иначе сериализует inline со всеми фазами.
        """
        if self.source_path is not None:
            return {
                "type": "path",
                "path": self.source_path,
                "name": self.name,
            }

        return {
            "type": "inline",
            "name": self.name,
            "shader_name": self.shader_name,
            "phases": [phase.serialize() for phase in self.phases],
        }

    @classmethod
    def direct_deserialize(cls, data: dict, context=None) -> "Material":
        """
        Десериализует материал.

        Поддерживает типы:
        - "path": ссылка на .material файл
        - "inline": полная inline-сериализация
        """
        material_type = data.get("type", "inline")

        if material_type == "inline":
            mat = cls.__new__(cls)
            mat.name = data.get("name")
            mat.source_path = None
            mat.shader_path = None
            mat.shader_name = data.get("shader_name")
            mat.phases = [
                MaterialPhase.deserialize(phase_data, context)
                for phase_data in data.get("phases", [])
            ]
            return mat

        raise ValueError(f"Unknown material type: {material_type}")

    # Backward compatibility aliases
    serialize = direct_serialize
    deserialize = direct_deserialize

    @classmethod
    def from_parsed(
        cls,
        program: "ShaderMultyPhaseProgramm",
        color: np.ndarray | None = None,
        textures: Dict[str, TextureHandle] | None = None,
        uniforms: Dict[str, Any] | None = None,
        name: str | None = None,
        source_path: str | None = None,
    ) -> "Material":
        """
        Создаёт Material из распаршенной мультифазной программы.

        Параметры:
            program: ShaderMultyPhaseProgramm из shader_parser
            color: Базовый цвет (применяется ко всем фазам, где есть u_color)
            textures: Текстуры (применяются ко всем фазам)
            uniforms: Дополнительные uniforms (переопределяют defaults во всех фазах)
            name: Имя материала

        Возвращает:
            Material со всеми фазами из программы

        Пример использования:
            from termin.visualization.render.shader_parser import parse_shader_text, ShaderMultyPhaseProgramm

            text = open("my_shader.shader").read()
            tree = parse_shader_text(text)
            program = ShaderMultyPhaseProgramm.from_tree(tree)
            material = Material.from_parsed(program, color=(1, 0, 0, 1))
        """
        if not program.phases:
            raise ValueError("Программа не содержит фаз")

        # Создаём материал через __new__ чтобы обойти __init__
        mat = cls.__new__(cls)
        mat.name = name or program.program
        mat.source_path = source_path
        mat.shader_path = None  # Будет установлен при загрузке из .material файла
        mat.phases = []

        for shader_phase in program.phases:
            phase = MaterialPhase.from_shader_phase(
                shader_phase=shader_phase,
                color=color,
                textures=textures,
                extra_uniforms=uniforms,
            )
            mat.phases.append(phase)

        return mat

    def get_phases_for_mark(self, phase_mark: str) -> List["MaterialPhase"]:
        """
        Возвращает все фазы материала с указанной меткой, отсортированные по priority.

        Параметры:
            phase_mark: Метка фазы ("opaque", "transparent", "shadow" и т.д.)

        Возвращает:
            Список MaterialPhase отсортированный по priority (меньше = раньше)
        """
        matching = [p for p in self.phases if p.phase_mark == phase_mark]
        return sorted(matching, key=lambda p: p.priority)


# --- ErrorMaterial ---

_error_material: Material | None = None


def get_error_material() -> Material:
    """
    Возвращает материал ошибки (ярко-розовый).

    Используется когда MaterialHandle не может получить материал.
    Синглтон — создаётся один раз.
    """
    global _error_material

    if _error_material is None:
        _error_material = Material(
            color=np.array([1.0, 0.0, 1.0, 1.0], dtype=np.float32),  # Magenta
            name="__ErrorMaterial__",
            shader_name="DefaultShader",
        )

    return _error_material
