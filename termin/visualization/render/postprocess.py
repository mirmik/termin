from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple, List

import numpy as np

from termin.visualization.render.shader import ShaderProgram
from termin.visualization.platform.backends.base import (
    FramebufferHandle,
    GraphicsBackend,
    TextureHandle,
)
from termin.visualization.render.framegraph import RenderFramePass, blit_fbo_to_fbo
from termin.visualization.render.framegraph.passes.present import _get_texture_from_resource


class PostEffect:
    """
    Базовый интерфейс пост-эффекта.

    По умолчанию:
    - не требует дополнительных ресурсов (кроме основного color);
    - получает текущую color-текстуру и словарь extra_textures.
    """

    name: str = "unnamed_post_effect"

    # ---- Сериализация ---------------------------------------------

    def serialize(self) -> dict:
        """
        Сериализует PostEffect в словарь.

        Базовая реализация сохраняет:
        - type: имя класса для десериализации
        - name: имя эффекта

        Подклассы должны переопределить _serialize_params() для
        добавления своих параметров.
        """
        data = {
            "type": self.__class__.__name__,
            "name": self.name,
        }
        data.update(self._serialize_params())
        return data

    def _serialize_params(self) -> dict:
        """
        Возвращает словарь с параметрами для сериализации.

        Подклассы должны переопределить этот метод.
        """
        return {}

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

        return effect_cls._deserialize_instance(data, resource_manager)

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "PostEffect":
        """
        Создаёт экземпляр из сериализованных данных.

        Подклассы должны переопределить этот метод.
        """
        instance = cls()
        if "name" in data:
            instance.name = data["name"]
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
        color_tex: "TextureHandle",
        extra_textures: dict[str, "TextureHandle"],
        size: tuple[int, int],
    ):
        """
        color_tex      – текущая цветовая текстура (что пришло с предыдущего шага).
        extra_textures – карта имя_ресурса -> TextureHandle (id, depth, normals...).
        size           – (width, height) целевого буфера.

        Эффект внутри сам:
        - биндит нужные текстуры по юнитам;
        - включает свой шейдер;
        - рисует фуллскрин-квад.
        """
        raise NotImplementedError



class PostProcessPass(RenderFramePass):
    def __init__(
        self,
        effects,
        input_res: str,
        output_res: str,
        pass_name: str = "PostProcess",
    ):
        # нормализуем список эффектов
        if not isinstance(effects, (list, tuple)):
            effects = [effects]
        self.effects = list(effects)

        self.input_res = input_res
        self.output_res = output_res

        # --- динамически собираем reads на основе эффектов ---
        reads: set[str] = {input_res}
        for eff in self.effects:
            # даём шанс и "старым" объектам, если вдруг не наследуются от PostEffect
            reads |= set(eff.required_resources())

        super().__init__(
            pass_name=pass_name,
            reads=reads,
            writes={output_res},
        )

        self._temp_fbos: list["FramebufferHandle"] = []

    def _serialize_params(self) -> dict:
        """Сериализует параметры PostProcessPass."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
            "effects": [eff.serialize() for eff in self.effects],
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "PostProcessPass":
        """Создаёт PostProcessPass из сериализованных данных."""
        effects_data = data.get("effects", [])
        effects = []

        for eff_data in effects_data:
            try:
                eff = PostEffect.deserialize(eff_data, resource_manager)
                effects.append(eff)
            except ValueError as e:
                print(f"Warning: Failed to deserialize PostEffect: {e}")

        return cls(
            effects=effects,
            input_res=data.get("input_res", "color"),
            output_res=data.get("output_res", "color_pp"),
            pass_name=data.get("pass_name", "PostProcess"),
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
            self._temp_fbos.append(graphics.create_framebuffer(size))
        fb = self._temp_fbos[index]
        fb.resize(size)
        return fb

    def rebuild_reads(self):
        """
        Вызывать, если ты поменял self.effects после создания пасса.
        Обновляет список ресурсов, которые пасс читает,
        чтобы FrameGraph учёл новые зависимости.
        """
        reads: set[str] = {self.input_res}
        for eff in self.effects:
            reads |= set(eff.required_resources())
        self.reads = reads

    def add_effect(self, effect: PostEffect):
        """
        Добавляет эффект в конец цепочки.
        После вызова нужно вызвать rebuild_reads().
        """
        self.effects.append(effect)
        self.rebuild_reads()

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        context_key: int = 0,
        lights=None,
        canvas=None,
    ):
        from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend

        # Для NOP бэкенда пропускаем реальные OpenGL операции
        if isinstance(graphics, NOPGraphicsBackend):
            return

        px, py, pw, ph = rect
        key = context_key

        size = (pw, ph)

        fb_in = reads_fbos.get(self.input_res)
        if fb_in is None:
            return

        # Внутренняя точка дебага (символ и ресурс вывода)
        debug_symbol, debug_output = self.get_debug_internal_point()
        debug_fb = None
        if debug_symbol is not None and debug_output is not None:
            debug_fb = writes_fbos.get(debug_output)

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

        extra_textures: dict[str, "TextureHandle"] = {}
        for res_name in required_resources:
            fb = reads_fbos.get(res_name)
            if fb is None:
                continue
            # Извлекаем текстуру с учетом типа ресурса
            tex = _get_texture_from_resource(fb)
            if tex is not None:
                extra_textures[res_name] = tex

        fb_out_final = writes_fbos.get(self.output_res)
        if fb_out_final is None:
            return

        # --- нет эффектов -> блит и выходим ---
        if not self.effects:
            if debug_fb is not None and debug_symbol == "input":
                self._blit_to_debug(graphics, fb_in, debug_fb, size, key)
            blit_fbo_to_fbo(graphics, fb_in, fb_out_final, size, key)
            return

        current_tex = color_tex

        # При запросе дебага исходного состояния пробрасываем его в debug FBO.
        if debug_fb is not None and debug_symbol == "input":
            self._blit_to_debug(graphics, fb_in, debug_fb, size, key)

        # <<< ВАЖНО: постпроцесс — чисто экранная штука, отключаем глубину >>>
        graphics.set_depth_test(False)
        graphics.set_depth_mask(False)

        try:
            for i, effect in enumerate(self.effects):
                is_last = (i == len(self.effects) - 1)

                if is_last:
                    fb_target = fb_out_final
                else:
                    fb_target = self._get_temp_fbo(graphics, i % 2, size)

                graphics.bind_framebuffer(fb_target)
                graphics.set_viewport(0, 0, pw, ph)

                effect.draw(graphics, key, current_tex, extra_textures, size)

                # Сохранение промежуточного результата в debug FBO при совпадении символа
                effect_symbol = self._effect_symbol(i, effect)
                if debug_fb is not None and debug_symbol == effect_symbol:
                    self._blit_to_debug(graphics, fb_target, debug_fb, size, key)

                # Извлекаем текстуру с учетом типа ресурса
                current_tex = _get_texture_from_resource(fb_target)
                if current_tex is None:
                    break
        finally:
            # восстанавливаем "нормальное" состояние для последующих пассов
            graphics.set_depth_test(True)
            graphics.set_depth_mask(True)

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
