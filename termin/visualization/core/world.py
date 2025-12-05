"""Visualization world orchestrating scenes, windows and main loop."""

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


class VisualizationWorld:
    """
    High-level application controller.
    
    Оркестрирует рендеринг через RenderEngine:
    - Для каждого viewport создаётся ViewportRenderState с дефолтным pipeline
    - RenderEngine выполняет рендер всех views на каждое окно
    - FBO пул хранится в _viewport_states
    """

    def __init__(self, graphics_backend: GraphicsBackend | None = None, window_backend: WindowBackend | None = None):
        self.graphics = graphics_backend or get_default_graphics_backend()
        self.window_backend = window_backend or get_default_window_backend()
        set_default_graphics_backend(self.graphics)
        set_default_window_backend(self.window_backend)
        self.scenes: List[Scene] = []
        self.windows: List[Window] = []
        self._running = False
        
        # Новая архитектура рендеринга
        self._render_engine = RenderEngine(self.graphics)
        # Ключ — id(viewport), значение — ViewportRenderState
        self._viewport_states: Dict[int, ViewportRenderState] = {}
        
        self.fps = 0

    def add_scene(self, scene: Scene) -> Scene:
        self.scenes.append(scene)
        return scene

    def remove_scene(self, scene: Scene):
        if scene in self.scenes:
            self.scenes.remove(scene)

    def create_window(self, width: int = 1280, height: int = 720, title: str = "termin viewer", **backend_kwargs) -> Window:
        share = self.windows[0] if self.windows else None
        window = Window(width=width, height=height, title=title, graphics=self.graphics, window_backend=self.window_backend, share=share, **backend_kwargs)
        self.windows.append(window)
        return window

    def add_window(self, window: Window):
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

    def update_fps(self, dt):
        if dt > 0:
            self.fps = int(1.0 / dt)
        else:
            self.fps = 0

    def run(self):
        if self._running:
            return
        self._running = True
        last = time.perf_counter()

        while self.windows:
            now = time.perf_counter()
            dt = now - last
            last = now

            for scene in list(self.scenes):
                scene.update(dt)

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

    def save_to_file(self, path: str, resource_manager: Optional[ResourceManager] = None):
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
    def deserialize(
        cls,
        data: dict,
        graphics_backend: GraphicsBackend | None = None,
        window_backend: WindowBackend | None = None,
    ) -> "VisualizationWorld":
        """
        Восстанавливает мир из сериализованных данных.
        """
        world = cls(graphics_backend=graphics_backend, window_backend=window_backend)

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
    def load_from_file(
        cls,
        path: str,
        graphics_backend: GraphicsBackend | None = None,
        window_backend: WindowBackend | None = None,
    ) -> "VisualizationWorld":
        """
        Загружает мир из JSON файла.

        Параметры:
            path: Путь к файлу
            graphics_backend: Backend для графики (опционально)
            window_backend: Backend для окон (опционально)

        Возвращает:
            Новый VisualizationWorld с восстановленным состоянием
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.deserialize(data, graphics_backend, window_backend)
