"""
Display — абстракция дисплея (экрана вывода).

Display объединяет:
- RenderSurface — куда рендерим (окно или offscreen)
- Viewports — список viewport'ов с камерами и сценами

Display НЕ отвечает за:
- Ввод (это делает DisplayInputManager)
- Создание окна (это делает Visualization или Editor)
"""

from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.render.surface import RenderSurface
    from termin.visualization.ui.canvas import Canvas


class Display:
    """
    Display — что и куда рендерим.

    Содержит:
    - surface: RenderSurface (окно или offscreen FBO)
    - viewports: список Viewport'ов

    Для рендеринга используйте RenderEngine снаружи:
        engine.render_views(display.surface, views)
    """

    def __init__(self, surface: "RenderSurface"):
        """
        Создаёт Display с указанной поверхностью.

        Параметры:
            surface: Поверхность рендеринга (WindowRenderSurface или OffscreenRenderSurface).
        """
        self._surface = surface
        self._viewports: List["Viewport"] = []

    @property
    def surface(self) -> "RenderSurface":
        """Поверхность рендеринга."""
        return self._surface

    @property
    def viewports(self) -> List["Viewport"]:
        """Список viewport'ов (только для чтения)."""
        return list(self._viewports)

    def get_size(self) -> Tuple[int, int]:
        """Возвращает размер дисплея в пикселях."""
        return self._surface.get_size()

    def add_viewport(self, viewport: "Viewport") -> "Viewport":
        """
        Добавляет viewport в дисплей.

        Устанавливает обратную ссылку viewport.display = self.

        Параметры:
            viewport: Viewport для добавления.

        Возвращает:
            Добавленный viewport.
        """
        viewport.display = self
        self._viewports.append(viewport)
        return viewport

    def remove_viewport(self, viewport: "Viewport") -> None:
        """
        Удаляет viewport из дисплея.

        Параметры:
            viewport: Viewport для удаления.
        """
        if viewport in self._viewports:
            self._viewports.remove(viewport)
            viewport.display = None

    def create_viewport(
        self,
        scene: "Scene",
        camera: "CameraComponent",
        rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        canvas: Optional["Canvas"] = None,
    ) -> "Viewport":
        """
        Создаёт и добавляет новый viewport.

        Параметры:
            scene: Сцена для рендеринга.
            camera: Камера для рендеринга.
            rect: Нормализованный прямоугольник (x, y, w, h) в [0..1].
            canvas: Опциональная 2D канва для UI.

        Возвращает:
            Созданный Viewport.
        """
        from termin.visualization.core.viewport import Viewport

        viewport = Viewport(
            scene=scene,
            camera=camera,
            display=self,
            rect=rect,
            canvas=canvas,
        )
        camera.viewport = viewport
        self._viewports.append(viewport)
        return viewport

    def viewport_at(self, x: float, y: float) -> Optional["Viewport"]:
        """
        Находит viewport под указанными координатами.

        Параметры:
            x, y: Нормализованные координаты [0..1], origin сверху-слева.

        Возвращает:
            Viewport под курсором или None.
        """
        # Преобразуем y: экранные координаты (сверху-вниз) → OpenGL (снизу-вверх)
        ny = 1.0 - y

        for viewport in self._viewports:
            vx, vy, vw, vh = viewport.rect
            if vx <= x <= vx + vw and vy <= ny <= vy + vh:
                return viewport
        return None

    def viewport_at_pixels(self, px: float, py: float) -> Optional["Viewport"]:
        """
        Находит viewport под указанными пиксельными координатами.

        Параметры:
            px, py: Координаты в пикселях, origin сверху-слева.

        Возвращает:
            Viewport под курсором или None.
        """
        width, height = self.get_size()
        if width <= 0 or height <= 0:
            return None

        nx = px / width
        ny = py / height
        return self.viewport_at(nx, ny)

    def viewport_rect_to_pixels(self, viewport: "Viewport") -> Tuple[int, int, int, int]:
        """
        Преобразует нормализованный rect viewport'а в пиксели.

        Параметры:
            viewport: Viewport для преобразования.

        Возвращает:
            (px, py, pw, ph) — позиция и размер в пикселях.
        """
        width, height = self.get_size()
        vx, vy, vw, vh = viewport.rect
        px = int(vx * width)
        py = int(vy * height)
        pw = int(vw * width)
        ph = int(vh * height)
        return (px, py, pw, ph)

    def make_current(self) -> None:
        """Делает контекст рендеринга текущим."""
        self._surface.make_current()

    def present(self) -> None:
        """Представляет результат рендеринга (swap buffers)."""
        self._surface.present()
