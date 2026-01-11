from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, List, TYPE_CHECKING

import numpy as np

from termin.visualization.render.shader import ShaderProgram
from termin.visualization.platform.backends.base import (
    FramebufferHandle,
    GraphicsBackend,
    GPUTextureHandle,
)
from termin.visualization.render.framegraph import RenderFramePass, blit_fbo_to_fbo
from termin.visualization.render.framegraph.passes.present import _get_texture_from_resource
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class PostEffect:
    """
    Базовый интерфейс пост-эффекта.

    По умолчанию:
    - не требует дополнительных ресурсов (кроме основного color);
    - получает текущую color-текстуру и словарь extra_textures.
    """

    name: str = "unnamed_post_effect"

    # Поля для редактирования в инспекторе
    # Подклассы должны переопределить этот атрибут
    inspect_fields: dict = {}

    def __init_subclass__(cls, **kwargs):
        """Register subclass in InspectRegistry for inspector support."""
        super().__init_subclass__(**kwargs)

        # Don't register the base class itself
        if cls.__name__ == "PostEffect":
            return

        try:
            from termin._native.inspect import InspectRegistry
            registry = InspectRegistry.instance()

            # Register only own fields (not inherited)
            own_fields = cls.__dict__.get('inspect_fields', {})
            if own_fields:
                registry.register_python_fields(cls.__name__, own_fields)

            # Find parent type and register inheritance
            parent_name = None
            for klass in cls.__mro__[1:]:
                if klass is PostEffect:
                    parent_name = "PostEffect"
                    break
                if hasattr(klass, 'inspect_fields'):
                    parent_name = klass.__name__
                    break

            if parent_name:
                registry.set_type_parent(cls.__name__, parent_name)
        except ImportError:
            pass

    # ---- Сериализация ---------------------------------------------

    def serialize_data(self) -> dict:
        """
        Сериализует данные эффекта через InspectRegistry.

        Использует тот же механизм, что и PythonComponent - kind handlers
        применяются для enum, handles и т.д.
        """
        from termin._native.inspect import InspectRegistry
        return InspectRegistry.instance().serialize_all(self)

    def deserialize_data(self, data: dict) -> None:
        """
        Десериализует данные эффекта через InspectRegistry.

        Использует тот же механизм, что и PythonComponent - kind handlers
        применяются для enum, handles и т.д.
        """
        if not data:
            return
        from termin._native.inspect import InspectRegistry
        InspectRegistry.instance().deserialize_all(self, data)

    def serialize(self) -> dict:
        """
        Сериализует PostEffect в словарь.

        Использует InspectRegistry для сериализации полей.
        """
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "data": self.serialize_data(),
        }

    @classmethod
    def deserialize(cls, data: dict, resource_manager=None) -> "PostEffect":
        """
        Десериализует PostEffect из словаря.

        Args:
            data: Словарь с сериализованными данными
            resource_manager: ResourceManager для поиска класса

        Returns:
            Экземпляр PostEffect

        Raises:
            ValueError: если тип не найден
        """
        effect_type = data.get("type")
        if effect_type is None:
            raise ValueError("Missing 'type' in PostEffect data")

        # Получаем класс из ResourceManager
        if resource_manager is None:
            from termin.visualization.core.resources import ResourceManager
            resource_manager = ResourceManager.instance()

        effect_cls = resource_manager.get_post_effect(effect_type)
        if effect_cls is None:
            raise ValueError(f"Unknown PostEffect type: {effect_type}")

        # Создаём экземпляр и десериализуем данные
        instance = effect_cls()
        if "name" in data:
            instance.name = data["name"]
        instance.deserialize_data(data.get("data", {}))
        return instance

    # ---- API эффекта ---------------------------------------------

    def required_resources(self) -> set[str]:
        """
        Какие ресурсы (по именам FrameGraph) нужны этому эффекту,
        помимо основного input_res (обычно color).

        Например:
            {"id"}
            {"id", "depth"}
        и т.п.
        """
        return set()

    def draw(
        self,
        gfx: "GraphicsBackend",
        context_key: int,
        color_tex: "GPUTextureHandle",
        extra_textures: dict[str, "GPUTextureHandle"],
        size: tuple[int, int],
        target_fbo: "FramebufferHandle | None" = None,
    ):
        """
        color_tex      – текущая цветовая текстура (что пришло с предыдущего шага).
        extra_textures – карта имя_ресурса -> GPUTextureHandle (id, depth, normals...).
        size           – (width, height) целевого буфера.
        target_fbo     – целевой FBO (уже привязан, но передаётся для эффектов
                         с внутренними проходами, которым нужно восстановить его).

        Эффект внутри сам:
        - биндит нужные текстуры по юнитам;
        - включает свой шейдер;
        - рисует фуллскрин-квад.
        """
        raise NotImplementedError

    def clear_callbacks(self) -> None:
        """Clear any callbacks that reference external objects. Override in subclasses."""
        pass


class PostProcessPass(RenderFramePass):
    category = "Effects"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
        "internal_format": InspectField(
            path="internal_format",
            label="Internal Format",
            kind="enum",
            choices=[("", "Default (RGBA8)"), ("rgba8", "RGBA8"), ("rgba16f", "RGBA16F (HDR)"), ("rgba32f", "RGBA32F")],
        ),
    }

    def __init__(
        self,
        effects,
        input_res: str,
        output_res: str,
        pass_name: str = "PostProcess",
        internal_format: str = "",
    ):
        super().__init__(pass_name=pass_name)

        # нормализуем список эффектов
        if not isinstance(effects, (list, tuple)):
            effects = [effects]
        self.effects = list(effects)

        self.input_res = input_res
        self.output_res = output_res
        self._internal_format = internal_format  # FBO format for temp buffers ("rgba16f" for HDR)

        self._temp_fbos: list["FramebufferHandle"] = []

    @property
    def internal_format(self) -> str:
        return self._internal_format

    @internal_format.setter
    def internal_format(self, value: str) -> None:
        if value != self._internal_format:
            # Clear temp FBOs so they get recreated with new format
            for fbo in self._temp_fbos:
                if fbo is not None:
                    fbo.delete()
            self._temp_fbos.clear()
            self._internal_format = value

    def compute_reads(self) -> Set[str]:
        """Динамически собираем reads на основе эффектов."""
        reads: Set[str] = {self.input_res}
        for eff in self.effects:
            reads |= set(eff.required_resources())
        return reads

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def serialize_data(self) -> dict:
        """Сериализует данные PostProcessPass включая эффекты."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
            "internal_format": self.internal_format,
            "effects": [eff.serialize() for eff in self.effects],
        }

    def deserialize_data(self, data: dict) -> None:
        """Десериализует данные PostProcessPass включая эффекты."""
        if not data:
            return
        if "input_res" in data:
            self.input_res = data["input_res"]
        if "output_res" in data:
            self.output_res = data["output_res"]
        if "internal_format" in data:
            self.internal_format = data["internal_format"]
        # Effects уже десериализованы в _deserialize_instance

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "PostProcessPass":
        """Создаёт PostProcessPass из сериализованных данных."""
        # Effects и другие данные находятся внутри data["data"]
        inner_data = data.get("data", {})
        effects_data = inner_data.get("effects", [])
        effects = []

        for eff_data in effects_data:
            try:
                eff = PostEffect.deserialize(eff_data, resource_manager)
                effects.append(eff)
            except ValueError as e:
                print(f"Warning: Failed to deserialize PostEffect: {e}")

        return cls(
            effects=effects,
            input_res=inner_data.get("input_res", "color"),
            output_res=inner_data.get("output_res", "color_pp"),
            pass_name=data.get("pass_name", "PostProcess"),
            internal_format=inner_data.get("internal_format", ""),
        )

    def _effect_symbol(self, index: int, effect: "PostEffect") -> str:
        """
        Формирует стабильное имя внутреннего символа для эффекта.

        Добавляем индекс в цепочке, чтобы одинаковые эффекты (например,
        два Highlight) можно было различать.
        """
        effect_name = effect.name if hasattr(effect, "name") else effect.__class__.__name__
        if not effect_name:
            effect_name = effect.__class__.__name__
        return f"{index:02d}:{effect_name}"

    def get_internal_symbols(self) -> List[str]:
        """
        Возвращает список внутренних символов:
        - "input" — исходный color перед постобработкой;
        - по одному символу на каждый эффект в цепочке.
        """
        symbols: List[str] = ["input"]
        for idx, eff in enumerate(self.effects):
            symbols.append(self._effect_symbol(idx, eff))
        return symbols

    def _get_temp_fbo(self, graphics: "GraphicsBackend", index: int, size: tuple[int, int]):
        while len(self._temp_fbos) <= index:
            self._temp_fbos.append(graphics.create_framebuffer(size, 1, self.internal_format))
        fb = self._temp_fbos[index]
        fb.resize(size)
        return fb

    def destroy(self) -> None:
        """
        Clean up resources.

        Deletes temporary FBOs and clears callbacks on effects.
        """
        for fbo in self._temp_fbos:
            if fbo is not None:
                fbo.delete()
        self._temp_fbos.clear()

        for effect in self.effects:
            effect.clear_callbacks()

    def add_effect(self, effect: PostEffect):
        """
        Добавляет эффект в конец цепочки.
        reads пересчитывается автоматически через compute_reads().
        """
        self.effects.append(effect)

    def execute(self, ctx: "ExecuteContext") -> None:
        from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend

        # Для NOP бэкенда пропускаем реальные OpenGL операции
        if isinstance(ctx.graphics, NOPGraphicsBackend):
            return

        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        size = (pw, ph)

        fb_in = ctx.reads_fbos.get(self.input_res)
        if fb_in is None:
            return

        # Внутренняя точка дебага
        debug_symbol = self.get_debug_internal_point()
        debugger_window = self.get_debugger_window()

        # Извлекаем текстуру с учетом типа ресурса
        color_tex = _get_texture_from_resource(fb_in)
        if color_tex is None:
            return

        # --- extra textures ---
        required_resources: set[str] = set()
        for eff in self.effects:
            req = getattr(eff, "required_resources", None)
            if callable(req):
                required_resources |= set(req())

        extra_textures: dict[str, "GPUTextureHandle"] = {}
        for res_name in required_resources:
            fb = ctx.reads_fbos.get(res_name)
            if fb is None:
                continue
            # Извлекаем текстуру с учетом типа ресурса
            tex = _get_texture_from_resource(fb)
            if tex is not None:
                extra_textures[res_name] = tex

        fb_out_final = ctx.writes_fbos.get(self.output_res)
        if fb_out_final is None:
            return

        # --- нет эффектов -> блит и выходим ---
        if not self.effects:
            blit_fbo_to_fbo(ctx.graphics, fb_in, fb_out_final, size, key)
            return

        current_tex = color_tex

        # <<< ВАЖНО: постпроцесс — чисто экранная штука, отключаем глубину >>>
        ctx.graphics.set_depth_test(False)
        ctx.graphics.set_depth_mask(False)

        # Debugger: блит входной текстуры если выбран символ "input"
        if debug_symbol == "input":
            self._blit_to_debugger(ctx.graphics, fb_in)

        try:
            for i, effect in enumerate(self.effects):
                is_last = (i == len(self.effects) - 1)

                if is_last:
                    fb_target = fb_out_final
                else:
                    fb_target = self._get_temp_fbo(ctx.graphics, i % 2, size)

                ctx.graphics.bind_framebuffer(fb_target)
                ctx.graphics.set_viewport(0, 0, pw, ph)

                effect.draw(ctx.graphics, key, current_tex, extra_textures, size, fb_target)
                ctx.graphics.check_gl_error(f"PostFX: {effect.name if hasattr(effect, 'name') else effect.__class__.__name__}")

                # Debugger: блит после применения эффекта если выбран его символ
                if debug_symbol == self._effect_symbol(i, effect):
                    self._blit_to_debugger(ctx.graphics, fb_target)

                # Извлекаем текстуру с учетом типа ресурса
                current_tex = _get_texture_from_resource(fb_target)
                if current_tex is None:
                    break
        finally:
            # восстанавливаем "нормальное" состояние для последующих пассов
            ctx.graphics.set_depth_test(True)
            ctx.graphics.set_depth_mask(True)

    def _blit_to_debug(
        self,
        gfx: "GraphicsBackend",
        src_fb: "FramebufferHandle",
        dst_fb: "FramebufferHandle",
        size: tuple[int, int],
        context_key: int,
    ) -> None:
        """
        Копирует промежуточный результат постобработки в debug FBO.

        Используется для внутренних точек — после копирования возвращаемся
        к исходному FBO, чтобы продолжить цепочку без побочных эффектов.
        """
        blit_fbo_to_fbo(gfx, src_fb, dst_fb, size, context_key)
        gfx.bind_framebuffer(src_fb)
        gfx.set_viewport(0, 0, size[0], size[1])
