from __future__ import annotations

from typing import Optional, Callable, List, Tuple

from PyQt5 import QtWidgets, QtCore

from OpenGL import GL as gl

from termin.visualization.platform.backends.base import GraphicsBackend
from termin.visualization.core.viewport import Viewport
from termin.visualization.render.shader import ShaderProgram


class FramegraphTextureWidget(QtWidgets.QOpenGLWidget):
    """
    QOpenGLWidget, который берёт FBO из viewport.fbos и рисует его color-текстуру
    фуллскрин-квадом. Работает напрямую через OpenGL, без участия Window/FrameGraph.
    """

    def __init__(
        self,
        graphics: GraphicsBackend,
        viewport: Viewport,
        resource_name: str = "debug",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._graphics = graphics
        self._viewport = viewport
        self._resource_name = resource_name

        self._shader: Optional[ShaderProgram] = None
        self._vao: Optional[int] = None
        self._vbo: Optional[int] = None

        self.setMinimumSize(200, 150)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(400, 300)

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
            out vec4 FragColor;
            void main()
            {
                FragColor = texture(u_tex, v_uv);
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

    def initializeGL(self) -> None:
        self._get_shader()
        self._init_fullscreen_quad()

    def _current_fbo(self):
        if self._viewport is None:
            return None
        fbos = self._viewport.fbos
        if not fbos:
            return None
        if self._resource_name not in fbos:
            return None
        return fbos[self._resource_name]

    def paintGL(self) -> None:
        fb = self._current_fbo()

        dpr = self.devicePixelRatioF()
        w = int(self.width() * dpr)
        h = int(self.height() * dpr)

        gl.glViewport(0, 0, w, h)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        if fb is None:
            return

        tex = fb.color_texture()

        shader = self._get_shader()
        shader.use()
        shader.set_uniform_int("u_tex", 0)

        tex.bind(0)

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)

        self._init_fullscreen_quad()
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)

        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_DEPTH_TEST)


class FramegraphDebugDialog(QtWidgets.QDialog):
    """
    Окно-дебагер framegraph с двумя режимами подключения:

    1. «Между пассами» — выбираем промежуточный ресурс (FBO) между пассами.
       Используется BlitPass для копирования выбранного ресурса в debug FBO.

    2. «Внутри пасса» — выбираем пасс и его внутренний символ.
       Например, для ColorPass можно выбрать меш и увидеть состояние
       рендера после его отрисовки.

    UI:
    - Группа радиокнопок для выбора режима
    - Панель для режима «Между пассами»: ComboBox с ресурсами
    - Панель для режима «Внутри пасса»: ComboBox пассов + ComboBox символов
    - Чекбокс паузы
    - GL-виджет с текстурой
    """

    def __init__(
        self,
        graphics: GraphicsBackend,
        viewport: Viewport,
        resource_name: str = "debug",
        parent: Optional[QtWidgets.QWidget] = None,
        # Колбэки для режима «Между пассами»
        get_available_resources: Optional[Callable[[], List[str]]] = None,
        set_source_resource: Optional[Callable[[str], None]] = None,
        # Общие колбэки
        get_paused: Optional[Callable[[], bool]] = None,
        set_paused: Optional[Callable[[bool], None]] = None,
        # Колбэки для режима «Внутри пасса»
        # Возвращает список (pass_name, has_internal_symbols)
        get_passes_info: Optional[Callable[[], List[Tuple[str, bool]]]] = None,
        # Возвращает список символов для выбранного пасса
        get_pass_internal_symbols: Optional[Callable[[str], List[str]]] = None,
        # Устанавливает внутренний символ для пасса (pass_name, symbol)
        set_pass_internal_symbol: Optional[Callable[[str, str | None], None]] = None,
        # Геттер для BlitPass (чтобы управлять им напрямую)
        get_debug_blit_pass: Optional[Callable[[], object]] = None,
    ) -> None:
        super().__init__(parent)
        self._graphics = graphics
        self._viewport = viewport
        self._resource_name = resource_name

        # Колбэки для режима «Между пассами»
        self._get_available_resources = get_available_resources
        self._set_source_resource = set_source_resource
        self._get_debug_blit_pass = get_debug_blit_pass

        # Общие колбэки
        self._get_paused = get_paused
        self._set_paused = set_paused

        # Колбэки для режима «Внутри пасса»
        self._get_passes_info = get_passes_info
        self._get_pass_internal_symbols = get_pass_internal_symbols
        self._set_pass_internal_symbol = set_pass_internal_symbol

        # Текущий режим: "between" или "inside"
        self._mode = "between"
        # Текущий выбранный пасс (для режима «Внутри пасса»)
        self._selected_pass: str | None = None
        # Текущий выбранный внутренний символ (для режима «Внутри пасса»)
        self._selected_symbol: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Framegraph Debugger")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setModal(False)
        self.setMinimumSize(450, 400)

        layout = QtWidgets.QVBoxLayout(self)

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

        # ============ Пауза ============
        self._pause_check = QtWidgets.QCheckBox("Пауза")
        self._pause_check.toggled.connect(self._on_pause_toggled)
        layout.addWidget(self._pause_check)

        # ============ GL-виджет ============
        self._gl_widget = FramegraphTextureWidget(
            graphics=self._graphics,
            viewport=self._viewport,
            resource_name=self._resource_name,
            parent=self,
        )
        layout.addWidget(self._gl_widget, 1)

        # Инициализация
        self._update_resource_list()
        self._update_passes_list()
        self._sync_pause_state()

    def _on_mode_changed(self, checked: bool) -> None:
        """Обработчик переключения режима."""
        if self._radio_between.isChecked():
            self._mode = "between"
            self._between_panel.show()
            self._inside_panel.hide()
            # Сбрасываем внутренний символ
            self._clear_internal_symbol()
        else:
            self._mode = "inside"
            self._between_panel.hide()
            self._inside_panel.show()
            self._update_passes_list()

    def _on_resource_selected(self, name: str) -> None:
        """Обработчик выбора ресурса (режим «Между пассами»).
        
        Напрямую обновляет reads у BlitPass, чтобы граф зависимостей
        корректно выстроил порядок пассов до вызова request_update.
        """
        if not name:
            return
        # Обновляем reads у BlitPass напрямую
        if self._get_debug_blit_pass is not None:
            blit_pass = self._get_debug_blit_pass()
            if blit_pass is not None:
                blit_pass.reads = {name}
        # Устанавливаем источник и запрашиваем обновление
        if self._set_source_resource is not None:
            self._set_source_resource(name)

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
        if self._set_pass_internal_symbol is not None:
            self._set_pass_internal_symbol(self._selected_pass, name)

    def _on_pause_toggled(self, checked: bool) -> None:
        """Обработчик переключения паузы."""
        if self._set_paused is not None:
            self._set_paused(bool(checked))

    def _clear_internal_symbol(self) -> None:
        """Сбрасывает внутренний символ при переключении режима."""
        if self._set_pass_internal_symbol is not None and self._selected_pass:
            self._set_pass_internal_symbol(self._selected_pass, None)

    def _update_resource_list(self) -> None:
        """Обновляет список ресурсов для режима «Между пассами»."""
        if self._get_available_resources is not None:
            names = self._get_available_resources()
        else:
            names = list(self._viewport.fbos.keys())

        # Фильтруем debug — его не показываем как источник
        names = [n for n in names if n != "debug"]
        
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

        if self._get_passes_info is not None:
            passes_info = self._get_passes_info()

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

        if self._get_pass_internal_symbols is not None and self._selected_pass:
            symbols = self._get_pass_internal_symbols(self._selected_pass)

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

    def _sync_pause_state(self) -> None:
        """Синхронизирует состояние чекбокса Pause с внешним состоянием."""
        if self._get_paused is None:
            return
        value = bool(self._get_paused())
        self._pause_check.blockSignals(True)
        self._pause_check.setChecked(value)
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
        self._gl_widget.update()
