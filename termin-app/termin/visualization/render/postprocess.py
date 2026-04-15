from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, List, TYPE_CHECKING

import numpy as np

from tgfx import (
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
    - получает tgfx2 handles для входных/extra текстур;
    - рисует через RenderContext2 внутри открытого pass'а.
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
        except ImportError as e:
            import logging
            logging.getLogger(__name__).warning(f"InspectRegistry not available for {cls.__name__}: {e}")

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
        ctx2,
        color_tex2,
        target_tex2,
        extra_tex2: dict,
        size: tuple[int, int],
    ):
        """
        ctx2        — tgfx2 Tgfx2RenderContext (ни в каком pass'е не находится
                      на момент вызова — эффект сам открывает/закрывает).
        color_tex2  — Tgfx2TextureHandle входного color (предыдущий шаг).
        target_tex2 — Tgfx2TextureHandle куда надо нарисовать конечный
                      результат. Эффект должен закончить рендером именно
                      сюда.
        extra_tex2  — карта имя_ресурса -> Tgfx2TextureHandle (id, depth, ...).
        size        — (width, height) целевого буфера.

        Эффект внутри:
        - открывает один или несколько ctx2.begin_pass/end_pass;
        - последний pass — в target_tex2;
        - компилирует шейдер через tc_shader_ensure_tgfx2;
        - биндит текстуры/униформы, draw_fullscreen_quad().

        Простые одноступенчатые эффекты могут использовать
        PostEffect._simple_draw(ctx2, target_tex2, size, setup_fn).
        """
        raise NotImplementedError

    @staticmethod
    def _simple_draw(ctx2, target_tex2, size, setup_fn):
        """
        Helper для одноступенчатых эффектов: открывает pass на target_tex2,
        выставляет стандартный state (depth off, blend off, cull none),
        вызывает setup_fn(ctx2) где эффект биндит свой шейдер, текстуры,
        униформы и вызывает draw_fullscreen_quad, затем закрывает pass.
        """
        from tgfx._tgfx_native import CULL_NONE, PIXEL_RGBA8
        w, h = size
        ctx2.begin_pass(target_tex2)
        ctx2.set_viewport(0, 0, w, h)
        ctx2.set_depth_test(False)
        ctx2.set_depth_write(False)
        ctx2.set_blend(False)
        ctx2.set_cull(CULL_NONE)
        ctx2.set_color_format(PIXEL_RGBA8)
        setup_fn(ctx2)
        ctx2.end_pass()

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
                from tcbase import log
                log.error(f"Failed to deserialize PostEffect: {e}")

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
        effect_name = effect.name or effect.__class__.__name__
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

        if ctx.ctx2 is None:
            from tcbase import log
            log.error(f"[PostProcessPass] '{self.pass_name}': ctx.ctx2 is None — PostProcessPass is tgfx2-only")
            return

        from tgfx._tgfx_native import wrap_fbo_color_as_tgfx2

        px, py, pw, ph = ctx.rect
        size = (pw, ph)
        ctx2 = ctx.ctx2

        tex_in = ctx.tex2_reads.get(self.input_res)
        if not tex_in:
            return

        tex_out_final = ctx.tex2_writes.get(self.output_res)
        if not tex_out_final:
            return

        # --- нет эффектов -> блит и выходим ---
        if not self.effects:
            ctx2.blit(tex_in, tex_out_final)
            return

        # Внутренняя точка дебага
        debug_symbol = self.get_debug_internal_point()

        # Extra textures: читаем напрямую из tex2_reads — никаких
        # per-frame wrap'ов, handles уже персистентные.
        required_resources: set[str] = set()
        for eff in self.effects:
            required_resources |= set(eff.required_resources())

        extra_tex2: dict = {}
        for res_name in required_resources:
            tex2 = ctx.tex2_reads.get(res_name)
            if tex2:
                extra_tex2[res_name] = tex2

        current_tex2 = tex_in

        # Эффект сам открывает/закрывает свои ctx2 passes. PostProcessPass
        # лишь решает куда направить выход: в temp FBO (промежуточные
        # шаги) или в финальный output (последний эффект).
        for i, effect in enumerate(self.effects):
            is_last = (i == len(self.effects) - 1)

            if is_last:
                target_tex2 = tex_out_final
            else:
                # Temp FBOs остаются на legacy пути до полной миграции
                # _get_temp_fbo на native device.create_texture.
                fb_target = self._get_temp_fbo(ctx.graphics, i % 2, size)
                target_tex2 = wrap_fbo_color_as_tgfx2(ctx2, fb_target)
                if not target_tex2:
                    from tcbase import log
                    log.error(f"[PostProcessPass] '{self.pass_name}': failed to wrap temp target for effect '{effect.name}'")
                    break

            effect.draw(ctx2, current_tex2, target_tex2, extra_tex2, size)

            # Выход этого эффекта становится входом следующего
            if not is_last:
                current_tex2 = target_tex2

