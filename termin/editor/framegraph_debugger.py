from __future__ import annotations

from typing import Optional, Callable, List, Tuple, TYPE_CHECKING
from abc import ABC, abstractmethod

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QWindow

from OpenGL import GL as gl
import numpy as np

from termin.visualization.platform.backends.base import GraphicsBackend
from termin.visualization.render.shader import ShaderProgram

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import TextureHandle
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
    def get_texture(self, resource, context: dict) -> "TextureHandle | None":
        """
        Извлекает текстуру из ресурса для отображения.

        Args:
            resource: объект ресурса (SingleFBO, ShadowMapArrayResource и т.д.)
            context: контекст с дополнительной информацией (например, индекс shadow map)

        Returns:
            TextureHandle или None
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

    def get_texture(self, resource, context: dict) -> "TextureHandle | None":
        """Возвращает color_texture из SingleFBO."""
        if resource is None:
            return None
        if hasattr(resource, 'color_texture'):
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

    def get_texture(self, resource, context: dict) -> "TextureHandle | None":
        """
        Возвращает текстуру из выбранного entry в ShadowMapArray.

        context должен содержать 'shadow_map_index' — индекс выбранного shadow map.
        """
        if resource is None:
            return None

        shadow_map_index = context.get('shadow_map_index', 0)

        # Проверяем, что это ShadowMapArrayResource
        if not hasattr(resource, '__len__') or not hasattr(resource, '__getitem__'):
            return None

        if len(resource) == 0:
            return None

        # Ограничиваем индекс размером массива
        index = min(shadow_map_index, len(resource) - 1)
        entry = resource[index]

        if hasattr(entry, 'texture'):
            return entry.texture()

        return None

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

        # Получаем количество shadow maps
        count = len(resource) if hasattr(resource, '__len__') else 0

        # Блокируем сигналы при обновлении
        self._combo.blockSignals(True)
        self._combo.clear()

        if count > 0:
            for i in range(count):
                # Пытаемся получить информацию об источнике света
                try:
                    entry = resource[i]
                    light_index = entry.light_index if hasattr(entry, 'light_index') else i
                    self._combo.addItem(f"Light {light_index}", i)
                except (IndexError, AttributeError, TypeError):
                    self._combo.addItem(f"Shadow Map {i}", i)

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

        self._shader: Optional[ShaderProgram] = None
        self._vao: Optional[int] = None
        self._vbo: Optional[int] = None
        self._initialized = False
        self._channel_mode: int = 0  # 0=RGB, 1=R, 2=G, 3=B, 4=A

        # Captured depth для режима "внутри пасса" (передаётся через callback)
        self._captured_depth: Optional[np.ndarray] = None

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

    def _get_shader(self) -> ShaderProgram:
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
            out vec4 FragColor;
            void main()
            {
                vec4 c = texture(u_tex, v_uv);
                if (u_channel == 1) {
                    FragColor = vec4(c.r, c.r, c.r, 1.0);
                } else if (u_channel == 2) {
                    FragColor = vec4(c.g, c.g, c.g, 1.0);
                } else if (u_channel == 3) {
                    FragColor = vec4(c.b, c.b, c.b, 1.0);
                } else if (u_channel == 4) {
                    FragColor = vec4(c.a, c.a, c.a, 1.0);
                } else {
                    FragColor = vec4(c.rgb, 1.0);
                }
            }
            """
            self._shader = ShaderProgram(vert_src, frag_src)
            self._shader.ensure_ready(self._graphics)
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
            TextureHandle или None
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

    def get_resource_type(self) -> str | None:
        """
        Возвращает тип текущего ресурса.

        Returns:
            "fbo", "shadow_map_array" или None
        """
        resource = self._current_resource()
        if resource is None:
            return None
        if hasattr(resource, 'resource_type'):
            return resource.resource_type
        return None

    def _update_depth_image(self) -> None:
        """Read depth buffer from current FBO and emit as QImage."""
        resource = self._current_resource()
        if resource is None:
            return

        # Read depth directly from FBO
        depth = self._graphics.read_depth_buffer(resource)
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

    def render(self) -> None:
        """Рендерит текстуру в SDL окно."""
        self._ensure_initialized()
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
            return

        shader = self._get_shader()
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        shader.set_uniform_int("u_channel", self._channel_mode)

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
        self._update_depth_image()

    def update(self) -> None:
        """Переопределяем update() для вызова render()."""
        super().update()
        self.render()

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

        # Текущий режим: "between" или "inside"
        self._mode = "between"
        # Текущий выбранный пасс (для режима «Внутри пасса»)
        self._selected_pass: str | None = None
        # Текущий выбранный внутренний символ (для режима «Внутри пасса»)
        self._selected_symbol: str | None = None

        # Debug source resource name (for "between passes" mode)
        self._debug_source_res: str = "color_pp"
        # Paused state
        self._debug_paused: bool = False

        # FrameDebuggerPass для режима "между пассами" (создаётся динамически)
        self._frame_debugger_pass = None

        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Framegraph Debugger")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setModal(False)
        self.setMinimumSize(450, 400)

        layout = QtWidgets.QVBoxLayout(self)

        # ============ Выбор viewport ============
        viewport_row = QtWidgets.QHBoxLayout()
        viewport_label = QtWidgets.QLabel("Viewport:")
        self._viewport_combo = QtWidgets.QComboBox()
        self._viewport_combo.currentIndexChanged.connect(self._on_viewport_selected)
        viewport_row.addWidget(viewport_label)
        viewport_row.addWidget(self._viewport_combo, 1)
        layout.addLayout(viewport_row)

        # ============ Группа выбора режима ============
        mode_group = QtWidgets.QGroupBox("Режим подключения")
        mode_layout = QtWidgets.QVBoxLayout(mode_group)
        self._radio_between = QtWidgets.QRadioButton("Между пассами (ресурс FBO)")
        self._radio_inside = QtWidgets.QRadioButton("Внутри пасса (символ)")
        self._radio_between.setChecked(True)

        self._radio_between.toggled.connect(self._on_mode_changed)

        mode_layout.addWidget(self._radio_between)
        mode_layout.addWidget(self._radio_inside)
        layout.addWidget(mode_group)

        # ============ Панель «Между пассами» ============
        self._between_panel = QtWidgets.QWidget()
        between_layout = QtWidgets.QHBoxLayout(self._between_panel)
        between_layout.setContentsMargins(0, 0, 0, 0)

        self._resource_label = QtWidgets.QLabel("Ресурс:")
        self._resource_combo = QtWidgets.QComboBox()
        self._resource_combo.currentTextChanged.connect(self._on_resource_selected)
        between_layout.addWidget(self._resource_label)
        between_layout.addWidget(self._resource_combo, 1)
        layout.addWidget(self._between_panel)

        # ============ Панель «Внутри пасса» ============
        self._inside_panel = QtWidgets.QWidget()
        inside_layout = QtWidgets.QVBoxLayout(self._inside_panel)
        inside_layout.setContentsMargins(0, 0, 0, 0)
        # Выбор пасса
        pass_row = QtWidgets.QHBoxLayout()
        self._pass_label = QtWidgets.QLabel("Пасс:")
        self._pass_combo = QtWidgets.QComboBox()
        self._pass_combo.currentTextChanged.connect(self._on_pass_selected)
        pass_row.addWidget(self._pass_label)
        pass_row.addWidget(self._pass_combo, 1)
        inside_layout.addLayout(pass_row)
        # Выбор символа
        symbol_row = QtWidgets.QHBoxLayout()
        self._symbol_label = QtWidgets.QLabel("Символ:")
        self._symbol_combo = QtWidgets.QComboBox()
        self._symbol_combo.currentTextChanged.connect(self._on_symbol_selected)
        symbol_row.addWidget(self._symbol_label)
        symbol_row.addWidget(self._symbol_combo, 1)
        inside_layout.addLayout(symbol_row)
        layout.addWidget(self._inside_panel)
        self._inside_panel.hide()  # По умолчанию скрыта

        # ============ Контейнер для динамических UI панелей обработчиков ресурсов ============
        self._resource_ui_container = QtWidgets.QWidget()
        self._resource_ui_layout = QtWidgets.QVBoxLayout(self._resource_ui_container)
        self._resource_ui_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._resource_ui_container)
        self._resource_ui_container.hide()  # По умолчанию скрыт

        # Текущая UI панель обработчика
        self._current_handler_ui: QtWidgets.QWidget | None = None
        self._current_handler: ResourceHandler | None = None

        # ============ Пауза и выбор канала ============
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

        layout.addLayout(controls_row)

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

        depth_title = QtWidgets.QLabel("Depth Buffer")
        depth_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        depth_layout.addWidget(depth_title)

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

        # Инициализация
        self._update_viewport_list()
        self._update_resource_list()
        self._update_passes_list()
        self._sync_pause_state()

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

        # Update GL widget resource based on pipeline capabilities
        self._update_gl_widget_resource()

        # Подключаем к новому viewport если режим "между пассами"
        if self._mode == "between":
            self._attach_frame_debugger_pass()

        # Request render update for new viewport
        if self._on_request_update is not None:
            self._on_request_update()

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

    # ============ Data access helpers ============

    def _get_current_render_state(self):
        """Get ViewportRenderState for current viewport."""
        if self._current_viewport is None or self._rendering_controller is None:
            return None
        return self._rendering_controller.get_viewport_state(self._current_viewport)

    def _get_fbos(self) -> dict:
        """Get FBOs dict from current viewport's render state."""
        state = self._get_current_render_state()
        if state is None:
            return {}
        return state.fbos

    def _get_current_pipeline(self):
        """Get pipeline from current viewport's render state."""
        state = self._get_current_render_state()
        if state is None:
            return None
        return state.pipeline

    def _on_depth_image_updated(self, image: QtGui.QImage) -> None:
        if image is None or image.isNull():
            return
        if not hasattr(self, "_depth_label"):
            return
        pixmap = QtGui.QPixmap.fromImage(image)
        target_size = self._depth_label.size()
        if target_size.width() > 0 and target_size.height() > 0:
            pixmap = pixmap.scaled(
                target_size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        self._depth_label.setPixmap(pixmap)

    def _on_mode_changed(self, checked: bool) -> None:
        """Обработчик переключения режима."""
        if self._radio_between.isChecked():
            self._mode = "between"
            self._between_panel.show()
            self._inside_panel.hide()
            # Сбрасываем внутренний символ
            self._clear_internal_symbol()
            # Подключаем FrameDebuggerPass к пайплайну
            self._attach_frame_debugger_pass()
            # Обновляем UI для типа ресурса (может показать UI обработчика)
            self._update_ui_for_resource_type()
        else:
            self._mode = "inside"
            self._between_panel.hide()
            self._inside_panel.show()
            # Отключаем FrameDebuggerPass от пайплайна
            self._detach_frame_debugger_pass()
            # В режиме "Внутри пасса" скрываем UI обработчиков ресурсов
            self._resource_ui_container.hide()
            self._update_passes_list()

    def _attach_frame_debugger_pass(self) -> None:
        """Создаёт и добавляет FrameDebuggerPass в пайплайн текущего viewport."""
        pipeline = self._get_current_pipeline()
        if pipeline is None:
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

        # Передаём SDL окно и depth callback
        sdl_window = self._gl_widget.get_sdl_window()
        depth_callback = self._gl_widget.on_depth_captured
        self._frame_debugger_pass.set_debugger_window(sdl_window, depth_callback)

        # Добавляем в конец пайплайна (после всех пассов)
        pipeline.passes.append(self._frame_debugger_pass)

        if self._on_request_update is not None:
            self._on_request_update()

    def _detach_frame_debugger_pass(self) -> None:
        """Удаляет FrameDebuggerPass из пайплайна."""
        if self._frame_debugger_pass is None:
            return

        pipeline = self._get_current_pipeline()
        if pipeline is not None and self._frame_debugger_pass in pipeline.passes:
            pipeline.passes.remove(self._frame_debugger_pass)

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

        # Запрашиваем обновление
        if self._on_request_update is not None:
            self._on_request_update()

        # Обновляем UI для типа ресурса
        self._update_ui_for_resource_type()

    def _on_pass_selected(self, name: str) -> None:
        """Обработчик выбора пасса (режим «Внутри пасса»)."""
        if not name:
            return
        # Извлекаем реальное имя пасса (без суффикса)
        idx = self._pass_combo.currentIndex()
        if idx >= 0:
            self._selected_pass = self._pass_combo.itemData(idx)
        # При ручном выборе пасса сбрасываем выбранный символ,
        # чтобы не тянуть его между разными пассами.
        self._selected_symbol = None
        self._update_symbols_list()

    def _on_symbol_selected(self, name: str) -> None:
        """Обработчик выбора символа (режим «Внутри пасса»)."""
        if not name:
            return
        if self._selected_pass is None:
            return
        # Запоминаем выбранный внутренний символ для последующих обновлений списка.
        self._selected_symbol = name
        self._set_pass_internal_symbol(self._selected_pass, name)

    def _on_pause_toggled(self, checked: bool) -> None:
        """Обработчик переключения паузы."""
        self._debug_paused = bool(checked)
        if self._on_request_update is not None:
            self._on_request_update()

    def _on_channel_changed(self, index: int) -> None:
        """Обработчик выбора канала для отображения."""
        self._gl_widget.set_channel_mode(index)

    def _clear_internal_symbol(self) -> None:
        """Сбрасывает внутренний символ при переключении режима."""
        if self._selected_pass:
            self._set_pass_internal_symbol(self._selected_pass, None)

    def _set_pass_internal_symbol(self, pass_name: str, symbol: str | None) -> None:
        """Set internal debug symbol for a pass."""
        pipeline = self._get_current_pipeline()
        if pipeline is None:
            return

        for p in pipeline.passes:
            if p.pass_name == pass_name:
                if symbol is None or symbol == "":
                    # Отключаем внутреннюю точку дебага
                    p.set_debug_internal_point(None)
                    p.set_debugger_window(None, None)
                else:
                    # Устанавливаем символ и передаём SDL окно для блита
                    p.set_debug_internal_point(symbol)
                    sdl_window = self._gl_widget.get_sdl_window()
                    depth_callback = self._gl_widget.on_depth_captured
                    p.set_debugger_window(sdl_window, depth_callback)

                if self._on_request_update is not None:
                    self._on_request_update()
                return

    def _update_resource_list(self) -> None:
        """Обновляет список ресурсов для режима «Между пассами»."""
        # Get resources from pipeline
        pipeline = self._get_current_pipeline()
        if pipeline is not None:
            resources: set[str] = set()
            for p in pipeline.passes:
                resources.update(p.reads)
                resources.update(p.writes)
            resources.discard("DISPLAY")
            names = sorted(resources)
        else:
            names = list(self._get_fbos().keys())

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

        self._pass_combo.blockSignals(True)
        self._pass_combo.clear()

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

        selected_index = -1

        for index, (pass_name, has_symbols) in enumerate(passes_info):
            suffix = " ●" if has_symbols else ""
            self._pass_combo.addItem(pass_name + suffix, pass_name)
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

        self._symbol_combo.blockSignals(True)
        self._symbol_combo.clear()

        symbols: List[str] = []

        # Get symbols from current pipeline
        if self._selected_pass:
            pipeline = self._get_current_pipeline()
            if pipeline is not None:
                for p in pipeline.passes:
                    if p.pass_name == self._selected_pass:
                        symbols = p.get_internal_symbols()
                        break

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
                        handler.set_index_changed_callback(self._gl_widget.set_shadow_map_index)
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

    def debugger_request_update(self) -> None:
        """
        Вызывается редактором при обновлении основного viewport.
        Обновляет списки и перерисовывает GL-виджет.
        """
        self._update_resource_list()
        if self._mode == "inside":
            self._update_passes_list()
        self._sync_pause_state()
        self._update_ui_for_resource_type()
        # В режиме "между пассами" не вызываем _gl_widget.update(),
        # т.к. FrameDebuggerPass уже отрендерил в окно
        if self._mode == "inside":
            self._gl_widget.update()

    def showEvent(self, event) -> None:
        """При показе диалога подключаем FrameDebuggerPass если нужно."""
        super().showEvent(event)
        if self._mode == "between":
            self._attach_frame_debugger_pass()

    def hideEvent(self, event) -> None:
        """При скрытии диалога отключаем FrameDebuggerPass."""
        self._detach_frame_debugger_pass()
        # Также сбрасываем внутренний символ для режима "внутри пасса"
        self._clear_internal_symbol()
        super().hideEvent(event)
