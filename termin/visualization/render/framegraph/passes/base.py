from __future__ import annotations

from typing import TYPE_CHECKING

from termin.visualization.render.framegraph.core import FramePass

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle


class RenderFramePass(FramePass):
    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene: "Scene",
        camera: "Camera",
        context_key: int,
        lights: list["Light"] | None = None,
        canvas=None,
    ) -> None:
        """
        Абстрактное выполнение прохода кадра.

        Все зависимости прокидываются явно:
        - graphics: графический бэкенд;
        - reads_fbos: карта FBO, из которых пасс читает;
        - writes_fbos: карта FBO, в которые пасс пишет;
        - rect: (px, py, pw, ph) – целевой прямоугольник вывода в пикселях;
        - scene, camera, renderer: объекты текущего вьюпорта;
        - context_key: ключ для кэшей VAO/шейдеров;
        - lights: предвычисленные источники света (может быть None);
        - canvas: 2D-канва вьюпорта (legacy, не используется).
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
            shader.ensure_ready(graphics)
            shader.use()
            shader.set_uniform_int("u_tex", 0)
            tex.bind(0)
            graphics.draw_ui_textured_quad(0)

            self._debugger_window.swap_buffers()

        except Exception:
            pass

        finally:
            if saved_window and saved_context:
                sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)

            # Восстанавливаем состояние для продолжения рендеринга
            graphics.bind_framebuffer(src_fbo)
            w, h = src_fbo.get_size()
            graphics.set_viewport(0, 0, w, h)
            graphics.set_depth_test(True)
            graphics.set_depth_mask(True)
