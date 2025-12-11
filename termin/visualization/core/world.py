"""World and Visualization classes for scene management and rendering."""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

from termin.visualization.core.scene import Scene
from termin.visualization.core.viewport import Viewport, make_default_pipeline
from termin.visualization.core.resources import ResourceManager
from termin.visualization.core.entity import Entity
from termin.visualization.platform.window import Window
from termin.visualization.platform.backends.base import GraphicsBackend, WindowBackend
from termin.visualization.platform.backends import (
    get_default_graphics_backend,
    get_default_window_backend,
    set_default_graphics_backend,
    set_default_window_backend,
)
from termin.visualization.render import (
    RenderEngine,
    RenderView,
    ViewportRenderState,
)

# For testing purposes, set this to True to close the world after the first frame.
CLOSE_AFTER_FIRST_FRAME = False


class World:
    """
    Коллекция сцен.

    Чистый контейнер для сцен без логики рендеринга.
    Используется редактором и игрой для хранения игровых данных.
    """

    def __init__(self):
        self.scenes: List[Scene] = []

    def add_scene(self, scene: Scene) -> Scene:
        """Добавляет сцену в мир."""
        self.scenes.append(scene)
        return scene

    def remove_scene(self, scene: Scene) -> None:
        """Удаляет сцену из мира."""
        if scene in self.scenes:
            self.scenes.remove(scene)

    def update(self, dt: float) -> None:
        """Обновляет все сцены."""
        for scene in self.scenes:
            scene.update(dt)

    # --- Сериализация ---

    def serialize(self, resource_manager: Optional[ResourceManager] = None) -> dict:
        """
        Сериализует мир в словарь.

        Включает:
        - resources: Все ресурсы из ResourceManager
        - scenes: Все сцены
        """
        rm = resource_manager or ResourceManager.instance()
        return {
            "version": "1.0",
            "resources": rm.serialize(),
            "scenes": [scene.serialize() for scene in self.scenes],
        }

    def save_to_file(self, path: str, resource_manager: Optional[ResourceManager] = None) -> None:
        """
        Сохраняет мир в JSON файл.

        Параметры:
            path: Путь к файлу для сохранения
            resource_manager: ResourceManager для сериализации ресурсов
        """
        data = self.serialize(resource_manager)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def deserialize(cls, data: dict) -> "World":
        """
        Восстанавливает мир из сериализованных данных.
        """
        world = cls()

        # Восстанавливаем ресурсы в глобальный ResourceManager
        rm = ResourceManager.instance()
        resources_data = data.get("resources", {})
        if resources_data:
            restored_rm = ResourceManager.deserialize(resources_data)
            rm.materials.update(restored_rm.materials)
            rm.meshes.update(restored_rm.meshes)
            rm.textures.update(restored_rm.textures)

        # Восстанавливаем сцены
        for scene_data in data.get("scenes", []):
            scene = Scene.deserialize(scene_data)
            world.add_scene(scene)

        return world

    @classmethod
    def load_from_file(cls, path: str) -> "World":
        """
        Загружает мир из JSON файла.

        Параметры:
            path: Путь к файлу

        Возвращает:
            Новый World с восстановленным состоянием
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.deserialize(data)


class Visualization:
    """
    Оркестратор рендеринга для простых приложений.

    Управляет:
    - Созданием окон (Window фасадов)
    - Основным циклом (run)
    - Рендерингом всех окон через RenderEngine

    Для редактора используйте World + Display + EditorDisplayInputManager напрямую.
    """

    def __init__(
        self,
        world: Optional[World] = None,
        graphics_backend: Optional[GraphicsBackend] = None,
        window_backend: Optional[WindowBackend] = None,
    ):
        """
        Создаёт Visualization.

        Параметры:
            world: World с сценами (создаётся новый если не указан).
            graphics_backend: Графический бэкенд.
            window_backend: Оконный бэкенд.
        """
        self.graphics = graphics_backend or get_default_graphics_backend()
        self.window_backend = window_backend or get_default_window_backend()
        set_default_graphics_backend(self.graphics)
        set_default_window_backend(self.window_backend)

        self.world = world or World()
        self.windows: List[Window] = []
        self._running = False

        # RenderEngine и состояния viewport'ов
        self._render_engine = RenderEngine(self.graphics)
        self._viewport_states: Dict[int, ViewportRenderState] = {}

        self.fps = 0

    @property
    def scenes(self) -> List[Scene]:
        """Сцены из World (для совместимости)."""
        return self.world.scenes

    def add_scene(self, scene: Scene) -> Scene:
        """Добавляет сцену (делегирует в World)."""
        return self.world.add_scene(scene)

    def remove_scene(self, scene: Scene) -> None:
        """Удаляет сцену (делегирует в World)."""
        self.world.remove_scene(scene)

    def create_window(
        self,
        width: int = 1280,
        height: int = 720,
        title: str = "termin viewer",
        **backend_kwargs,
    ) -> Window:
        """
        Создаёт новое окно.

        Параметры:
            width: Ширина окна.
            height: Высота окна.
            title: Заголовок окна.
            **backend_kwargs: Дополнительные параметры для бэкенда.

        Возвращает:
            Созданный Window.
        """
        share = self.windows[0] if self.windows else None
        window = Window(
            width=width,
            height=height,
            title=title,
            graphics=self.graphics,
            window_backend=self.window_backend,
            share=share,
            **backend_kwargs,
        )
        self.windows.append(window)
        return window

    def add_window(self, window: Window) -> None:
        """Добавляет существующее окно."""
        self.windows.append(window)

    def get_viewport_state(self, viewport: Viewport) -> ViewportRenderState:
        """
        Возвращает ViewportRenderState для viewport'а.

        Если состояние не существует, создаёт его с дефолтным pipeline.

        Параметры:
            viewport: Viewport для которого нужно состояние.

        Возвращает:
            ViewportRenderState с pipeline и FBO пулом.
        """
        key = id(viewport)
        if key not in self._viewport_states:
            pipeline = make_default_pipeline()
            self._viewport_states[key] = ViewportRenderState(pipeline=pipeline)
        return self._viewport_states[key]

    def find_render_pass(self, viewport: Viewport, pass_name: str):
        """
        Находит render pass по имени в pipeline viewport'а.

        Параметры:
            viewport: Viewport для которого ищем pass.
            pass_name: Имя pass'а (например, "PostFX", "Color").

        Возвращает:
            RenderFramePass или None, если не найден.
        """
        state = self.get_viewport_state(viewport)
        if state.pipeline is None:
            return None
        for render_pass in state.pipeline.passes:
            if render_pass.pass_name == pass_name:
                return render_pass
        return None

    def _render_window(self, window: Window) -> None:
        """
        Рендерит все viewport'ы окна через RenderEngine.

        Для каждого viewport создаёт RenderView и использует
        соответствующий ViewportRenderState.

        Параметры:
            window: Окно для рендеринга.
        """
        if window.handle is None:
            return

        # Собираем views для всех viewport'ов
        views = []
        for viewport in window.viewports:
            view = RenderView(
                scene=viewport.scene,
                camera=viewport.camera,
                rect=viewport.rect,
                canvas=viewport.canvas,
            )
            state = self.get_viewport_state(viewport)
            views.append((view, state))

        # Рендерим все views на surface окна
        if views:
            self._render_engine.render_views(
                surface=window.render_surface,
                views=views,
                present=True,
            )

        # Вызываем after_render_handler если есть
        if window.after_render_handler is not None:
            window.after_render_handler(window)

    def update_fps(self, dt: float) -> None:
        """Обновляет счётчик FPS."""
        if dt > 0:
            self.fps = int(1.0 / dt)
        else:
            self.fps = 0

    def run(self) -> None:
        """Запускает основной цикл."""
        if self._running:
            return
        self._running = True
        last = time.perf_counter()

        while self.windows:
            now = time.perf_counter()
            dt = now - last
            last = now

            # Обновляем все сцены
            self.world.update(dt)

            alive = []
            for window in list(self.windows):
                if window.should_close:
                    window.close()
                    continue
                window.update(dt)
                # Qt-виджеты управляют рендером сами
                if window.handle.drives_render():
                    window.handle.widget.update()
                else:
                    # GLFW и другие бэкенды — рендерим через RenderEngine
                    self._render_window(window)
                alive.append(window)
            self.windows = alive
            self.window_backend.poll_events()
            self.update_fps(dt)

            if CLOSE_AFTER_FIRST_FRAME:
                break

        for window in self.windows:
            window.close()
        self.window_backend.terminate()
        self._running = False

    # --- Сериализация (делегирует в World) ---

    def serialize(self, resource_manager: Optional[ResourceManager] = None) -> dict:
        """Сериализует мир (делегирует в World)."""
        return self.world.serialize(resource_manager)

    def save_to_file(self, path: str, resource_manager: Optional[ResourceManager] = None) -> None:
        """Сохраняет мир в файл (делегирует в World)."""
        self.world.save_to_file(path, resource_manager)

    @classmethod
    def deserialize(
        cls,
        data: dict,
        graphics_backend: Optional[GraphicsBackend] = None,
        window_backend: Optional[WindowBackend] = None,
    ) -> "Visualization":
        """Восстанавливает Visualization из сериализованных данных."""
        world = World.deserialize(data)
        return cls(world=world, graphics_backend=graphics_backend, window_backend=window_backend)

    @classmethod
    def load_from_file(
        cls,
        path: str,
        graphics_backend: Optional[GraphicsBackend] = None,
        window_backend: Optional[WindowBackend] = None,
    ) -> "Visualization":
        """Загружает Visualization из JSON файла."""
        world = World.load_from_file(path)
        return cls(world=world, graphics_backend=graphics_backend, window_backend=window_backend)


# Алиас для обратной совместимости
VisualizationWorld = Visualization
