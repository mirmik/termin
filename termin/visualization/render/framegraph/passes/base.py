from __future__ import annotations

from termin.visualization.render.framegraph.core import FramePass


class RenderFramePass(FramePass):
    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene: "Scene",
        camera: "Camera",
        renderer: "Renderer",
        context_key: int,
        lights: list["Light"] | None = None,
        bind_default_framebuffer=None,
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
        - bind_default_framebuffer: функция биндинга системного framebuffer (для Present);
        - canvas: 2D-канва вьюпорта (для CanvasPass).
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
