from __future__ import annotations

from typing import Optional

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
        resource_name: str = "color",
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

        self._vao = vao
        self._vbo = vbo

    def initializeGL(self) -> None:
        """
        Qt создал контекст, здесь можно инициализировать ресурсы.
        """
        self._graphics.ensure_ready()
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

        if fb is None:
            # Пока нет FBO – просто фон.
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
    Окно-дебагер: внутри одно GL-окно, которое показывает текстуру из framegraph
    (ресурс resource_name из viewport.fbos).
    """

    def __init__(
        self,
        graphics: GraphicsBackend,
        viewport: Viewport,
        resource_name: str = "color",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._graphics = graphics
        self._viewport = viewport
        self._resource_name = resource_name

        self.setWindowTitle(f"Framegraph texture: {resource_name}")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setModal(False)
        self.setMinimumSize(400, 300)

        layout = QtWidgets.QVBoxLayout(self)
        self._gl_widget = FramegraphTextureWidget(
            graphics=self._graphics,
            viewport=self._viewport,
            resource_name=self._resource_name,
            parent=self,
        )
        layout.addWidget(self._gl_widget)

    def request_update(self) -> None:
        """
        Редактор может вызвать это, чтобы запросить перерисовку окна
        при обновлении основного viewport.
        """
        self._gl_widget.update()
