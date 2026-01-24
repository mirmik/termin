from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.render.framegraph.core import FramePass

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class RenderFramePass(FramePass):
    def execute(self, ctx: "ExecuteContext") -> None:
        """
        Execute the render pass.

        Args:
            ctx: ExecuteContext containing all render data:
                - graphics: graphics backend
                - reads_fbos/writes_fbos: FBO maps
                - rect: pixel rectangle (px, py, pw, ph)
                - scene, camera: what to render
                - lights: pre-computed lights
                - layer_mask: which entity layers to render
        """
        raise NotImplementedError

    def required_resources(self) -> set[str]:
        """
        Возвращает множество ресурсов, которые должны быть доступны пассу.

        По умолчанию это объединение reads и writes, но конкретные пассы
        могут переопределить метод, если набор зависимостей меняется
        динамически (например, BlitPass с переключаемым источником).
        """
        return set(self.reads) | set(self.writes)

    def get_resource_specs(self) -> list["ResourceSpec"]:
        """
        Возвращает список спецификаций требований к ресурсам.

        Пассы могут переопределить этот метод для объявления:
        - Фиксированного размера ресурса (например, shadow map 1024x1024)
        - Параметров очистки (цвет, глубина)
        - Формата attachment'ов (в будущем)

        По умолчанию возвращает пустой список (нет специальных требований).
        """
        return []

    def destroy(self) -> None:
        """
        Clean up pass resources.

        Override in subclasses to release FBOs, textures, etc.
        """
        pass

    def _blit_to_debugger(
        self, graphics: "GraphicsBackend", src_fbo: "FramebufferHandle"
    ) -> None:
        """
        Блитит текущее состояние FBO в окно дебаггера.

        Используется для режима "внутри пасса" — отображение промежуточного
        состояния после отрисовки конкретной сущности.
        """
        if self._debugger_window is None:
            return

        from termin.visualization.render.framegraph.passes.present import PresentToScreenPass
        from sdl2 import video as sdl_video

        tex = src_fbo.color_texture()
        if tex is None:
            return

        try:
            saved_context = sdl_video.SDL_GL_GetCurrentContext()
            saved_window = sdl_video.SDL_GL_GetCurrentWindow()

            self._debugger_window.make_current()

            dst_w, dst_h = self._debugger_window.framebuffer_size()

            graphics.bind_framebuffer(None)
            graphics.set_viewport(0, 0, dst_w, dst_h)

            graphics.set_depth_test(False)
            graphics.set_depth_mask(False)

            shader = PresentToScreenPass._get_shader()
            shader.ensure_ready()  # debugger has its own context
            shader.use()
            shader.set_uniform_int("u_tex", 0)
            tex.bind(0)
            graphics.draw_ui_textured_quad(0)

            self._debugger_window.swap_buffers()

        except Exception as e:
            from termin._native import log
            log.error(f"[RenderFramePass] blit_to_debugger failed: {e}")

        finally:
            if saved_window and saved_context:
                sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)

            # Восстанавливаем состояние для продолжения рендеринга
            graphics.bind_framebuffer(src_fbo)
            w, h = src_fbo.get_size()
            graphics.set_viewport(0, 0, w, h)
            graphics.set_depth_test(True)
            graphics.set_depth_mask(True)
