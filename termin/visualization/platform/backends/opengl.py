"""OpenGL-based graphics backend."""

from __future__ import annotations

import ctypes
from typing import Callable, Dict, Tuple

import numpy as np
from OpenGL import GL as gl
from OpenGL import GL as GL
from OpenGL.raw.GL.VERSION.GL_2_0 import glVertexAttribPointer as _gl_vertex_attrib_pointer

from termin.mesh.mesh import Mesh, VertexAttribType

from termin.visualization.platform.backends.base import (
    FramebufferHandle,
    GraphicsBackend,
    MeshHandle,
    ShaderHandle,
    TextureHandle,
)

_OPENGL_INITED = False

# Глобальный реестр контекстов: context_key -> make_current callable
# Используется для переключения контекста при удалении GPU ресурсов
_context_registry: Dict[int, Callable[[], None]] = {}

# Текущий активный context_key (обновляется при make_current)
_current_context_key: int | None = None


def register_context(context_key: int, make_current: Callable[[], None]) -> None:
    """Регистрирует контекст для последующего переключения при удалении ресурсов."""
    global _current_context_key
    _context_registry[context_key] = make_current
    # При регистрации контекст уже активен
    _current_context_key = context_key


def get_context_make_current(context_key: int) -> Callable[[], None] | None:
    """Возвращает функцию make_current для контекста или None."""
    original = _context_registry.get(context_key)
    if original is None:
        return None

    # Оборачиваем чтобы обновлять _current_context_key
    def wrapped():
        global _current_context_key
        original()
        _current_context_key = context_key

    return wrapped


def get_current_context_key() -> int | None:
    """Возвращает текущий активный context_key или None."""
    return _current_context_key


def _compile_shader(source: str, shader_type: int) -> int:
    shader = gl.glCreateShader(shader_type)
    gl.glShaderSource(shader, source)
    gl.glCompileShader(shader)
    status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
    if not status:
        log = gl.glGetShaderInfoLog(shader)
        raise RuntimeError(log.decode("utf-8") if isinstance(log, bytes) else str(log))
    return shader


def _link_program(shaders: list[int]) -> int:
    program = gl.glCreateProgram()
    
    for shader in shaders:
        gl.glAttachShader(program, shader)
    
    gl.glLinkProgram(program)
    status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
    if not status:
        log = gl.glGetProgramInfoLog(program)
        raise RuntimeError(log.decode("utf-8") if isinstance(log, bytes) else str(log))
    
    for shader in shaders:
        gl.glDetachShader(program, shader)
        gl.glDeleteShader(shader)

    return program


class OpenGLShaderHandle(ShaderHandle):
    def __init__(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None):
        self.vertex_source = vertex_source
        self.fragment_source = fragment_source
        self.geometry_source = geometry_source
        self.program: int | None = None
        self._uniform_cache: Dict[str, int] = {}

    def _ensure_compiled(self):
        if self.program is not None:
            return
        shaders = []
        vert = _compile_shader(self.vertex_source, gl.GL_VERTEX_SHADER)
        shaders.append(vert)

        if self.geometry_source:
            geom = _compile_shader(self.geometry_source, gl.GL_GEOMETRY_SHADER)
            shaders.append(geom)

        frag = _compile_shader(self.fragment_source, gl.GL_FRAGMENT_SHADER)
        shaders.append(frag)
        self.program = _link_program(shaders)

    def use(self):
        self._ensure_compiled()
        gl.glUseProgram(self.program)

    def stop(self):
        gl.glUseProgram(0)

    def delete(self):
        if self.program is not None:
            gl.glDeleteProgram(self.program)
            self.program = None
        self._uniform_cache.clear()

    def _uniform_location(self, name: str) -> int:
        if name not in self._uniform_cache:
            location = gl.glGetUniformLocation(self.program, name.encode("utf-8"))
            self._uniform_cache[name] = location
        return self._uniform_cache[name]

    def set_uniform_matrix4(self, name: str, matrix):
        self._ensure_compiled()
        mat = np.asarray(matrix, dtype=np.float32)
        gl.glUniformMatrix4fv(self._uniform_location(name), 1, True, mat.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))

    def set_uniform_vec2(self, name: str, vector):
        self._ensure_compiled()
        vec = np.asarray(vector, dtype=np.float32)
        gl.glUniform2f(self._uniform_location(name), float(vec[0]), float(vec[1]))

    def set_uniform_vec3(self, name: str, vector):
        self._ensure_compiled()
        vec = np.asarray(vector, dtype=np.float32)
        gl.glUniform3f(self._uniform_location(name), float(vec[0]), float(vec[1]), float(vec[2]))

    def set_uniform_vec4(self, name: str, vector):
        self._ensure_compiled()
        vec = np.asarray(vector, dtype=np.float32)
        gl.glUniform4f(self._uniform_location(name), float(vec[0]), float(vec[1]), float(vec[2]), float(vec[3]))

    def set_uniform_float(self, name: str, value: float):
        self._ensure_compiled()
        gl.glUniform1f(self._uniform_location(name), float(value))

    _DEBUG_UNIFORM_INT = False

    def set_uniform_int(self, name: str, value: int):
        self._ensure_compiled()
        location = self._uniform_location(name)
        if self._DEBUG_UNIFORM_INT and name == "u_bone_count":
            print(f"[OpenGL] set_uniform_int: name={name!r}, value={value}, location={location}")
        if location < 0:
            return
        gl.glUniform1i(location, int(value))

    _DEBUG_UNIFORM_ARRAY = False

    def set_uniform_matrix4_array(self, name: str, matrices, count: int):
        """Upload an array of 4x4 matrices to shader uniform."""
        self._ensure_compiled()
        location = self._uniform_location(name)
        if self._DEBUG_UNIFORM_ARRAY:
            print(f"[OpenGL] set_uniform_matrix4_array: name={name!r}, count={count}, location={location}")
        if location < 0:
            if self._DEBUG_UNIFORM_ARRAY:
                print(f"  WARNING: uniform {name!r} not found in shader!")
            return
        mat = np.asarray(matrices, dtype=np.float32).reshape(count, 4, 4)
        gl.glUniformMatrix4fv(
            location,
            count,
            True,  # transpose (row-major to column-major)
            mat.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        )


GL_TYPE_MAP = {
    VertexAttribType.FLOAT32: gl.GL_FLOAT,
    VertexAttribType.INT32:   gl.GL_INT,
    VertexAttribType.UINT32:  gl.GL_UNSIGNED_INT,
}

class OpenGLMeshHandle(MeshHandle):
    def __init__(self, mesh: Mesh):
        self._mesh = mesh
        if self._mesh.type == "triangles":
            if self._mesh.vertex_normals is None:
                self._mesh.compute_vertex_normals()
        self._vao: int | None = None
        self._vbo: int | None = None
        self._ebo: int | None = None
        self._index_count = self._mesh.indices.size
        self._upload()

    def _upload(self):
        buf = self._mesh.interleaved_buffer()
        layout = self._mesh.get_vertex_layout()

        self._vao = gl.glGenVertexArrays(1)
        self._vbo = gl.glGenBuffers(1)
        self._ebo = gl.glGenBuffers(1)

        gl.glBindVertexArray(self._vao)

        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, buf.nbytes, buf, gl.GL_STATIC_DRAW)

        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self._mesh.indices.nbytes, self._mesh.indices, gl.GL_STATIC_DRAW)


        for index, attr in enumerate(layout.attributes):
            gl_type = GL_TYPE_MAP[attr.vtype]
            gl.glEnableVertexAttribArray(index)
            _gl_vertex_attrib_pointer(
                index,
                attr.size,
                gl_type,
                gl.GL_FALSE,
                layout.stride,
                ctypes.c_void_p(attr.offset),
            )

        gl.glBindVertexArray(0)


    _DEBUG_DRAW = True  # DEBUG: investigate GL_INVALID_OPERATION

    def draw(self):
        gl.glEnable(gl.GL_DEPTH_TEST)

        if self._DEBUG_DRAW:
            current_program = gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)
            print(f"[OpenGLMeshHandle.draw] vao={self._vao}, vbo={self._vbo}, ebo={self._ebo}, idx_count={self._index_count}, current_program={current_program}")

        gl.glBindVertexArray(self._vao or 0)

        mode = gl.GL_TRIANGLES
        if self._mesh.type == "lines":
            mode = gl.GL_LINES

        gl.glDrawElements(mode, self._index_count, gl.GL_UNSIGNED_INT, ctypes.c_void_p(0))
        gl.glBindVertexArray(0)

    def delete(self):
        if self._vao is None:
            return
        gl.glDeleteVertexArrays(1, [self._vao])
        gl.glDeleteBuffers(1, [self._vbo])
        gl.glDeleteBuffers(1, [self._ebo])
        self._vao = self._vbo = self._ebo = None


class OpenGLTextureHandle(TextureHandle):
    def __init__(self, image_data: np.ndarray, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False):
        self._handle: int | None = None
        self._channels = channels
        self._data = image_data
        self._size = size
        self._mipmap = mipmap
        self._clamp = clamp
        self._upload()

    def _upload(self):
        self._handle = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._handle)
        internal_format = gl.GL_RGBA if self._channels != 1 else gl.GL_RED
        gl_format = internal_format
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, internal_format, self._size[0], self._size[1], 0, gl_format, gl.GL_UNSIGNED_BYTE, self._data)
        if self._mipmap:
            gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
        min_filter = gl.GL_LINEAR_MIPMAP_LINEAR if self._mipmap else gl.GL_LINEAR
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, min_filter)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        wrap_mode = gl.GL_CLAMP_TO_EDGE if self._clamp else gl.GL_REPEAT
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap_mode)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap_mode)
        if self._channels == 1:
            swizzle = np.array([gl.GL_RED, gl.GL_RED, gl.GL_RED, gl.GL_RED], dtype=np.int32)
            gl.glTexParameteriv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_SWIZZLE_RGBA, swizzle)

    def bind(self, unit: int = 0):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._handle or 0)

    def delete(self):
        if self._handle is not None:
            gl.glDeleteTextures(1, [self._handle])
            self._handle = None


class OpenGLGraphicsBackend(GraphicsBackend):
    def __init__(self):
        self._ui_buffers: Dict[int, Tuple[int, int]] = {}

    def ensure_ready(self):
        global _OPENGL_INITED
        if _OPENGL_INITED:
            return
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        gl.glFrontFace(gl.GL_CCW)
        _OPENGL_INITED = True

    def read_pixel(self, framebuffer, x: int, y: int):
        # привязываем FBO, из которого читаем
        self.bind_framebuffer(framebuffer)

        data = GL.glReadPixels(x, y, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        # data = 4 байта
        if isinstance(data, (bytes, bytearray)):
            arr = np.frombuffer(data, dtype=np.uint8)
        else:
            arr = np.array(data, dtype=np.uint8)

        r, g, b, a = arr
        return r / 255.0, g / 255.0, b / 255.0, a / 255.0

    def read_depth_buffer(self, framebuffer):
        if framebuffer is None:
            return None
        if not isinstance(framebuffer, OpenGLFramebufferHandle):
            return None
        if framebuffer._fbo is None:
            return None

        size = framebuffer._size
        if not size:
            return None
        width = int(size[0])
        height = int(size[1])
        if width <= 0 or height <= 0:
            return None

        try:
            current_fbo = gl.glGetIntegerv(gl.GL_FRAMEBUFFER_BINDING)
        except Exception:
            current_fbo = 0

        if isinstance(current_fbo, (list, tuple)):
            if current_fbo:
                current_fbo = int(current_fbo[0])
            else:
                current_fbo = 0

        try:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, framebuffer._fbo or 0)
            data = gl.glReadPixels(
                0,
                0,
                width,
                height,
                gl.GL_DEPTH_COMPONENT,
                gl.GL_FLOAT,
            )
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, int(current_fbo))

        if data is None:
            return None

        if isinstance(data, (bytes, bytearray)):
            depth = np.frombuffer(data, dtype=np.float32)
        else:
            depth = np.array(data, dtype=np.float32)

        expected_size = width * height
        if depth.size != expected_size:
            return None

        depth = depth.reshape((height, width))
        depth = np.flipud(depth)
        return depth

    def read_depth_pixel(self, framebuffer, x: int, y: int) -> float | None:
        """Читает глубину в указанной точке FBO."""
        if framebuffer is None:
            return None
        if not isinstance(framebuffer, OpenGLFramebufferHandle):
            return None
        if framebuffer._fbo is None:
            return None

        self.bind_framebuffer(framebuffer)

        data = gl.glReadPixels(x, y, 1, 1, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT)
        if data is None:
            return None

        if isinstance(data, (bytes, bytearray)):
            depth = np.frombuffer(data, dtype=np.float32)
        else:
            depth = np.array(data, dtype=np.float32)

        if depth.size == 0:
            return None

        return float(depth[0])

    def set_viewport(self, x: int, y: int, w: int, h: int):
        gl.glViewport(x, y, w, h)

    def enable_scissor(self, x: int, y: int, w: int, h: int):
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(x, y, w, h)

    def disable_scissor(self):
        gl.glDisable(gl.GL_SCISSOR_TEST)

    def clear_color_depth(self, color):
        gl.glClearColor(float(color[0]), float(color[1]), float(color[2]), float(color[3]))
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

    def clear_color(self, color):
        gl.glClearColor(float(color[0]), float(color[1]), float(color[2]), float(color[3]))
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)

    def clear_depth(self, value: float = 1.0):
        gl.glClearDepth(float(value))
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)

    def set_color_mask(self, r: bool, g: bool, b: bool, a: bool) -> None:
        gl.glColorMask(
            gl.GL_TRUE if r else gl.GL_FALSE,
            gl.GL_TRUE if g else gl.GL_FALSE,
            gl.GL_TRUE if b else gl.GL_FALSE,
            gl.GL_TRUE if a else gl.GL_FALSE,
        )

    def set_depth_test(self, enabled: bool):
        if enabled:
            gl.glEnable(gl.GL_DEPTH_TEST)
        else:
            gl.glDisable(gl.GL_DEPTH_TEST)

    def set_depth_mask(self, enabled: bool):
        gl.glDepthMask(gl.GL_TRUE if enabled else gl.GL_FALSE)

    def set_depth_func(self, func: str):
        mapping = {"less": gl.GL_LESS, "lequal": gl.GL_LEQUAL}
        gl.glDepthFunc(mapping.get(func, gl.GL_LESS))

    def set_cull_face(self, enabled: bool):
        if enabled:
            gl.glEnable(gl.GL_CULL_FACE)
        else:
            gl.glDisable(gl.GL_CULL_FACE)

    def set_blend(self, enabled: bool):
        if enabled:
            gl.glEnable(gl.GL_BLEND)
        else:
            gl.glDisable(gl.GL_BLEND)

    def set_blend_func(self, src: str, dst: str):
        mapping = {
            "src_alpha": gl.GL_SRC_ALPHA,
            "one_minus_src_alpha": gl.GL_ONE_MINUS_SRC_ALPHA,
            "one": gl.GL_ONE,
            "zero": gl.GL_ZERO,
        }
        gl.glBlendFunc(mapping.get(src, gl.GL_SRC_ALPHA), mapping.get(dst, gl.GL_ONE_MINUS_SRC_ALPHA))

    def reset_state(self) -> None:
        # Depth
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDepthMask(gl.GL_TRUE)

        # Blending off (opaque)
        gl.glDisable(gl.GL_BLEND)

        # Face culling
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        gl.glFrontFace(gl.GL_CCW)

        # Polygon mode
        gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)

        # Color mask
        gl.glColorMask(gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)

        # Stencil off
        gl.glDisable(gl.GL_STENCIL_TEST)

        # Scissor off
        gl.glDisable(gl.GL_SCISSOR_TEST)

    def create_shader(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None) -> ShaderHandle:
        return OpenGLShaderHandle(vertex_source, fragment_source, geometry_source)

    def create_mesh(self, mesh: Mesh) -> MeshHandle:
        return OpenGLMeshHandle(mesh)

    def create_texture(self, image_data, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False) -> TextureHandle:
        return OpenGLTextureHandle(image_data, size, channels=channels, mipmap=mipmap, clamp=clamp)

    def draw_ui_vertices(self, context_key: int, vertices):
        vao, vbo = self._ui_buffers.get(context_key, (None, None))
        if vao is None:
            vao = gl.glGenVertexArrays(1)
            vbo = gl.glGenBuffers(1)
            self._ui_buffers[context_key] = (vao, vbo)
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_DYNAMIC_DRAW)
        gl.glEnableVertexAttribArray(0)
        _gl_vertex_attrib_pointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))
        gl.glDisableVertexAttribArray(1)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)

    FS_VERTS = np.array(
    [
        [-1, -1, 0, 0],
        [ 1, -1, 1, 0],
        [-1,  1, 0, 1],
        [ 1,  1, 1, 1],
    ],
    dtype=np.float32,
    )

    def draw_ui_textured_quad(self, context_key: int):
        vao, vbo = self._ui_buffers.get(context_key, (None, None))
        if vao is None:
            vao = gl.glGenVertexArrays(1)
            vbo = gl.glGenBuffers(1)
            self._ui_buffers[context_key] = (vao, vbo)
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, self.FS_VERTS.nbytes, self.FS_VERTS, gl.GL_DYNAMIC_DRAW)
        stride = 4 * 4
        gl.glEnableVertexAttribArray(0)
        _gl_vertex_attrib_pointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(1)
        _gl_vertex_attrib_pointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)

    def set_polygon_mode(self, mode: str):
        from OpenGL import GL as gl
        if mode == "line":
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
        else:
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)

    def set_cull_face_enabled(self, enabled: bool):
        from OpenGL import GL as gl
        if enabled:
            gl.glEnable(gl.GL_CULL_FACE)
        else:
            gl.glDisable(gl.GL_CULL_FACE)

    def set_depth_test_enabled(self, enabled: bool):
        from OpenGL import GL as gl
        if enabled:
            gl.glEnable(gl.GL_DEPTH_TEST)
        else:
            gl.glDisable(gl.GL_DEPTH_TEST)

    def set_depth_write_enabled(self, enabled: bool):
        from OpenGL import GL as gl
        gl.glDepthMask(gl.GL_TRUE if enabled else gl.GL_FALSE)

    def create_framebuffer(self, size: Tuple[int, int], samples: int = 1) -> FramebufferHandle:
        return OpenGLFramebufferHandle(size, samples=samples)

    def create_shadow_framebuffer(self, size: Tuple[int, int]) -> FramebufferHandle:
        """Создаёт framebuffer для shadow mapping с depth texture и hardware PCF."""
        return OpenGLShadowFramebufferHandle(size)

    def bind_framebuffer(self, framebuffer: FramebufferHandle | None):
        if framebuffer is None:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        else:
            assert isinstance(framebuffer, (OpenGLFramebufferHandle, OpenGLShadowFramebufferHandle))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, framebuffer._fbo or 0)

    def blit_framebuffer(
        self,
        src: FramebufferHandle,
        dst: FramebufferHandle,
        src_rect: Tuple[int, int, int, int],
        dst_rect: Tuple[int, int, int, int],
    ):
        """
        Копирует color buffer из src в dst через glBlitFramebuffer.
        Автоматически выполняет MSAA resolve.
        """
        src_fbo = src._fbo if src._fbo is not None else 0
        dst_fbo = dst._fbo if dst._fbo is not None else 0

        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, src_fbo)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, dst_fbo)

        gl.glBlitFramebuffer(
            src_rect[0], src_rect[1], src_rect[2], src_rect[3],
            dst_rect[0], dst_rect[1], dst_rect[2], dst_rect[3],
            gl.GL_COLOR_BUFFER_BIT,
            gl.GL_NEAREST,
        )

        # Возвращаем состояние
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)


class _OpenGLColorTextureHandle(TextureHandle):
    """
    Лёгкая обёртка над уже созданной GL-текстурой.
    Жизненный цикл управляется фреймбуфером, delete() ничего не делает.
    """
    def __init__(self, tex_id: int):
        self._tex_id = tex_id

    def bind(self, unit: int = 0):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._tex_id or 0)

    def delete(self):
        # Фактическое удаление делает владелец FBO
        pass

    def _set_tex_id(self, tex_id: int):
        self._tex_id = tex_id

class OpenGLFramebufferHandle(FramebufferHandle):
    def __init__(
        self,
        size: Tuple[int, int],
        fbo_id: int | None = None,
        owns_attachments: bool = True,
        samples: int = 1,
    ):
        self._size = size
        self._owns_attachments = owns_attachments
        self._samples = samples  # 1 = обычный, >1 = MSAA
        self._fbo: int | None = None
        self._color_tex: int | None = None
        self._depth_rb: int | None = None
        self._color_handle = _OpenGLColorTextureHandle(0)
        if fbo_id is None:
            self._create()
        else:
            self._fbo = fbo_id

    @property
    def samples(self) -> int:
        """Количество MSAA samples (1 = без MSAA)."""
        return self._samples

    @property
    def is_msaa(self) -> bool:
        """True если FBO использует MSAA."""
        return self._samples > 1

    def set_external_target(self, fbo_id: int, size: Tuple[int, int]):
        """Rebind handle to an externally managed FBO without owning attachments."""
        self._owns_attachments = False
        self._fbo = fbo_id
        self._size = size

    def get_size(self) -> Tuple[int, int]:
        """Returns the size of the framebuffer."""
        return self._size

    def _create(self):
        w, h = self._size

        # создаём FBO
        self._fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)

        if self._samples > 1:
            # MSAA: используем GL_TEXTURE_2D_MULTISAMPLE
            self._color_tex = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, self._color_tex)
            gl.glTexImage2DMultisample(
                gl.GL_TEXTURE_2D_MULTISAMPLE,
                self._samples,
                gl.GL_RGBA8,
                w, h,
                gl.GL_TRUE,  # fixedsamplelocations
            )
            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER,
                gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D_MULTISAMPLE,
                self._color_tex,
                0,
            )

            # depth renderbuffer с MSAA
            self._depth_rb = gl.glGenRenderbuffers(1)
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth_rb)
            gl.glRenderbufferStorageMultisample(
                gl.GL_RENDERBUFFER,
                self._samples,
                gl.GL_DEPTH_COMPONENT24,
                w, h,
            )
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER,
                gl.GL_DEPTH_ATTACHMENT,
                gl.GL_RENDERBUFFER,
                self._depth_rb,
            )
        else:
            # Обычный FBO без MSAA
            self._color_tex = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._color_tex)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8,
                w, h, 0,
                gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None
            )
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER,
                gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D,
                self._color_tex,
                0,
            )

            # depth renderbuffer
            self._depth_rb = gl.glGenRenderbuffers(1)
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth_rb)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, w, h)
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER,
                gl.GL_DEPTH_ATTACHMENT,
                gl.GL_RENDERBUFFER,
                self._depth_rb,
            )

        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            raise RuntimeError(f"Framebuffer is incomplete: 0x{status:X}")

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

        # обновляем handle текстуры (для MSAA текстура не сэмплируется напрямую)
        self._color_handle._set_tex_id(self._color_tex)

    def resize(self, size: Tuple[int, int]):
        if size == self._size and self._fbo is not None:
            return
        if not self._owns_attachments:
            self._size = size
            return
        self.delete()
        self._size = size
        self._create()

    def color_texture(self) -> TextureHandle:
        return self._color_handle

    def delete(self):
        if not self._owns_attachments:
            self._fbo = None
            return
        if self._fbo is not None:
            gl.glDeleteFramebuffers(1, [self._fbo])
            self._fbo = None
        if self._color_tex is not None:
            gl.glDeleteTextures(1, [self._color_tex])
            self._color_tex = None
        if self._depth_rb is not None:
            gl.glDeleteRenderbuffers(1, [self._depth_rb])
            self._depth_rb = None


class _OpenGLDepthTextureHandle(TextureHandle):
    """
    Обёртка над depth texture для shadow mapping.
    Настроена для hardware PCF (sampler2DShadow).
    """
    def __init__(self, tex_id: int):
        self._tex_id = tex_id

    def bind(self, unit: int = 0):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._tex_id or 0)

    def delete(self):
        # Удаление через владельца FBO
        pass

    def _set_tex_id(self, tex_id: int):
        self._tex_id = tex_id


class OpenGLShadowFramebufferHandle(FramebufferHandle):
    """
    Framebuffer для shadow mapping с depth texture.

    Особенности:
    - Depth texture вместо renderbuffer
    - GL_TEXTURE_COMPARE_MODE для hardware PCF
    - Нет color attachment (depth-only)
    """

    def __init__(self, size: Tuple[int, int]):
        self._size = size
        self._fbo: int | None = None
        self._depth_tex: int | None = None
        self._depth_handle = _OpenGLDepthTextureHandle(0)
        self._create()

    def get_size(self) -> Tuple[int, int]:
        return self._size

    def _create(self):
        w, h = self._size

        # Создаём FBO
        self._fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)

        # Depth texture (не renderbuffer!)
        self._depth_tex = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._depth_tex)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24,
            w, h, 0,
            gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, None
        )

        # Фильтрация для PCF
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER)

        # Border color = 1.0 (максимальная глубина = нет тени)
        border_color = (1.0, 1.0, 1.0, 1.0)
        gl.glTexParameterfv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_BORDER_COLOR, border_color)

        # Hardware PCF: sampler2DShadow автоматически делает depth comparison
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)

        # Привязываем depth texture к FBO
        gl.glFramebufferTexture2D(
            gl.GL_FRAMEBUFFER,
            gl.GL_DEPTH_ATTACHMENT,
            gl.GL_TEXTURE_2D,
            self._depth_tex,
            0,
        )

        # Нет color attachment - отключаем draw/read buffer
        gl.glDrawBuffer(gl.GL_NONE)
        gl.glReadBuffer(gl.GL_NONE)

        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            raise RuntimeError(f"Shadow framebuffer is incomplete: 0x{status:X}")

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

        self._depth_handle._set_tex_id(self._depth_tex)

    def resize(self, size: Tuple[int, int]):
        if size == self._size and self._fbo is not None:
            return
        self.delete()
        self._size = size
        self._create()

    def color_texture(self) -> TextureHandle:
        """Для shadow FBO возвращаем depth texture."""
        return self._depth_handle

    def depth_texture(self) -> TextureHandle:
        """Возвращает depth texture для shadow sampling."""
        return self._depth_handle

    def delete(self):
        if self._fbo is not None:
            gl.glDeleteFramebuffers(1, [self._fbo])
            self._fbo = None
        if self._depth_tex is not None:
            gl.glDeleteTextures(1, [self._depth_tex])
            self._depth_tex = None
