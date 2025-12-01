from __future__ import annotations

from typing import Optional, Callable

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
        """
        Ленивая инициализация шейдера фуллскрин-квада.
        """
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
            # Компилируем шейдер через тот же graphics, что и движок
            self._shader.ensure_ready(self._graphics)
        return self._shader

    def _init_fullscreen_quad(self) -> None:
        """
        Создаёт VAO/VBO для quad'а (позиции + UV).
        """
        if self._vao is not None:
            return

        # x, y, u, v (triangle strip)
        data = [
            -1.0, -1.0, 0.0, 0.0,
            1.0, -1.0, 1.0, 0.0,
            -1.0,  1.0, 0.0, 1.0,
            1.0,  1.0, 1.0, 1.0,
        ]
        import array
        arr = array.array("f", data)

        vao = gl.glGenVertexArrays(1)
        vbo = gl.glGenBuffers(1)

        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, arr.tobytes(), gl.GL_STATIC_DRAW)

        stride = 4 * 4  # 4 float на вершину
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, gl.ctypes.c_void_p(8))

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glBindVertexArray(0)

        print("Initialized fullscreen quad VAO/VBO:", vao, vbo)
        self._vao = vao
        self._vbo = vbo

    def initializeGL(self) -> None:
        """
        Qt создал контекст, здесь можно инициализировать ресурсы.
        """
        self._get_shader()
        self._init_fullscreen_quad()

    def _current_fbo(self):
        """
        Берёт FBO по имени ресурса из viewport.fbos.
        """
        if self._viewport is None:
            return None
        fbos = self._viewport.fbos
        if not fbos:
            return None
        if self._resource_name not in fbos:
            return None
        return fbos[self._resource_name]

    def paintGL(self) -> None:
        """
        Рисуем содержимое FBO как текстуру на фуллскрин-квад.
        """
        fb = self._current_fbo()

        dpr = self.devicePixelRatioF()
        w = int(self.width() * dpr)
        h = int(self.height() * dpr)

        gl.glViewport(0, 0, w, h)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        print("Painting FBO texture:", self._resource_name, "FBO:", fb)
        if fb is None:
            # Пока нет FBO – просто фон.
            return

        tex = fb.color_texture()

        shader = self._get_shader()
        shader.use()
        shader.set_uniform_int("u_tex", 0)

        print("Binding texture:", tex)
        tex.bind(0)

        print("glIsTexture:", tex._tex_id, gl.glIsTexture(tex._tex_id))

        w = gl.glGetTexLevelParameteriv(gl.GL_TEXTURE_2D, 0, gl.GL_TEXTURE_WIDTH)
        h = gl.glGetTexLevelParameteriv(gl.GL_TEXTURE_2D, 0, gl.GL_TEXTURE_HEIGHT)
        print("debug tex size:", w, h)

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)

        self._init_fullscreen_quad()
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)

        print("Finished drawing fullscreen quad")

        gl.glDepthMask(gl.GL_TRUE)
        gl.glEnable(gl.GL_DEPTH_TEST)

class FramegraphDebugDialog(QtWidgets.QDialog):
    """
    Окно-дебагер: внутри одно GL-окно, которое показывает текстуру из framegraph
    (ресурс resource_name из viewport.fbos), плюс панель управления:
    выбор ресурса и кнопка паузы.
    """

    def __init__(
        self,
        graphics: GraphicsBackend,
        viewport: Viewport,
        resource_name: str = "debug",
        parent: Optional[QtWidgets.QWidget] = None,
        get_available_resources: Optional[Callable[[], list[str]]] = None,
        set_source_resource: Optional[Callable[[str], None]] = None,
        get_paused: Optional[Callable[[], bool]] = None,
        set_paused: Optional[Callable[[bool], None]] = None,
    ) -> None:
        super().__init__(parent)

        self._graphics = graphics
        self._viewport = viewport
        self._resource_name = resource_name

        self._get_available_resources = get_available_resources
        self._set_source_resource = set_source_resource
        self._get_paused = get_paused
        self._set_paused = set_paused

        self.setWindowTitle(f"Framegraph texture: {resource_name}")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setModal(False)
        self.setMinimumSize(400, 300)

        layout = QtWidgets.QVBoxLayout(self)

        controls_layout = QtWidgets.QHBoxLayout()
        self._resource_label = QtWidgets.QLabel("Resource:", self)
        self._resource_combo = QtWidgets.QComboBox(self)
        self._resource_combo.currentTextChanged.connect(self._on_resource_selected)
        self._pause_check = QtWidgets.QCheckBox("Pause", self)
        self._pause_check.toggled.connect(self._on_pause_toggled)

        controls_layout.addWidget(self._resource_label)
        controls_layout.addWidget(self._resource_combo, 1)
        controls_layout.addWidget(self._pause_check)
        layout.addLayout(controls_layout)

        self._gl_widget = FramegraphTextureWidget(
            graphics=self._graphics,
            viewport=self._viewport,
            resource_name=self._resource_name,
            parent=self,
        )
        layout.addWidget(self._gl_widget)

        # инициализируем список ресурсов и состояние паузы
        self._update_resource_list()
        self._sync_pause_state()

    def _update_resource_list(self) -> None:
        """
        Обновляет список доступных ресурсов framegraph в комбобоксе.
        """
        if not hasattr(self, "_resource_combo"):
            return

        if self._get_available_resources is not None:
            names = self._get_available_resources()
        else:
            names = list(self._viewport.fbos.keys())

        names = sorted(set(names))

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

    def _sync_pause_state(self) -> None:
        """
        Синхронизирует состояние чекбокса Pause с внешним состоянием.
        """
        if self._get_paused is None or not hasattr(self, "_pause_check"):
            return
        value = bool(self._get_paused())
        self._pause_check.blockSignals(True)
        self._pause_check.setChecked(value)
        self._pause_check.blockSignals(False)

    def _on_resource_selected(self, name: str) -> None:
        """
        Обработчик выбора ресурса в комбобоксе: прокидывает имя в BlitPass.
        """
        if not name:
            return
        if self._set_source_resource is not None:
            self._set_source_resource(name)

    def _on_pause_toggled(self, checked: bool) -> None:
        """
        Обработчик переключения паузы: обновляет флаг для BlitPass.
        """
        if self._set_paused is not None:
            self._set_paused(bool(checked))

    def request_update(self) -> None:
        """
        Редактор может вызвать это, чтобы запросить перерисовку окна
        при обновлении основного viewport.
        Также здесь обновляем список ресурсов и состояние паузы.
        """
        self._update_resource_list()
        self._sync_pause_state()
        self._gl_widget.update()