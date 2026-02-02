from __future__ import annotations

from typing import Optional, Callable, List, Tuple, TYPE_CHECKING
from abc import ABC, abstractmethod

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QWindow

from OpenGL import GL as gl
import numpy as np

from termin.visualization.platform.backends.base import GraphicsBackend
from termin._native.render import TcShader

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GPUTextureHandle
    from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend


# ============================================================
# Обработчики ресурсов (ResourceHandlers)
# ============================================================


class ResourceHandler(ABC):
    """
    Базовый класс для обработки различных типов ресурсов framegraph.

    Каждый тип ресурса имеет свой обработчик, который знает:
    - Как извлечь текстуру для отображения
    - Нужны ли UI элементы управления
    - Как обновить UI при изменении ресурса
    """

    @abstractmethod
    def get_texture(self, resource, context: dict) -> "GPUTextureHandle | None":
        """
        Извлекает текстуру из ресурса для отображения.

        Args:
            resource: объект ресурса (SingleFBO, ShadowMapArrayResource и т.д.)
            context: контекст с дополнительной информацией (например, индекс shadow map)

        Returns:
            GPUTextureHandle или None
        """
        pass

    @abstractmethod
    def create_ui_panel(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget | None:
        """
        Создаёт панель UI для управления ресурсом (если нужна).

        Args:
            parent: родительский виджет

        Returns:
            QWidget с элементами управления или None, если управление не требуется
        """
        pass

    @abstractmethod
    def update_ui(self, resource, ui_panel: QtWidgets.QWidget | None) -> None:
        """
        Обновляет UI элементы на основе текущего состояния ресурса.

        Args:
            resource: объект ресурса
            ui_panel: панель UI, созданная в create_ui_panel
        """
        pass


class SingleFBOHandler(ResourceHandler):
    """
    Обработчик для SingleFBO ресурсов.

    SingleFBO — это простой framebuffer с одной color текстурой.
    Не требует дополнительных UI элементов управления.
    """

    def get_texture(self, resource, context: dict) -> "GPUTextureHandle | None":
        """Возвращает color_texture из SingleFBO или FramebufferHandle."""
        if resource is None:
            return None

        from termin.visualization.render.framegraph.resource import SingleFBO
        from termin.graphics import FramebufferHandle

        if isinstance(resource, SingleFBO):
            return resource.color_texture()
        if isinstance(resource, FramebufferHandle):
            return resource.color_texture()
        return None

    def create_ui_panel(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget | None:
        """SingleFBO не требует дополнительных элементов управления."""
        return None

    def update_ui(self, resource, ui_panel: QtWidgets.QWidget | None) -> None:
        """Нет UI для обновления."""
        pass


class ShadowMapArrayHandler(ResourceHandler):
    """
    Обработчик для ShadowMapArrayResource.

    ShadowMapArray содержит массив shadow maps от разных источников света.
    Требует ComboBox для выбора конкретной shadow map.
    """

    def __init__(self):
        self._combo: QtWidgets.QComboBox | None = None
        self._on_index_changed: Callable[[int], None] | None = None

    def set_index_changed_callback(self, callback: Callable[[int], None]) -> None:
        """Устанавливает callback для уведомления об изменении индекса."""
        self._on_index_changed = callback

    def get_texture(self, resource, context: dict) -> "GPUTextureHandle | None":
        """
        Возвращает текстуру из выбранного entry в ShadowMapArray.

        context должен содержать 'shadow_map_index' — индекс выбранного shadow map.
        """
        if resource is None:
            return None

        from termin.visualization.render.framegraph.resource import ShadowMapArrayResource

        if not isinstance(resource, ShadowMapArrayResource):
            return None

        if len(resource) == 0:
            return None

        shadow_map_index = context.get('shadow_map_index', 0)
        index = min(shadow_map_index, len(resource) - 1)
        entry = resource[index]

        return entry.texture()

    def create_ui_panel(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget | None:
        """Создаёт панель с ComboBox для выбора shadow map."""
        panel = QtWidgets.QWidget(parent)
        layout = QtWidgets.QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QtWidgets.QLabel("Shadow Map:")
        self._combo = QtWidgets.QComboBox()
        self._combo.currentIndexChanged.connect(self._on_combo_changed)

        layout.addWidget(label)
        layout.addWidget(self._combo, 1)

        return panel

    def update_ui(self, resource, ui_panel: QtWidgets.QWidget | None) -> None:
        """Обновляет список shadow maps в ComboBox."""
        if self._combo is None or resource is None:
            return

        from termin.visualization.render.framegraph.resource import ShadowMapArrayResource

        if not isinstance(resource, ShadowMapArrayResource):
            return

        count = len(resource)

        # Блокируем сигналы при обновлении
        self._combo.blockSignals(True)
        self._combo.clear()

        for i in range(count):
            entry = resource[i]
            self._combo.addItem(f"Light {entry.light_index}", i)

        # Устанавливаем первый элемент по умолчанию
        if count > 0:
            self._combo.setCurrentIndex(0)

        self._combo.blockSignals(False)

    def _on_combo_changed(self, index: int) -> None:
        """Внутренний обработчик изменения ComboBox."""
        if self._on_index_changed is not None and index >= 0:
            self._on_index_changed(index)


class FramegraphTextureWidget(QtWidgets.QWidget):
    """
    Виджет для отображения FBO текстуры из framegraph.

    Использует SDL окно с shared OpenGL context для доступа к текстурам,
    созданным в основном рендер-контексте.
    """
    depthImageUpdated = QtCore.pyqtSignal(QtGui.QImage)
    depthErrorUpdated = QtCore.pyqtSignal(str)

    def __init__(
        self,
        window_backend: "SDLEmbeddedWindowBackend",
        graphics: GraphicsBackend,
        get_fbos: Callable[[], dict],
        resource_name: str = "debug",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._window_backend = window_backend
        self._graphics = graphics
        self._get_fbos = get_fbos
        self._resource_name = resource_name

        self._shader: Optional[TcShader] = None
        self._vao: Optional[int] = None
        self._vbo: Optional[int] = None
        self._initialized = False
        self._channel_mode: int = 0  # 0=RGB, 1=R, 2=G, 3=B, 4=A
        self._highlight_hdr: bool = False  # Highlight HDR pixels (>1.0)

        # HDR statistics (updated on render)
        self._hdr_stats: dict = {}

        # Captured depth для режима "внутри пасса" (передаётся через callback)
        self._captured_depth: Optional[np.ndarray] = None

        # Флаг запроса обновления depth buffer (только по кнопке)
        self._depth_update_requested: bool = False

        # Реестр обработчиков ресурсов
        self._handlers: dict[str, ResourceHandler] = {
            "fbo": SingleFBOHandler(),
            "shadow_map_array": ShadowMapArrayHandler(),
        }

        # Контекст для обработчиков (хранит состояние, например индекс shadow map)
        self._handler_context: dict = {
            'shadow_map_index': 0,
        }

        self.setMinimumSize(200, 150)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # Создаём SDL окно с shared context
        self._sdl_window = window_backend.create_embedded_window(
            width=400, height=300, title="Framegraph Debug"
        )

        # Встраиваем SDL окно в Qt
        native_handle = self._sdl_window.native_handle
        self._qwindow = QWindow.fromWinId(native_handle)
        self._gl_container = QtWidgets.QWidget.createWindowContainer(self._qwindow, self)

        # Layout для контейнера
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._gl_container)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(400, 300)

    def _ensure_initialized(self) -> None:
        """Инициализирует OpenGL ресурсы при первом использовании."""
        if self._initialized:
            return
        self._sdl_window.make_current()
        self._get_shader()
        self._init_fullscreen_quad()
        self._initialized = True

    def _get_shader(self) -> TcShader:
        """Ленивая инициализация шейдера фуллскрин-квада."""
        if self._shader is None:
            vert_src = """
            #version 330 core
            layout(location = 0) in vec2 a_pos;
            layout(location = 1) in vec2 a_uv;
            out vec2 v_uv;
            void main()
            {
                v_uv = a_uv;
                gl_Position = vec4(a_pos, 0.0, 1.0);
            }
            """
            frag_src = """
            #version 330 core
            in vec2 v_uv;
            uniform sampler2D u_tex;
            uniform int u_channel;  // 0=RGB, 1=R, 2=G, 3=B, 4=A
            uniform int u_highlight_hdr;  // 1=highlight pixels > 1.0
            out vec4 FragColor;
            void main()
            {
                vec4 c = texture(u_tex, v_uv);
                vec3 result;

                if (u_channel == 1) {
                    result = vec3(c.r);
                } else if (u_channel == 2) {
                    result = vec3(c.g);
                } else if (u_channel == 3) {
                    result = vec3(c.b);
                } else if (u_channel == 4) {
                    result = vec3(c.a);
                } else {
                    result = c.rgb;
                }

                // HDR highlight: show pixels > 1.0 with magenta overlay
                if (u_highlight_hdr == 1) {
                    float maxVal = max(max(c.r, c.g), c.b);
                    if (maxVal > 1.0) {
                        float intensity = clamp((maxVal - 1.0) / 2.0, 0.0, 1.0);
                        result = mix(result, vec3(1.0, 0.0, 1.0), 0.5 + intensity * 0.5);
                    }
                }

                FragColor = vec4(result, 1.0);
            }
            """
            self._shader = TcShader.from_sources(vert_src, frag_src, "", "FramegraphDebugger")
            self._shader.ensure_ready()
        return self._shader

    def _init_fullscreen_quad(self) -> None:
        """Создаёт VAO/VBO для quad'а (позиции + UV)."""
        if self._vao is not None:
            return

        data = [
            -1.0, -1.0, 0.0, 0.0,
            1.0, -1.0, 1.0, 0.0,
            -1.0, 1.0, 0.0, 1.0,
            1.0, 1.0, 1.0, 1.0,
        ]
        import array
        arr = array.array("f", data)

        vao = gl.glGenVertexArrays(1)
        vbo = gl.glGenBuffers(1)

        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, arr.tobytes(), gl.GL_STATIC_DRAW)

        stride = 4 * 4
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(8))

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)

        self._vao = vao
        self._vbo = vbo

    def set_resource_name(self, name: str) -> None:
        """Set resource name to display."""
        self._resource_name = name

    def get_sdl_window(self):
        """Возвращает SDL окно для блита из пасса."""
        return self._sdl_window

    def on_depth_captured(self, depth_array: np.ndarray) -> None:
        """
        Callback для получения depth buffer из пасса.

        Вызывается из ColorPass._blit_to_debugger при захвате
        промежуточного состояния.
        """
        self._captured_depth = depth_array
        self._emit_depth_image(depth_array)

    def on_depth_error(self, message: str) -> None:
        """
        Callback для сообщения об ошибке чтения depth buffer.

        Вызывается из FrameDebuggerPass при невозможности прочитать depth.
        """
        self.depthErrorUpdated.emit(message)

    def _emit_depth_image(self, depth: np.ndarray) -> None:
        """Конвертирует depth array в QImage и эмитит сигнал."""
        if depth is None:
            return
        height, width = depth.shape
        depth = np.nan_to_num(depth, nan=1.0, posinf=1.0, neginf=0.0)
        d_min = float(depth.min())
        d_max = float(depth.max())
        if d_max > d_min:
            norm = (depth - d_min) / (d_max - d_min)
        else:
            norm = depth
        norm = 1.0 - norm
        img = (norm * 255.0).clip(0.0, 255.0).astype(np.uint8)
        height_i, width_i = img.shape
        bytes_per_line = width_i
        buffer = img.tobytes()

        qimage = QtGui.QImage(
            buffer,
            width_i,
            height_i,
            bytes_per_line,
            QtGui.QImage.Format.Format_Grayscale8,
        )
        qimage = qimage.copy()
        self.depthImageUpdated.emit(qimage)

    def _current_resource(self):
        """Возвращает текущий ресурс из словаря fbos."""
        fbos = self._get_fbos()
        if not fbos:
            return None
        if self._resource_name not in fbos:
            return None
        return fbos[self._resource_name]

    def _get_texture(self):
        """
        Извлекает текстуру из текущего ресурса используя соответствующий обработчик.

        Returns:
            GPUTextureHandle или None
        """
        resource = self._current_resource()
        if resource is None:
            return None

        # Определяем тип ресурса
        resource_type = self.get_resource_type()
        if resource_type is None:
            # Для обратной совместимости: если нет resource_type, пробуем SingleFBOHandler
            handler = self._handlers.get("fbo")
            if handler:
                return handler.get_texture(resource, self._handler_context)
            return None

        # Получаем соответствующий обработчик
        handler = self._handlers.get(resource_type)
        if handler is None:
            return None

        # Используем обработчик для получения текстуры
        return handler.get_texture(resource, self._handler_context)

    def set_shadow_map_index(self, index: int) -> None:
        """
        Устанавливает индекс shadow map для отображения.

        Args:
            index: индекс в массиве ShadowMapArrayResource
        """
        self._handler_context['shadow_map_index'] = max(0, index)
        self.render()

    def set_channel_mode(self, mode: int) -> None:
        """
        Устанавливает режим отображения каналов.

        Args:
            mode: 0=RGB, 1=R, 2=G, 3=B, 4=A
        """
        self._channel_mode = mode
        self.render()

    def set_highlight_hdr(self, enabled: bool) -> None:
        """
        Включает/выключает подсветку HDR пикселей.

        Args:
            enabled: True для подсветки пикселей > 1.0
        """
        self._highlight_hdr = enabled
        self.render()

    def get_hdr_stats(self) -> dict:
        """
        Возвращает последние вычисленные HDR статистики.

        Returns:
            dict с ключами: min_r, max_r, min_g, max_g, min_b, max_b,
                           hdr_pixel_count, total_pixels, hdr_percent
        """
        return self._hdr_stats

    def request_depth_update(self) -> None:
        """Запросить обновление depth buffer на следующем рендере."""
        self._depth_update_requested = True

    def get_resource_type(self) -> str | None:
        """
        Возвращает тип текущего ресурса.

        Returns:
            "fbo", "shadow_map_array" или None
        """
        resource = self._current_resource()
        if resource is None:
            return None

        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        if isinstance(resource, ShadowMapArrayResource):
            return "shadow_map_array"
        if isinstance(resource, (SingleFBO, FramebufferHandle)):
            return "fbo"
        return None

    def _update_depth_image(self) -> None:
        """Read depth buffer from current FBO and emit as QImage."""
        resource = self._current_resource()
        if resource is None:
            return

        # Extract FBO from resource
        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        fbo = None
        if isinstance(resource, ShadowMapArrayResource):
            if len(resource) > 0:
                index = self._handler_context.get('shadow_map_index', 0)
                index = min(index, len(resource) - 1)
                entry = resource[index]
                fbo = entry.fbo
        elif isinstance(resource, SingleFBO):
            fbo = resource._fbo
        elif isinstance(resource, FramebufferHandle):
            fbo = resource

        if fbo is None:
            return

        # Read depth directly from FBO
        depth = self._graphics.read_depth_buffer(fbo)
        if depth is None:
            return

        height, width = depth.shape
        depth = np.nan_to_num(depth, nan=1.0, posinf=1.0, neginf=0.0)
        d_min = float(depth.min())
        d_max = float(depth.max())
        if d_max > d_min:
            norm = (depth - d_min) / (d_max - d_min)
        else:
            norm = depth
        norm = 1.0 - norm
        img = (norm * 255.0).clip(0.0, 255.0).astype(np.uint8)
        height_i, width_i = img.shape
        bytes_per_line = width_i
        buffer = img.tobytes()

        qimage = QtGui.QImage(
            buffer,
            width_i,
            height_i,
            bytes_per_line,
            QtGui.QImage.Format.Format_Grayscale8,
        )
        qimage = qimage.copy()
        self.depthImageUpdated.emit(qimage)

    def compute_hdr_stats(self) -> dict:
        """
        Вычисляет HDR статистику для текущей текстуры.

        Читает пиксели из FBO и вычисляет:
        - min/max/avg для каждого канала RGB
        - количество и процент HDR пикселей (>1.0)

        Returns:
            dict со статистикой или пустой dict при ошибке
        """
        resource = self._current_resource()
        if resource is None:
            return {}

        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        fbo = None
        if isinstance(resource, ShadowMapArrayResource):
            if len(resource) > 0:
                index = self._handler_context.get('shadow_map_index', 0)
                index = min(index, len(resource) - 1)
                entry = resource[index]
                fbo = entry.fbo
        elif isinstance(resource, SingleFBO):
            fbo = resource._fbo
        elif isinstance(resource, FramebufferHandle):
            fbo = resource

        if fbo is None:
            return {}

        # Read color buffer from FBO as float
        pixels = self._graphics.read_color_buffer_float(fbo)
        if pixels is None:
            return {}

        # pixels shape: (height, width, 4) for RGBA
        if len(pixels.shape) != 3 or pixels.shape[2] < 3:
            return {}

        r = pixels[:, :, 0]
        g = pixels[:, :, 1]
        b = pixels[:, :, 2]

        total_pixels = r.size

        # Compute stats
        stats = {
            "min_r": float(np.min(r)),
            "max_r": float(np.max(r)),
            "avg_r": float(np.mean(r)),
            "min_g": float(np.min(g)),
            "max_g": float(np.max(g)),
            "avg_g": float(np.mean(g)),
            "min_b": float(np.min(b)),
            "max_b": float(np.max(b)),
            "avg_b": float(np.mean(b)),
            "total_pixels": total_pixels,
        }

        # Count HDR pixels (any channel > 1.0)
        max_rgb = np.maximum(np.maximum(r, g), b)
        hdr_mask = max_rgb > 1.0
        hdr_count = int(np.sum(hdr_mask))

        stats["hdr_pixel_count"] = hdr_count
        stats["hdr_percent"] = (hdr_count / total_pixels * 100.0) if total_pixels > 0 else 0.0

        # Max value overall
        stats["max_value"] = float(np.max(max_rgb))

        self._hdr_stats = stats
        return stats

    def render(self) -> None:
        """Рендерит текстуру в SDL окно."""
        from sdl2 import video as sdl_video

        self._ensure_initialized()

        # Запоминаем текущий контекст
        saved_context = sdl_video.SDL_GL_GetCurrentContext()
        saved_window = sdl_video.SDL_GL_GetCurrentWindow()

        self._sdl_window.make_current()

        # Bind default framebuffer (window)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

        w, h = self._sdl_window.framebuffer_size()

        gl.glViewport(0, 0, w, h)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        # Получаем текстуру из ресурса (независимо от типа)
        tex = self._get_texture()
        if tex is None:
            self._sdl_window.swap_buffers()
            # Восстанавливаем контекст
            if saved_window and saved_context:
                sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)
            return

        shader = self._get_shader()
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        shader.set_uniform_int("u_channel", self._channel_mode)
        shader.set_uniform_int("u_highlight_hdr", 1 if self._highlight_hdr else 0)

        tex.bind(0)

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)

        self._init_fullscreen_quad()
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)

        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_DEPTH_TEST)

        self._sdl_window.swap_buffers()

        # Читаем depth только по запросу (кнопка Refresh)
        if self._depth_update_requested:
            self._depth_update_requested = False
            self._update_depth_image()

        # Восстанавливаем контекст
        if saved_window and saved_context:
            sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)

    def update(self) -> None:
        """Переопределяем update() для вызова render()."""
        super().update()
        self.render()

    def clear_to_background(self) -> None:
        """Очищает окно дебаггера до фонового цвета (без текстуры)."""
        from sdl2 import video as sdl_video

        self._ensure_initialized()

        saved_context = sdl_video.SDL_GL_GetCurrentContext()
        saved_window = sdl_video.SDL_GL_GetCurrentWindow()

        self._sdl_window.make_current()

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        w, h = self._sdl_window.framebuffer_size()
        gl.glViewport(0, 0, w, h)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        self._sdl_window.swap_buffers()

        if saved_window and saved_context:
            sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)

    def closeEvent(self, event) -> None:
        """Закрываем SDL окно при закрытии виджета."""
        if self._sdl_window is not None:
            self._window_backend.remove_window(self._sdl_window)
            self._sdl_window.close()
            self._sdl_window = None
        super().closeEvent(event)


class FramegraphDebugDialog(QtWidgets.QDialog):
    """
    Окно-дебагер framegraph с двумя режимами подключения:

    1. «Между пассами» — выбираем промежуточный ресурс (FBO) между пассами.
       Используется BlitPass для копирования выбранного ресурса в debug FBO.

    2. «Внутри пасса» — выбираем пасс и его внутренний символ.
       Например, для ColorPass можно выбрать меш и увидеть состояние
       рендера после его отрисовки.

    UI:
    - ComboBox для выбора viewport
    - Группа радиокнопок для выбора режима
    - Панель для режима «Между пассами»: ComboBox с ресурсами
    - Панель для режима «Внутри пасса»: ComboBox пассов + ComboBox символов
    - Чекбокс паузы
    - GL-виджет с текстурой
    """

    def __init__(
        self,
        window_backend: "SDLEmbeddedWindowBackend",
        graphics: GraphicsBackend,
        rendering_controller,
        on_request_update: Optional[Callable[[], None]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._window_backend = window_backend
        self._graphics = graphics
        self._rendering_controller = rendering_controller
        self._on_request_update = on_request_update
        self._resource_name = "debug"

        # Current selected viewport
        self._current_viewport = None
        self._viewports_list: List[Tuple[object, str]] = []

        # Текущий режим: "inside" (Фреймпассы) или "between" (Ресурсы)
        self._mode = "inside"
        # Текущий выбранный пасс (для режима «Фреймпассы»)
        self._selected_pass: str | None = None
        # Текущий выбранный внутренний символ (для режима «Фреймпассы»)
        self._selected_symbol: str | None = None

        # Debug source resource name (for "between passes" mode)
        # Будет установлен при инициализации из первого доступного ресурса
        self._debug_source_res: str = ""
        # Paused state
        self._debug_paused: bool = False

        # FrameDebuggerPass для режима "между пассами" (создаётся динамически)
        self._frame_debugger_pass = None

        # UI элементы (инициализируются в _build_ui)
        self._depth_label: QtWidgets.QLabel | None = None

        self._build_ui()

        # Timer for updating timing info (GPU results may arrive with delay)
        self._timing_timer = QtCore.QTimer(self)
        self._timing_timer.timeout.connect(self._update_timing_label)
        self._timing_timer.start(100)  # Update every 100ms

    def _build_ui(self) -> None:
        self.setWindowTitle("Framegraph Debugger")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setModal(False)
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        layout = QtWidgets.QVBoxLayout(self)

        # ============ Верхняя панель: настройки слева, pipeline справа ============
        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # --- Левая часть: настройки ---
        settings_widget = QtWidgets.QWidget()
        settings_layout = QtWidgets.QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        # Выбор viewport
        viewport_row = QtWidgets.QHBoxLayout()
        viewport_label = QtWidgets.QLabel("Viewport:")
        self._viewport_combo = QtWidgets.QComboBox()
        self._viewport_combo.currentIndexChanged.connect(self._on_viewport_selected)
        viewport_row.addWidget(viewport_label)
        viewport_row.addWidget(self._viewport_combo, 1)
        settings_layout.addLayout(viewport_row)

        # Render stats status line
        render_stats_row = QtWidgets.QHBoxLayout()
        self._render_stats_label = QtWidgets.QLabel()
        self._render_stats_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; padding: 3px 6px; border-radius: 3px; "
            "font-family: monospace; font-size: 10px; color: #b8b8b8; }"
        )
        render_stats_row.addWidget(self._render_stats_label, 1)
        self._refresh_stats_btn = QtWidgets.QPushButton("↻")
        self._refresh_stats_btn.setFixedWidth(24)
        self._refresh_stats_btn.setToolTip("Refresh render stats")
        self._refresh_stats_btn.clicked.connect(self._on_refresh_render_stats_clicked)
        render_stats_row.addWidget(self._refresh_stats_btn)
        settings_layout.addLayout(render_stats_row)

        # Группа выбора режима
        mode_group = QtWidgets.QGroupBox("Режим")
        mode_layout = QtWidgets.QHBoxLayout(mode_group)
        self._radio_inside = QtWidgets.QRadioButton("Фреймпассы")
        self._radio_between = QtWidgets.QRadioButton("Ресурсы")
        self._radio_inside.setChecked(True)
        self._radio_inside.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self._radio_inside)
        mode_layout.addWidget(self._radio_between)
        settings_layout.addWidget(mode_group)

        # Панель «Ресурсы»
        self._between_panel = QtWidgets.QWidget()
        between_layout = QtWidgets.QVBoxLayout(self._between_panel)
        between_layout.setContentsMargins(0, 0, 0, 0)

        resource_row = QtWidgets.QHBoxLayout()
        self._resource_label = QtWidgets.QLabel("Ресурс:")
        self._resource_combo = QtWidgets.QComboBox()
        self._resource_combo.currentTextChanged.connect(self._on_resource_selected)
        resource_row.addWidget(self._resource_label)
        resource_row.addWidget(self._resource_combo, 1)
        between_layout.addLayout(resource_row)

        # Пасс, который пишет выбранный ресурс
        self._writer_pass_label = QtWidgets.QLabel()
        self._writer_pass_label.setStyleSheet(
            "QLabel { color: #8be9fd; font-weight: bold; }"
        )
        between_layout.addWidget(self._writer_pass_label)

        # HDR Analysis controls
        hdr_row = QtWidgets.QHBoxLayout()
        self._hdr_highlight_check = QtWidgets.QCheckBox("Highlight HDR")
        self._hdr_highlight_check.toggled.connect(self._on_hdr_highlight_toggled)
        hdr_row.addWidget(self._hdr_highlight_check)
        self._hdr_analyze_btn = QtWidgets.QPushButton("Analyze")
        self._hdr_analyze_btn.setFixedWidth(60)
        self._hdr_analyze_btn.clicked.connect(self._on_analyze_hdr_clicked)
        hdr_row.addWidget(self._hdr_analyze_btn)
        hdr_row.addStretch()
        between_layout.addLayout(hdr_row)

        # HDR statistics label
        self._hdr_stats_label = QtWidgets.QLabel()
        self._hdr_stats_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; padding: 4px; border-radius: 3px; "
            "font-family: monospace; font-size: 10px; }"
        )
        self._hdr_stats_label.setWordWrap(True)
        between_layout.addWidget(self._hdr_stats_label)

        settings_layout.addWidget(self._between_panel)
        self._between_panel.hide()  # Скрыт по умолчанию (режим "Фреймпассы")

        # Панель «Фреймпассы»
        self._inside_panel = QtWidgets.QWidget()
        inside_layout = QtWidgets.QVBoxLayout(self._inside_panel)
        inside_layout.setContentsMargins(0, 0, 0, 0)

        pass_row = QtWidgets.QHBoxLayout()
        self._pass_label = QtWidgets.QLabel("Пасс:")
        self._pass_combo = QtWidgets.QComboBox()
        self._pass_combo.currentTextChanged.connect(self._on_pass_selected)
        pass_row.addWidget(self._pass_label)
        pass_row.addWidget(self._pass_combo, 1)
        inside_layout.addLayout(pass_row)

        symbol_row = QtWidgets.QHBoxLayout()
        self._symbol_label = QtWidgets.QLabel("Символ:")
        self._symbol_combo = QtWidgets.QComboBox()
        self._symbol_combo.currentTextChanged.connect(self._on_symbol_selected)
        symbol_row.addWidget(self._symbol_label)
        symbol_row.addWidget(self._symbol_combo, 1)
        inside_layout.addLayout(symbol_row)

        # Timing info label
        self._timing_label = QtWidgets.QLabel()
        self._timing_label.setStyleSheet(
            "QLabel { background-color: #2a3a2a; padding: 4px; border-radius: 3px; "
            "font-family: monospace; font-size: 11px; }"
        )
        self._timing_label.hide()
        inside_layout.addWidget(self._timing_label)

        # Pass serialization view
        self._pass_serialization = QtWidgets.QTextEdit()
        self._pass_serialization.setReadOnly(True)
        self._pass_serialization.setMaximumHeight(150)
        self._pass_serialization.setStyleSheet(
            "QTextEdit { font-family: monospace; font-size: 10px; "
            "background-color: #1e1e1e; color: #d4d4d4; }"
        )
        inside_layout.addWidget(self._pass_serialization)

        settings_layout.addWidget(self._inside_panel)
        # inside_panel показан по умолчанию (режим "Фреймпассы")

        # Контейнер для UI обработчиков ресурсов
        self._resource_ui_container = QtWidgets.QWidget()
        self._resource_ui_layout = QtWidgets.QVBoxLayout(self._resource_ui_container)
        self._resource_ui_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.addWidget(self._resource_ui_container)
        self._resource_ui_container.hide()

        self._current_handler_ui: QtWidgets.QWidget | None = None
        self._current_handler: ResourceHandler | None = None

        # Информация о FBO
        self._fbo_info_label = QtWidgets.QLabel()
        self._fbo_info_label.setStyleSheet(
            "QLabel { background-color: #2a2a2a; padding: 4px; border-radius: 3px; }"
        )
        self._fbo_info_label.setWordWrap(True)
        settings_layout.addWidget(self._fbo_info_label)

        # Пауза и выбор канала
        controls_row = QtWidgets.QHBoxLayout()
        self._pause_check = QtWidgets.QCheckBox("Пауза")
        self._pause_check.toggled.connect(self._on_pause_toggled)
        controls_row.addWidget(self._pause_check)
        controls_row.addStretch()
        channel_label = QtWidgets.QLabel("Канал:")
        self._channel_combo = QtWidgets.QComboBox()
        self._channel_combo.addItems(["RGB", "R", "G", "B", "A"])
        self._channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        controls_row.addWidget(channel_label)
        controls_row.addWidget(self._channel_combo)
        settings_layout.addLayout(controls_row)

        settings_layout.addStretch()

        # --- Правая часть: pipeline schedule ---
        pipeline_widget = QtWidgets.QWidget()
        pipeline_layout = QtWidgets.QVBoxLayout(pipeline_widget)
        pipeline_layout.setContentsMargins(0, 0, 0, 0)

        pipeline_title = QtWidgets.QLabel("Pipeline Schedule")
        pipeline_title.setStyleSheet("font-weight: bold;")
        pipeline_layout.addWidget(pipeline_title)

        self._pipeline_info = QtWidgets.QTextEdit()
        self._pipeline_info.setReadOnly(True)
        self._pipeline_info.setStyleSheet(
            "QTextEdit { font-family: monospace; font-size: 11px; "
            "background-color: #1e1e1e; color: #d4d4d4; }"
        )
        pipeline_layout.addWidget(self._pipeline_info)

        top_splitter.addWidget(settings_widget)
        top_splitter.addWidget(pipeline_widget)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)

        layout.addWidget(top_splitter)

        # ============ Просмотр ============
        self._gl_widget = FramegraphTextureWidget(
            window_backend=self._window_backend,
            graphics=self._graphics,
            get_fbos=self._get_fbos,
            resource_name=self._resource_name,
            parent=self,
        )

        # Depth buffer с подписью
        depth_container = QtWidgets.QWidget()
        depth_layout = QtWidgets.QVBoxLayout(depth_container)
        depth_layout.setContentsMargins(0, 0, 0, 0)

        # Header with title and refresh button
        depth_header = QtWidgets.QHBoxLayout()
        depth_title = QtWidgets.QLabel("Depth Buffer")
        depth_header.addWidget(depth_title)
        depth_header.addStretch()
        self._refresh_depth_btn = QtWidgets.QPushButton("Refresh")
        self._refresh_depth_btn.setFixedWidth(60)
        self._refresh_depth_btn.clicked.connect(self._on_refresh_depth_clicked)
        depth_header.addWidget(self._refresh_depth_btn)
        depth_layout.addLayout(depth_header)

        self._depth_label = QtWidgets.QLabel()
        self._depth_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._depth_label.setMinimumSize(100, 100)
        self._depth_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        depth_layout.addWidget(self._depth_label, 1)

        viewer_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        viewer_splitter.addWidget(self._gl_widget)
        viewer_splitter.addWidget(depth_container)
        viewer_splitter.setStretchFactor(0, 3)
        viewer_splitter.setStretchFactor(1, 2)

        layout.addWidget(viewer_splitter, 1)

        self._gl_widget.depthImageUpdated.connect(self._on_depth_image_updated)
        self._gl_widget.depthErrorUpdated.connect(self._on_depth_error_updated)

        # Инициализация
        self._update_viewport_list()
        self._update_resource_list()
        self._update_passes_list()
        self._sync_pause_state()
        self._update_render_stats()

        # Синхронизируем выбранный ресурс с первым в списке
        self._sync_initial_resource()

    # ============ Viewport selection ============

    def _on_viewport_selected(self, index: int) -> None:
        """Handle viewport selection change."""
        # Отключаем от старого viewport
        self._detach_frame_debugger_pass()

        if index < 0 or index >= len(self._viewports_list):
            self._current_viewport = None
            return
        self._current_viewport = self._viewports_list[index][0]

        # Update lists for new viewport
        self._update_resource_list()
        self._update_passes_list()

        # Синхронизируем ресурс с первым в списке для нового viewport
        self._sync_initial_resource()

        # Подключаем к новому viewport если режим "между пассами"
        if self._mode == "between":
            self._attach_frame_debugger_pass()

        # Запрашиваем обновление depth для новой текстуры
        self._request_depth_refresh()

        # Update GL widget
        self._gl_widget.update()

    def _update_gl_widget_resource(self) -> None:
        """Update GL widget resource name for current viewport."""
        current_res = self._resource_combo.currentText()
        if current_res:
            self._gl_widget.set_resource_name(current_res)
        else:
            # Fallback to first available resource
            fbos = self._get_fbos()
            if fbos:
                first_key = next(iter(fbos.keys()), None)
                if first_key:
                    self._gl_widget.set_resource_name(first_key)

    def _sync_initial_resource(self) -> None:
        """Синхронизирует начальное состояние: выбирает первый ресурс и обновляет все UI."""
        if self._resource_combo.count() == 0:
            return

        # Выбираем первый ресурс в комбобоксе
        self._resource_combo.setCurrentIndex(0)
        first_resource = self._resource_combo.currentText()

        if first_resource:
            # Синхронизируем все части
            self._debug_source_res = first_resource
            self._gl_widget.set_resource_name(first_resource)

            # Обновляем UI
            self._update_fbo_info()
            self._update_writer_pass_label()
            self._update_pipeline_info()

    def _update_viewport_list(self) -> None:
        """Update viewport ComboBox from RenderingController."""
        if self._rendering_controller is None:
            return

        self._viewports_list = self._rendering_controller.get_all_viewports_info()

        self._viewport_combo.blockSignals(True)
        self._viewport_combo.clear()
        for viewport, label in self._viewports_list:
            self._viewport_combo.addItem(label)

        # Select first viewport by default
        if self._viewports_list:
            self._viewport_combo.setCurrentIndex(0)
            self._current_viewport = self._viewports_list[0][0]
        self._viewport_combo.blockSignals(False)

    def _update_render_stats(self) -> None:
        """Update render statistics label from RenderingManager."""
        from termin.visualization.render.manager import RenderingManager

        rm = RenderingManager.instance()
        stats = rm.get_render_stats()

        scenes = stats["attached_scenes"]
        pipelines = stats["scene_pipelines"]
        unmanaged = stats["unmanaged_viewports"]

        parts = []
        parts.append(f"Scenes: {scenes}")
        parts.append(f"Pipelines: {pipelines}")
        parts.append(f"Unmanaged: {unmanaged}")

        # Add details if there's something to show
        details = []
        if stats["scene_names"]:
            details.append(f"[{', '.join(stats['scene_names'])}]")
        if stats["pipeline_names"]:
            details.append(f"({', '.join(stats['pipeline_names'])})")

        text = " | ".join(parts)
        if details:
            text += "  " + " ".join(details)

        self._render_stats_label.setText(text)

    def _on_refresh_render_stats_clicked(self) -> None:
        """Handle refresh button click for render stats."""
        self._update_render_stats()

    # ============ Data access helpers ============

    def _get_current_render_state(self):
        """Get ViewportRenderState for current viewport."""
        if self._current_viewport is None or self._rendering_controller is None:
            return None
        return self._rendering_controller.get_viewport_state(self._current_viewport)

    def _get_fbos(self) -> dict:
        """Get all resources (FBOs) from current pipeline's FBO pool."""
        pipeline = self._get_current_pipeline()
        if pipeline is None:
            return {}

        result = {}
        for key in pipeline.get_fbo_keys():
            fbo = pipeline.get_fbo(key)
            if fbo is not None:
                result[key] = fbo
        return result

    def _get_current_pipeline(self):
        """Get pipeline from current viewport.

        For viewports managed by scene pipeline, returns the compiled pipeline
        from the scene. For regular viewports, returns viewport.pipeline.
        """
        if self._current_viewport is None:
            return None

        # Check if viewport is managed by a scene pipeline
        managed_by = self._current_viewport.managed_by_scene_pipeline
        if managed_by and self._current_viewport.scene is not None:
            # Get compiled pipeline from scene
            return self._current_viewport.scene.get_pipeline(managed_by)

        # Regular viewport - use viewport's own pipeline
        return self._current_viewport.pipeline

    def _update_fbo_info(self) -> None:
        """Обновляет информацию о текущем FBO."""
        fbos = self._get_fbos()
        resource_name = self._gl_widget._resource_name
        resource = fbos.get(resource_name) if fbos else None

        if resource is None:
            self._fbo_info_label.setText(f"Ресурс '{resource_name}': не найден")
            return

        info_parts = [f"<b>{resource_name}</b>"]

        # Определяем тип ресурса
        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        if isinstance(resource, ShadowMapArrayResource):
            info_parts.append(f"Тип: ShadowMapArray ({len(resource)} entries)")
            if len(resource) > 0:
                entry = resource[0]
                fbo = entry.fbo
                if fbo is not None:
                    w, h = fbo.get_size()
                    info_parts.append(f"Размер: {w}×{h}")
        elif isinstance(resource, SingleFBO):
            info_parts.append("Тип: SingleFBO")
            fbo = resource._fbo
            if fbo is not None:
                w, h = fbo.get_size()
                samples = fbo.get_samples()
                is_msaa = fbo.is_msaa()
                fmt = fbo.get_format()
                info_parts.append(f"Размер: {w}×{h}")
                info_parts.append(f"Формат: {fmt}")
                if is_msaa:
                    info_parts.append(f"<span style='color: #ffaa00;'>MSAA: {samples}x</span>")
                else:
                    info_parts.append("MSAA: нет")
                info_parts.append(f"FBO ID: {fbo.get_fbo_id()}")
                # Real GL parameters
                gl_fmt = fbo.get_actual_gl_format()
                gl_w = fbo.get_actual_gl_width()
                gl_h = fbo.get_actual_gl_height()
                gl_s = fbo.get_actual_gl_samples()
                info_parts.append(f"<span style='color: #88ff88;'>GL: {gl_fmt} {gl_w}×{gl_h} s={gl_s}</span>")
                # Filter info
                req_filter = fbo.get_filter()
                gl_filter = fbo.get_actual_gl_filter()
                info_parts.append(f"<span style='color: #88aaff;'>Filter: {req_filter} → {gl_filter}</span>")
        elif isinstance(resource, FramebufferHandle):
            info_parts.append("Тип: FramebufferHandle")
            w, h = resource.get_size()
            samples = resource.get_samples()
            is_msaa = resource.is_msaa()
            fmt = resource.get_format()
            info_parts.append(f"Размер: {w}×{h}")
            info_parts.append(f"Формат: {fmt}")
            if is_msaa:
                info_parts.append(f"<span style='color: #ffaa00;'>MSAA: {samples}x</span>")
            else:
                info_parts.append("MSAA: нет")
            info_parts.append(f"FBO ID: {resource.get_fbo_id()}")
            # Real GL parameters
            gl_fmt = resource.get_actual_gl_format()
            gl_w = resource.get_actual_gl_width()
            gl_h = resource.get_actual_gl_height()
            gl_s = resource.get_actual_gl_samples()
            info_parts.append(f"<span style='color: #88ff88;'>GL: {gl_fmt} {gl_w}×{gl_h} s={gl_s}</span>")
            # Filter info
            req_filter = resource.get_filter()
            gl_filter = resource.get_actual_gl_filter()
            info_parts.append(f"<span style='color: #88aaff;'>Filter: {req_filter} → {gl_filter}</span>")
        else:
            info_parts.append(f"Тип: {type(resource).__name__}")

        self._fbo_info_label.setText(" | ".join(info_parts))

    def _update_writer_pass_label(self) -> None:
        """Обновляет лейбл с именем пасса, который пишет выбранный ресурс."""
        resource_name = self._gl_widget._resource_name
        if not resource_name:
            self._writer_pass_label.setText("")
            return

        schedule = self._build_schedule(exclude_debugger=True)
        writer_pass = None
        for p in schedule:
            if resource_name in p.writes:
                writer_pass = p.pass_name
                break

        if writer_pass:
            self._writer_pass_label.setText(f"← {writer_pass}")
        else:
            self._writer_pass_label.setText("(read-only)")

    def _update_pass_serialization(self) -> None:
        """Обновляет отображение сериализации выбранного пасса."""
        import json

        if self._selected_pass is None:
            self._pass_serialization.clear()
            return

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            self._pass_serialization.setText("<no pipeline>")
            return

        # Find pass by name
        for p in pipeline.passes:
            if p.pass_name == self._selected_pass:
                try:
                    data = p.serialize()
                    text = json.dumps(data, indent=2, ensure_ascii=False)
                    self._pass_serialization.setText(text)
                except Exception as e:
                    self._pass_serialization.setText(f"<error: {e}>")
                return

        self._pass_serialization.setText(f"<pass '{self._selected_pass}' not found>")

    def _on_depth_image_updated(self, image: QtGui.QImage) -> None:
        if image is None or image.isNull():
            return
        if self._depth_label is None:
            return
        # Сбрасываем стиль ошибки
        self._depth_label.setStyleSheet("")
        self._depth_label.setText("")
        pixmap = QtGui.QPixmap.fromImage(image)
        target_size = self._depth_label.size()
        if target_size.width() > 0 and target_size.height() > 0:
            pixmap = pixmap.scaled(
                target_size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        self._depth_label.setPixmap(pixmap)

    def _on_depth_error_updated(self, message: str) -> None:
        if self._depth_label is None:
            return
        self._depth_label.clear()
        self._depth_label.setText(message)
        self._depth_label.setStyleSheet("color: #ff6666;")

    def _on_mode_changed(self, checked: bool) -> None:
        """Обработчик переключения режима."""
        if self._radio_inside.isChecked():
            self._mode = "inside"
            self._between_panel.hide()
            self._inside_panel.show()
            # Сбрасываем внутренний символ предыдущего пасса
            self._clear_internal_symbol()
            # Отключаем FrameDebuggerPass от пайплайна
            self._detach_frame_debugger_pass()
            # В режиме "Фреймпассы" скрываем UI обработчиков ресурсов
            self._resource_ui_container.hide()
            self._update_passes_list()
            # Обновляем сериализацию для выбранного пасса
            self._update_pass_serialization()
            # Очищаем окно дебаггера до выбора символа
            self._gl_widget.clear_to_background()
        else:
            self._mode = "between"
            self._between_panel.show()
            self._inside_panel.hide()
            # Сбрасываем внутренний символ
            self._clear_internal_symbol()
            # Подключаем FrameDebuggerPass к пайплайну
            self._attach_frame_debugger_pass()
            # Обновляем UI для типа ресурса (может показать UI обработчика)
            self._update_ui_for_resource_type()

        # Запрашиваем обновление depth для новой текстуры
        self._request_depth_refresh()

    def _attach_frame_debugger_pass(self) -> None:
        """Создаёт и добавляет FrameDebuggerPass в пайплайн текущего viewport."""
        from termin._native import log

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            log.warn("[FrameDebugger] _attach: no pipeline")
            return

        # Если уже есть — сначала удаляем
        self._detach_frame_debugger_pass()

        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        def get_source():
            if self._debug_paused:
                return None
            return self._debug_source_res

        self._frame_debugger_pass = FrameDebuggerPass(
            get_source_res=get_source,
            pass_name="FrameDebugger",
        )

        # Передаём SDL окно и depth callbacks
        sdl_window = self._gl_widget.get_sdl_window()
        depth_callback = self._gl_widget.on_depth_captured
        depth_error_callback = self._gl_widget.on_depth_error
        self._frame_debugger_pass.set_debugger_window(
            sdl_window, depth_callback, depth_error_callback
        )

        # Добавляем в конец пайплайна (после всех пассов)
        pipeline.add_pass(self._frame_debugger_pass)
        log.info(f"[FrameDebugger] Attached FrameDebuggerPass, pipeline has {len(pipeline.passes)} passes")

        if self._on_request_update is not None:
            self._on_request_update()

    def _detach_frame_debugger_pass(self) -> None:
        """Удаляет все FrameDebuggerPass из пайплайна по имени."""
        pipeline = self._get_current_pipeline()
        if pipeline is not None:
            removed = pipeline.remove_passes_by_name("FrameDebugger")
            if removed > 0:
                from termin._native import log
                log.info(f"[FrameDebugger] Removed {removed} FrameDebuggerPass(es), pipeline has {len(pipeline.passes)} passes")

        self._frame_debugger_pass = None

        if self._on_request_update is not None:
            self._on_request_update()

    def _on_resource_selected(self, name: str) -> None:
        """Обработчик выбора ресурса (режим «Между пассами»)."""
        if not name:
            return

        # Показываем выбранный ресурс напрямую
        self._debug_source_res = name
        self._gl_widget.set_resource_name(name)

        # Обновляем UI для типа ресурса
        self._update_ui_for_resource_type()

        # Обновляем информацию о FBO, пасс-писатель и подсветку в pipeline
        self._update_fbo_info()
        self._update_writer_pass_label()
        self._update_pipeline_info()

        # Сбрасываем HDR статистику при смене ресурса
        self._hdr_stats_label.setText("")

        # Запрашиваем обновление depth для новой текстуры
        self._request_depth_refresh()

    def _on_hdr_highlight_toggled(self, checked: bool) -> None:
        """Обработчик переключения подсветки HDR."""
        self._gl_widget.set_highlight_hdr(checked)
        # Также передаём в FrameDebuggerPass для режима "между пассами"
        if self._frame_debugger_pass is not None:
            self._frame_debugger_pass.set_highlight_hdr(checked)

    def _on_analyze_hdr_clicked(self) -> None:
        """Обработчик кнопки анализа HDR."""
        stats = self._gl_widget.compute_hdr_stats()
        if not stats:
            self._hdr_stats_label.setText("Unable to read texture")
            return

        # Format statistics
        lines = []
        lines.append(f"<b>R:</b> {stats['min_r']:.3f} - {stats['max_r']:.3f} (avg: {stats['avg_r']:.3f})")
        lines.append(f"<b>G:</b> {stats['min_g']:.3f} - {stats['max_g']:.3f} (avg: {stats['avg_g']:.3f})")
        lines.append(f"<b>B:</b> {stats['min_b']:.3f} - {stats['max_b']:.3f} (avg: {stats['avg_b']:.3f})")
        lines.append(f"<b>Max:</b> {stats['max_value']:.3f}")

        hdr_percent = stats.get('hdr_percent', 0)
        hdr_count = stats.get('hdr_pixel_count', 0)
        total = stats.get('total_pixels', 0)

        if hdr_percent > 0:
            hdr_color = "#ff69b4"  # Pink for HDR
            lines.append(f"<span style='color: {hdr_color};'><b>HDR pixels:</b> {hdr_count:,} ({hdr_percent:.2f}%)</span>")
        else:
            lines.append(f"<b>HDR pixels:</b> 0 (0%)")

        self._hdr_stats_label.setText("<br>".join(lines))

    def _on_pass_selected(self, name: str) -> None:
        """Обработчик выбора пасса (режим «Внутри пасса»)."""
        if not name:
            return
        # Сначала очищаем debugger window у предыдущего пасса
        self._clear_internal_symbol()
        # Извлекаем реальное имя пасса (без суффикса)
        idx = self._pass_combo.currentIndex()
        if idx >= 0:
            self._selected_pass = self._pass_combo.itemData(idx)
        # При ручном выборе пасса сбрасываем выбранный символ,
        # чтобы не тянуть его между разными пассами.
        self._selected_symbol = None
        self._update_symbols_list()
        # Обновляем сериализацию пасса
        self._update_pass_serialization()
        # Выбираем последний символ по умолчанию
        if self._symbol_combo.count() > 0:
            last_index = self._symbol_combo.count() - 1
            self._symbol_combo.setCurrentIndex(last_index)
            last_symbol = self._symbol_combo.itemText(last_index)
            self._on_symbol_selected(last_symbol)

    def _on_symbol_selected(self, name: str) -> None:
        """Обработчик выбора символа (режим «Внутри пасса»)."""
        if not name:
            return
        if self._selected_pass is None:
            return

        # Запоминаем выбранный символ
        self._selected_symbol = name

        # Убираем debugger pass если был
        self._detach_frame_debugger_pass()
        self._set_pass_internal_symbol(self._selected_pass, name)
        # Показываем timing label
        self._timing_label.show()
        self._update_timing_label()

        # Запрашиваем обновление depth для новой текстуры
        self._request_depth_refresh()

    def _update_timing_label(self) -> None:
        """Обновляет метку с информацией о времени выполнения символа."""
        if self._timing_label is None:
            return

        if self._selected_pass is None or self._selected_symbol is None:
            self._timing_label.hide()
            return

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            self._timing_label.hide()
            return

        # Находим пасс и получаем timing
        for p in pipeline.passes:
            if p.pass_name == self._selected_pass:
                timings = p.get_internal_symbols_with_timing()
                for t in timings:
                    if t.name == self._selected_symbol:
                        gpu_str = f"{t.gpu_time_ms:.3f}ms" if t.gpu_time_ms >= 0 else "pending..."
                        self._timing_label.setText(
                            f"CPU: {t.cpu_time_ms:.3f}ms | GPU: {gpu_str}"
                        )
                        self._timing_label.show()
                        return
                break

        # Нет данных timing
        self._timing_label.setText("Timing: no data")
        self._timing_label.show()

    def _on_pause_toggled(self, checked: bool) -> None:
        """Обработчик переключения паузы."""
        self._debug_paused = bool(checked)
        if self._on_request_update is not None:
            self._on_request_update()

    def _on_channel_changed(self, index: int) -> None:
        """Обработчик выбора канала для отображения."""
        self._gl_widget.set_channel_mode(index)
        # Также передаём в FrameDebuggerPass для режима "между пассами"
        if self._frame_debugger_pass is not None:
            self._frame_debugger_pass.set_channel_mode(index)

    def _request_depth_refresh(self) -> None:
        """Запрашивает обновление depth buffer и перерисовку."""
        if self._mode == "between":
            if self._frame_debugger_pass is not None:
                self._frame_debugger_pass.request_depth_update()
        else:
            self._gl_widget.request_depth_update()

        if self._on_request_update is not None:
            self._on_request_update()

    def _on_refresh_depth_clicked(self) -> None:
        """Обработчик кнопки обновления depth buffer."""
        self._request_depth_refresh()

    def _on_shadow_map_index_changed(self, index: int) -> None:
        """Обработчик смены индекса shadow map."""
        self._gl_widget.set_shadow_map_index(index)
        self._request_depth_refresh()

    def _clear_internal_symbol(self) -> None:
        """Сбрасывает внутренний символ у ВСЕХ пассов."""
        from termin._native import log

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            return

        cleared_count = 0
        for p in pipeline.passes:
            try:
                p.set_debug_internal_point("")
                p.set_debugger_window(None)
                cleared_count += 1
            except AttributeError:
                log.warn(f"[FrameDebugger] Pass '{p.pass_name}' does not support debug symbols")

        log.info(f"[FrameDebugger] _clear_internal_symbol: cleared {cleared_count} passes")

    def _set_pass_internal_symbol(self, pass_name: str, symbol: str | None) -> None:
        """Set internal debug symbol for a pass."""
        from termin._native import log

        pipeline = self._get_current_pipeline()
        if pipeline is None:
            log.warn(f"[FrameDebugger] _set_pass_internal_symbol: no pipeline")
            return

        for p in pipeline.passes:
            if p.pass_name == pass_name:
                pass_type = type(p).__name__
                if symbol is None or symbol == "":
                    # Отключаем внутреннюю точку дебага
                    p.set_debug_internal_point("")
                    p.set_debugger_window(None)
                    log.info(f"[FrameDebugger] Cleared debug symbol for pass '{pass_name}' ({pass_type})")
                else:
                    # Устанавливаем символ и передаём SDL окно для блита
                    p.set_debug_internal_point(symbol)

                    sdl_window = self._gl_widget.get_sdl_window()
                    depth_callback = self._gl_widget.on_depth_captured
                    depth_error_callback = self._gl_widget.on_depth_error
                    p.set_debugger_window(sdl_window, depth_callback, depth_error_callback)
                    log.info(f"[FrameDebugger] Set debug symbol '{symbol}' for pass '{pass_name}' ({pass_type})")

                if self._on_request_update is not None:
                    self._on_request_update()
                return

        log.warn(f"[FrameDebugger] Pass '{pass_name}' not found in pipeline")

    def _build_schedule(self, exclude_debugger: bool = False) -> list:
        """Строит schedule из текущего pipeline через FrameGraph.

        Args:
            exclude_debugger: Исключить FrameDebuggerPass из schedule.
                              Полезно для построения списка ресурсов, чтобы
                              порядок не менялся при смене выбранного ресурса.
        """
        pipeline = self._get_current_pipeline()
        if pipeline is None:
            return []

        from termin.visualization.render.framegraph.core import FrameGraph
        from termin.visualization.render.framegraph.passes.base import RenderFramePass
        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        # Фильтруем пассы если нужно исключить debugger
        passes = pipeline.passes
        if exclude_debugger:
            passes = [p for p in passes if not isinstance(p, FrameDebuggerPass)]

        # Вызываем required_resources() для динамических пассов (как в RenderEngine)
        for render_pass in passes:
            if isinstance(render_pass, RenderFramePass):
                render_pass.required_resources()

        graph = FrameGraph(passes)
        return graph.build_schedule()

    def _update_pipeline_info(self) -> None:
        """Обновляет информацию о pipeline schedule."""
        from termin.visualization.render.framegraph.passes.frame_debugger import FrameDebuggerPass

        schedule = self._build_schedule()
        if not schedule:
            self._pipeline_info.setHtml("<i>Pipeline пуст</i>")
            return

        # Текущий выбранный ресурс
        current_resource = self._gl_widget._resource_name if self._gl_widget else None

        lines = []
        for p in schedule:
            reads_str = ", ".join(sorted(p.reads)) if p.reads else "∅"
            writes_str = ", ".join(sorted(p.writes)) if p.writes else "∅"
            line = f"{p.pass_name}: {{{reads_str}}} → {{{writes_str}}}"

            if isinstance(p, FrameDebuggerPass):
                # Оранжевый для FrameDebuggerPass
                line = f"<span style='color: #ffb86c;'>► {line}</span>"
            elif current_resource and current_resource in p.writes:
                # Зелёный для пасса, который пишет текущий ресурс
                line = f"<span style='color: #50fa7b; font-weight: bold;'>● {line}</span>"

            lines.append(line)

        self._pipeline_info.setHtml("<pre>" + "<br>".join(lines) + "</pre>")

    def _update_resource_list(self) -> None:
        """Обновляет список ресурсов для режима «Между пассами»."""
        # Обновляем pipeline info
        self._update_pipeline_info()

        # Получаем schedule для определения порядка записи ресурсов
        # Исключаем FrameDebuggerPass, чтобы порядок не менялся при смене ресурса
        schedule = self._build_schedule(exclude_debugger=True)

        if schedule:
            # Сначала собираем все записываемые ресурсы
            written: set[str] = set()
            for p in schedule:
                written.update(p.writes)
            written.discard("DISPLAY")

            # Ресурсы, которые только читаются (никогда не пишутся) — в начало
            read_only: list[str] = []
            for p in schedule:
                for r in sorted(p.reads):
                    if r not in written and r != "DISPLAY" and r not in read_only:
                        read_only.append(r)

            # Затем ресурсы в порядке первой записи
            seen: set[str] = set()
            write_order: list[str] = []
            for p in schedule:
                for w in sorted(p.writes):
                    if w not in seen and w != "DISPLAY":
                        seen.add(w)
                        write_order.append(w)

            names = read_only + write_order
        else:
            names = sorted(self._get_fbos().keys())

        # Check if list changed - avoid clearing ComboBox while user interacts with it
        current_items = [self._resource_combo.itemText(i) for i in range(self._resource_combo.count())]
        if current_items == names:
            return

        current = self._resource_combo.currentText()
        self._resource_combo.blockSignals(True)
        self._resource_combo.clear()
        for name in names:
            self._resource_combo.addItem(name)
        if current and current in names:
            index = self._resource_combo.findText(current)
            if index >= 0:
                self._resource_combo.setCurrentIndex(index)
        self._resource_combo.blockSignals(False)

    def _update_passes_list(self) -> None:
        """Обновляет список пассов для режима «Внутри пасса»."""
        previous_pass = self._selected_pass

        passes_info: List[Tuple[str, bool]] = []

        # Get passes info from current pipeline
        pipeline = self._get_current_pipeline()
        if pipeline is not None:
            from termin.visualization.render.framegraph.passes.shadow import ShadowPass
            for p in pipeline.passes:
                if isinstance(p, ShadowPass):
                    has_symbols = False
                else:
                    symbols = p.get_internal_symbols()
                    has_symbols = len(symbols) > 0
                passes_info.append((p.pass_name, has_symbols))

        # Build new items list
        new_items = [(f"{name} ●" if has_sym else name, name) for name, has_sym in passes_info]

        # Check if list changed - avoid clearing ComboBox while user interacts with it
        current_items = [(self._pass_combo.itemText(i), self._pass_combo.itemData(i))
                         for i in range(self._pass_combo.count())]
        if current_items == new_items:
            return

        self._pass_combo.blockSignals(True)
        self._pass_combo.clear()

        selected_index = -1

        for index, (display_name, pass_name) in enumerate(new_items):
            self._pass_combo.addItem(display_name, pass_name)
            if previous_pass is not None and pass_name == previous_pass:
                selected_index = index

        self._pass_combo.blockSignals(False)

        # Если ранее выбранного пасса больше нет в списке, логический выбор оставляем,
        # но в комбобоксе явно не выделяем ничего.
        if previous_pass is not None and selected_index < 0:
            self._pass_combo.blockSignals(True)
            self._pass_combo.setCurrentIndex(-1)
            self._pass_combo.blockSignals(False)
            return

        # Инициализация выбора, если раньше его не было
        if previous_pass is None:
            if self._pass_combo.count() > 0:
                self._pass_combo.blockSignals(True)
                self._pass_combo.setCurrentIndex(0)
                self._selected_pass = self._pass_combo.itemData(0)
                self._pass_combo.blockSignals(False)
                self._update_symbols_list()
            return

        # Перерисовываем символы для ранее выбранного пасса, если он есть в списке
        if selected_index >= 0:
            self._pass_combo.blockSignals(True)
            self._pass_combo.setCurrentIndex(selected_index)
            self._pass_combo.blockSignals(False)
            self._update_symbols_list()

    def _update_symbols_list(self) -> None:
        """Обновляет список символов для выбранного пасса."""
        previous_symbol = self._selected_symbol

        symbols: List[str] = []

        # Get symbols from current pipeline
        if self._selected_pass:
            pipeline = self._get_current_pipeline()
            if pipeline is not None:
                for p in pipeline.passes:
                    if p.pass_name == self._selected_pass:
                        symbols = list(p.get_internal_symbols())
                        break

        # Check if list changed - avoid clearing ComboBox while user interacts with it
        current_items = [self._symbol_combo.itemText(i) for i in range(self._symbol_combo.count())]
        if current_items == symbols:
            return

        self._symbol_combo.blockSignals(True)
        self._symbol_combo.clear()

        selected_index = -1

        for index, sym in enumerate(symbols):
            self._symbol_combo.addItem(sym)
            if previous_symbol is not None and sym == previous_symbol:
                selected_index = index

        # Если ранее выбранного символа нет в новом списке, логический выбор не трогаем,
        # просто не выделяем ничего в комбобоксе.
        if previous_symbol is not None and selected_index < 0:
            self._symbol_combo.setCurrentIndex(-1)
        elif selected_index >= 0:
            self._symbol_combo.setCurrentIndex(selected_index)

        self._symbol_combo.setEnabled(len(symbols) > 0)
        self._symbol_combo.blockSignals(False)

    def _update_ui_for_resource_type(self) -> None:
        """
        Обновляет UI в зависимости от типа текущего ресурса.

        Использует обработчики ресурсов для создания и обновления специфичных UI элементов.
        """
        # Определяем тип текущего ресурса
        resource_type = self._gl_widget.get_resource_type()

        # Получаем обработчик для этого типа
        handler = self._gl_widget._handlers.get(resource_type) if resource_type else None

        # Если тип ресурса изменился, пересоздаём UI
        if handler != self._current_handler:
            # Удаляем старую UI панель
            if self._current_handler_ui is not None:
                self._resource_ui_layout.removeWidget(self._current_handler_ui)
                self._current_handler_ui.deleteLater()
                self._current_handler_ui = None

            self._current_handler = handler

            # Создаём новую UI панель, если обработчик требует
            if handler is not None:
                ui_panel = handler.create_ui_panel(self._resource_ui_container)
                if ui_panel is not None:
                    self._current_handler_ui = ui_panel
                    self._resource_ui_layout.addWidget(ui_panel)
                    self._resource_ui_container.show()

                    # Для ShadowMapArrayHandler устанавливаем callback
                    if isinstance(handler, ShadowMapArrayHandler):
                        handler.set_index_changed_callback(self._on_shadow_map_index_changed)
                else:
                    self._resource_ui_container.hide()
            else:
                self._resource_ui_container.hide()

        # Обновляем UI панель с текущим ресурсом
        if handler is not None and self._current_handler_ui is not None:
            fbos = self._gl_widget._get_fbos()
            resource = fbos.get(self._gl_widget._resource_name) if fbos else None
            handler.update_ui(resource, self._current_handler_ui)

    def _sync_pause_state(self) -> None:
        """Синхронизирует состояние чекбокса Pause с внутренним состоянием."""
        self._pause_check.blockSignals(True)
        self._pause_check.setChecked(self._debug_paused)
        self._pause_check.blockSignals(False)

    def set_initial_resource(self, resource_name: str) -> None:
        """
        Устанавливает начальный ресурс для отображения.

        Полезно для запуска дебаггера с определённым ресурсом с первого кадра.
        """
        self._debug_source_res = resource_name
        self._gl_widget.set_resource_name(resource_name)

        # Синхронизируем комбобокс
        index = self._resource_combo.findText(resource_name)
        if index >= 0:
            self._resource_combo.blockSignals(True)
            self._resource_combo.setCurrentIndex(index)
            self._resource_combo.blockSignals(False)

    def debugger_request_update(self) -> None:
        """
        Вызывается редактором при обновлении основного viewport.
        Обновляет списки и перерисовывает GL-виджет.
        """
        # Если диалог скрыт, не делаем ничего (особенно с GL контекстом!)
        if not self.isVisible():
            return

        self._update_resource_list()
        if self._mode == "inside":
            self._update_passes_list()
        self._sync_pause_state()
        self._update_ui_for_resource_type()
        self._update_fbo_info()
        # В режиме "между пассами" FrameDebuggerPass уже отрендерил в окно.
        # В режиме "внутри пасса" пасс с debug_internal_symbol рендерит в окно.
        # Если символ не выбран - очищаем до фона, чтобы не показывать старую текстуру.
        if self._mode == "inside" and not self._selected_symbol:
            self._gl_widget.clear_to_background()

    def refresh_for_new_scene(self) -> None:
        """
        Refresh debugger for a new scene while preserving selection.

        Called when editor attaches to a different scene (e.g., game mode switch).
        Preserves selected pass, symbol, and resource if they exist in the new scene.
        """
        # Save current selection
        saved_mode = self._mode
        saved_resource = self._debug_source_res
        saved_pass = self._selected_pass
        saved_symbol = self._selected_symbol

        # Detach from old pipeline
        self._detach_frame_debugger_pass()
        self._clear_internal_symbol()

        # Update viewport list (gets new viewports from rendering controller)
        self._update_viewport_list()
        self._update_resource_list()
        self._update_passes_list()

        # Try to restore resource selection
        if saved_resource:
            index = self._resource_combo.findText(saved_resource)
            if index >= 0:
                self._resource_combo.setCurrentIndex(index)
                self._debug_source_res = saved_resource
                self._gl_widget.set_resource_name(saved_resource)

        # Try to restore pass selection
        if saved_pass:
            for i in range(self._pass_combo.count()):
                if self._pass_combo.itemData(i) == saved_pass:
                    self._pass_combo.setCurrentIndex(i)
                    self._selected_pass = saved_pass
                    self._update_symbols_list()
                    break

        # Try to restore symbol selection
        if saved_symbol and self._selected_pass:
            index = self._symbol_combo.findText(saved_symbol)
            if index >= 0:
                self._symbol_combo.setCurrentIndex(index)
                self._selected_symbol = saved_symbol
                if saved_mode == "inside":
                    self._set_pass_internal_symbol(self._selected_pass, saved_symbol)

        # Reattach to new pipeline if in "between" mode
        if saved_mode == "between":
            self._attach_frame_debugger_pass()

        # Update UI
        self._update_fbo_info()
        self._update_writer_pass_label()
        self._update_pipeline_info()
        self._update_ui_for_resource_type()

    def showEvent(self, event) -> None:
        """При показе диалога инициализируем текущий режим."""
        super().showEvent(event)
        if self._mode == "between":
            self._attach_frame_debugger_pass()
        else:
            # Режим "Фреймпассы" - обновляем список пассов
            self._update_passes_list()
            self._update_pass_serialization()

    def hideEvent(self, event) -> None:
        """При скрытии диалога отключаем FrameDebuggerPass."""
        self._detach_frame_debugger_pass()
        # Также сбрасываем внутренний символ для режима "Фреймпассы"
        self._clear_internal_symbol()
        super().hideEvent(event)
