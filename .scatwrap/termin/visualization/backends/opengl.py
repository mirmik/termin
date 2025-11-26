<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/opengl.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;OpenGL-based graphics backend.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
import ctypes<br>
from typing import Dict, Tuple<br>
<br>
import numpy as np<br>
from OpenGL import GL as gl<br>
from OpenGL import GL as GL<br>
from OpenGL.raw.GL.VERSION.GL_2_0 import glVertexAttribPointer as _gl_vertex_attrib_pointer<br>
<br>
from termin.mesh.mesh import Mesh, VertexAttribType<br>
<br>
from .base import (<br>
    GraphicsBackend,<br>
    MeshHandle,<br>
    PolylineHandle,<br>
    ShaderHandle,<br>
    TextureHandle,<br>
    FramebufferHandle,<br>
)<br>
<br>
_OPENGL_INITED = False<br>
<br>
<br>
def _compile_shader(source: str, shader_type: int) -&gt; int:<br>
    shader = gl.glCreateShader(shader_type)<br>
    gl.glShaderSource(shader, source)<br>
    gl.glCompileShader(shader)<br>
    status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)<br>
    if not status:<br>
        log = gl.glGetShaderInfoLog(shader)<br>
        raise RuntimeError(log.decode(&quot;utf-8&quot;) if isinstance(log, bytes) else str(log))<br>
    return shader<br>
<br>
<br>
def _link_program(shaders: list[int]) -&gt; int:<br>
    program = gl.glCreateProgram()<br>
    <br>
    for shader in shaders:<br>
        gl.glAttachShader(program, shader)<br>
    <br>
    gl.glLinkProgram(program)<br>
    status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)<br>
    if not status:<br>
        log = gl.glGetProgramInfoLog(program)<br>
        raise RuntimeError(log.decode(&quot;utf-8&quot;) if isinstance(log, bytes) else str(log))<br>
    <br>
    for shader in shaders:<br>
        gl.glDetachShader(program, shader)<br>
        gl.glDeleteShader(shader)<br>
<br>
    return program<br>
<br>
<br>
class OpenGLShaderHandle(ShaderHandle):<br>
    def __init__(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None):<br>
        self.vertex_source = vertex_source<br>
        self.fragment_source = fragment_source<br>
        self.geometry_source = geometry_source<br>
        self.program: int | None = None<br>
        self._uniform_cache: Dict[str, int] = {}<br>
<br>
    def _ensure_compiled(self):<br>
        if self.program is not None:<br>
            return<br>
        shaders = []<br>
        vert = _compile_shader(self.vertex_source, gl.GL_VERTEX_SHADER)<br>
        shaders.append(vert)<br>
<br>
        if self.geometry_source:<br>
            geom = _compile_shader(self.geometry_source, gl.GL_GEOMETRY_SHADER)<br>
            shaders.append(geom)<br>
<br>
        frag = _compile_shader(self.fragment_source, gl.GL_FRAGMENT_SHADER)<br>
        shaders.append(frag)<br>
        self.program = _link_program(shaders)<br>
<br>
    def use(self):<br>
        self._ensure_compiled()<br>
        gl.glUseProgram(self.program)<br>
<br>
    def stop(self):<br>
        gl.glUseProgram(0)<br>
<br>
    def delete(self):<br>
        if self.program is not None:<br>
            gl.glDeleteProgram(self.program)<br>
            self.program = None<br>
        self._uniform_cache.clear()<br>
<br>
    def _uniform_location(self, name: str) -&gt; int:<br>
        if name not in self._uniform_cache:<br>
            location = gl.glGetUniformLocation(self.program, name.encode(&quot;utf-8&quot;))<br>
            self._uniform_cache[name] = location<br>
        return self._uniform_cache[name]<br>
<br>
    def set_uniform_matrix4(self, name: str, matrix):<br>
        self._ensure_compiled()<br>
        mat = np.asarray(matrix, dtype=np.float32)<br>
        gl.glUniformMatrix4fv(self._uniform_location(name), 1, True, mat.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))<br>
<br>
    def set_uniform_vec2(self, name: str, vector):<br>
        self._ensure_compiled()<br>
        vec = np.asarray(vector, dtype=np.float32)<br>
        gl.glUniform2f(self._uniform_location(name), float(vec[0]), float(vec[1]))<br>
<br>
    def set_uniform_vec3(self, name: str, vector):<br>
        self._ensure_compiled()<br>
        vec = np.asarray(vector, dtype=np.float32)<br>
        gl.glUniform3f(self._uniform_location(name), float(vec[0]), float(vec[1]), float(vec[2]))<br>
<br>
    def set_uniform_vec4(self, name: str, vector):<br>
        self._ensure_compiled()<br>
        vec = np.asarray(vector, dtype=np.float32)<br>
        gl.glUniform4f(self._uniform_location(name), float(vec[0]), float(vec[1]), float(vec[2]), float(vec[3]))<br>
<br>
    def set_uniform_float(self, name: str, value: float):<br>
        self._ensure_compiled()<br>
        gl.glUniform1f(self._uniform_location(name), float(value))<br>
<br>
    def set_uniform_int(self, name: str, value: int):<br>
        self._ensure_compiled()<br>
        gl.glUniform1i(self._uniform_location(name), int(value))<br>
<br>
<br>
GL_TYPE_MAP = {<br>
    VertexAttribType.FLOAT32: gl.GL_FLOAT,<br>
    VertexAttribType.INT32:   gl.GL_INT,<br>
    VertexAttribType.UINT32:  gl.GL_UNSIGNED_INT,<br>
}<br>
<br>
class OpenGLMeshHandle(MeshHandle):<br>
    def __init__(self, mesh: Mesh):<br>
        self._mesh = mesh<br>
        if self._mesh.type == &quot;triangles&quot;:<br>
            if self._mesh.vertex_normals is None:<br>
                self._mesh.compute_vertex_normals()<br>
        self._vao: int | None = None<br>
        self._vbo: int | None = None<br>
        self._ebo: int | None = None<br>
        self._index_count = self._mesh.indices.size<br>
        self._upload()<br>
<br>
    def _upload(self):<br>
        buf = self._mesh.interleaved_buffer()<br>
        layout = self._mesh.get_vertex_layout()<br>
<br>
        self._vao = gl.glGenVertexArrays(1)<br>
        self._vbo = gl.glGenBuffers(1)<br>
        self._ebo = gl.glGenBuffers(1)<br>
<br>
        gl.glBindVertexArray(self._vao)<br>
<br>
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)<br>
        gl.glBufferData(gl.GL_ARRAY_BUFFER, buf.nbytes, buf, gl.GL_STATIC_DRAW)<br>
<br>
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self._ebo)<br>
        gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self._mesh.indices.nbytes, self._mesh.indices, gl.GL_STATIC_DRAW)<br>
<br>
<br>
        for index, attr in enumerate(layout.attributes):<br>
            gl_type = GL_TYPE_MAP[attr.vtype]<br>
            gl.glEnableVertexAttribArray(index)<br>
            _gl_vertex_attrib_pointer(<br>
                index,<br>
                attr.size,<br>
                gl_type,<br>
                gl.GL_FALSE,<br>
                layout.stride,<br>
                ctypes.c_void_p(attr.offset),<br>
            )<br>
<br>
        gl.glBindVertexArray(0)<br>
<br>
<br>
    def draw(self):<br>
        gl.glEnable(gl.GL_DEPTH_TEST)<br>
        gl.glBindVertexArray(self._vao or 0)<br>
<br>
        mode = gl.GL_TRIANGLES<br>
        if getattr(self._mesh, &quot;type&quot;, &quot;triangles&quot;) == &quot;lines&quot;:<br>
            mode = gl.GL_LINES<br>
<br>
        gl.glDrawElements(mode, self._index_count, gl.GL_UNSIGNED_INT, ctypes.c_void_p(0))<br>
        gl.glBindVertexArray(0)<br>
<br>
    def delete(self):<br>
        if self._vao is None:<br>
            return<br>
        gl.glDeleteVertexArrays(1, [self._vao])<br>
        gl.glDeleteBuffers(1, [self._vbo])<br>
        gl.glDeleteBuffers(1, [self._ebo])<br>
        self._vao = self._vbo = self._ebo = None<br>
<br>
<br>
class OpenGLPolylineHandle(PolylineHandle):<br>
    def __init__(self, vertices: np.ndarray, indices: np.ndarray | None, is_strip: bool):<br>
        self._vertices = vertices.astype(np.float32)<br>
        self._indices = indices.astype(np.uint32) if indices is not None else None<br>
        self._is_strip = is_strip<br>
        self._vao: int | None = None<br>
        self._vbo: int | None = None<br>
        self._ebo: int | None = None<br>
        self._upload()<br>
<br>
    def _upload(self):<br>
        vertex_block = self._vertices.ravel()<br>
        self._vao = gl.glGenVertexArrays(1)<br>
        self._vbo = gl.glGenBuffers(1)<br>
        gl.glBindVertexArray(self._vao)<br>
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)<br>
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertex_block.nbytes, vertex_block, gl.GL_STATIC_DRAW)<br>
        if self._indices is not None:<br>
            self._ebo = gl.glGenBuffers(1)<br>
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self._ebo)<br>
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self._indices.nbytes, self._indices, gl.GL_STATIC_DRAW)<br>
        stride = 3 * 4<br>
        gl.glEnableVertexAttribArray(0)<br>
        _gl_vertex_attrib_pointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))<br>
        gl.glBindVertexArray(0)<br>
<br>
    def draw(self):<br>
        mode = gl.GL_LINE_STRIP if self._is_strip else gl.GL_LINES<br>
        gl.glBindVertexArray(self._vao or 0)<br>
        gl.glEnable(gl.GL_DEPTH_TEST)<br>
        if self._indices is not None:<br>
            gl.glDrawElements(mode, self._indices.size, gl.GL_UNSIGNED_INT, ctypes.c_void_p(0))<br>
        else:<br>
            gl.glDrawArrays(mode, 0, self._vertices.shape[0])<br>
        gl.glBindVertexArray(0)<br>
<br>
    def delete(self):<br>
        if self._vao is None:<br>
            return<br>
        gl.glDeleteVertexArrays(1, [self._vao])<br>
        gl.glDeleteBuffers(1, [self._vbo])<br>
        if self._ebo is not None:<br>
            gl.glDeleteBuffers(1, [self._ebo])<br>
        self._vao = self._vbo = self._ebo = None<br>
<br>
<br>
class OpenGLTextureHandle(TextureHandle):<br>
    def __init__(self, image_data: np.ndarray, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False):<br>
        self._handle: int | None = None<br>
        self._channels = channels<br>
        self._data = image_data<br>
        self._size = size<br>
        self._mipmap = mipmap<br>
        self._clamp = clamp<br>
        self._upload()<br>
<br>
    def _upload(self):<br>
        self._handle = gl.glGenTextures(1)<br>
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._handle)<br>
        internal_format = gl.GL_RGBA if self._channels != 1 else gl.GL_RED<br>
        gl_format = internal_format<br>
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, internal_format, self._size[0], self._size[1], 0, gl_format, gl.GL_UNSIGNED_BYTE, self._data)<br>
        if self._mipmap:<br>
            gl.glGenerateMipmap(gl.GL_TEXTURE_2D)<br>
        min_filter = gl.GL_LINEAR_MIPMAP_LINEAR if self._mipmap else gl.GL_LINEAR<br>
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, min_filter)<br>
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)<br>
        wrap_mode = gl.GL_CLAMP_TO_EDGE if self._clamp else gl.GL_REPEAT<br>
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap_mode)<br>
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap_mode)<br>
        if self._channels == 1:<br>
            swizzle = np.array([gl.GL_RED, gl.GL_RED, gl.GL_RED, gl.GL_RED], dtype=np.int32)<br>
            gl.glTexParameteriv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_SWIZZLE_RGBA, swizzle)<br>
<br>
    def bind(self, unit: int = 0):<br>
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)<br>
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._handle or 0)<br>
<br>
    def delete(self):<br>
        if self._handle is not None:<br>
            gl.glDeleteTextures(1, [self._handle])<br>
            self._handle = None<br>
<br>
<br>
class OpenGLGraphicsBackend(GraphicsBackend):<br>
    def __init__(self):<br>
        self._ui_buffers: Dict[int, Tuple[int, int]] = {}<br>
<br>
    def ensure_ready(self):<br>
        global _OPENGL_INITED<br>
        if _OPENGL_INITED:<br>
            return<br>
        gl.glEnable(gl.GL_DEPTH_TEST)<br>
        gl.glEnable(gl.GL_CULL_FACE)<br>
        gl.glCullFace(gl.GL_BACK)<br>
        gl.glFrontFace(gl.GL_CCW)<br>
        _OPENGL_INITED = True<br>
<br>
    def read_pixel(self, framebuffer, x: int, y: int):<br>
        # привязываем FBO, из которого читаем<br>
        self.bind_framebuffer(framebuffer)<br>
        #print(&quot;Reading pixel at:&quot;, x, y, &quot;from framebuffer:&quot;, framebuffer._fbo)  # --- DEBUG ---<br>
<br>
        data = GL.glReadPixels(x, y, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)<br>
        # data = 4 байта<br>
        if isinstance(data, (bytes, bytearray)):<br>
            arr = np.frombuffer(data, dtype=np.uint8)<br>
        else:<br>
            arr = np.array(data, dtype=np.uint8)<br>
<br>
        r, g, b, a = arr<br>
        return r / 255.0, g / 255.0, b / 255.0, a / 255.0<br>
<br>
    def set_viewport(self, x: int, y: int, w: int, h: int):<br>
        gl.glViewport(x, y, w, h)<br>
<br>
    def enable_scissor(self, x: int, y: int, w: int, h: int):<br>
        gl.glEnable(gl.GL_SCISSOR_TEST)<br>
        gl.glScissor(x, y, w, h)<br>
<br>
    def disable_scissor(self):<br>
        gl.glDisable(gl.GL_SCISSOR_TEST)<br>
<br>
    def clear_color_depth(self, color):<br>
        gl.glClearColor(float(color[0]), float(color[1]), float(color[2]), float(color[3]))<br>
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)<br>
<br>
    def set_depth_test(self, enabled: bool):<br>
        if enabled:<br>
            gl.glEnable(gl.GL_DEPTH_TEST)<br>
        else:<br>
            gl.glDisable(gl.GL_DEPTH_TEST)<br>
<br>
    def set_depth_mask(self, enabled: bool):<br>
        gl.glDepthMask(gl.GL_TRUE if enabled else gl.GL_FALSE)<br>
<br>
    def set_depth_func(self, func: str):<br>
        mapping = {&quot;less&quot;: gl.GL_LESS, &quot;lequal&quot;: gl.GL_LEQUAL}<br>
        gl.glDepthFunc(mapping.get(func, gl.GL_LESS))<br>
<br>
    def set_cull_face(self, enabled: bool):<br>
        if enabled:<br>
            gl.glEnable(gl.GL_CULL_FACE)<br>
        else:<br>
            gl.glDisable(gl.GL_CULL_FACE)<br>
<br>
    def set_blend(self, enabled: bool):<br>
        if enabled:<br>
            gl.glEnable(gl.GL_BLEND)<br>
        else:<br>
            gl.glDisable(gl.GL_BLEND)<br>
<br>
    def set_blend_func(self, src: str, dst: str):<br>
        mapping = {<br>
            &quot;src_alpha&quot;: gl.GL_SRC_ALPHA,<br>
            &quot;one_minus_src_alpha&quot;: gl.GL_ONE_MINUS_SRC_ALPHA,<br>
            &quot;one&quot;: gl.GL_ONE,<br>
            &quot;zero&quot;: gl.GL_ZERO,<br>
        }<br>
        gl.glBlendFunc(mapping.get(src, gl.GL_SRC_ALPHA), mapping.get(dst, gl.GL_ONE_MINUS_SRC_ALPHA))<br>
<br>
    def create_shader(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None) -&gt; ShaderHandle:<br>
        return OpenGLShaderHandle(vertex_source, fragment_source, geometry_source)<br>
<br>
    def create_mesh(self, mesh: Mesh) -&gt; MeshHandle:<br>
        return OpenGLMeshHandle(mesh)<br>
<br>
    def create_polyline(self, polyline) -&gt; PolylineHandle:<br>
        return OpenGLPolylineHandle(polyline.vertices, polyline.indices, polyline.is_strip)<br>
<br>
    def create_texture(self, image_data, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False) -&gt; TextureHandle:<br>
        return OpenGLTextureHandle(image_data, size, channels=channels, mipmap=mipmap, clamp=clamp)<br>
<br>
    def draw_ui_vertices(self, context_key: int, vertices):<br>
        vao, vbo = self._ui_buffers.get(context_key, (None, None))<br>
        if vao is None:<br>
            vao = gl.glGenVertexArrays(1)<br>
            vbo = gl.glGenBuffers(1)<br>
            self._ui_buffers[context_key] = (vao, vbo)<br>
        gl.glBindVertexArray(vao)<br>
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)<br>
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_DYNAMIC_DRAW)<br>
        gl.glEnableVertexAttribArray(0)<br>
        _gl_vertex_attrib_pointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))<br>
        gl.glDisableVertexAttribArray(1)<br>
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)<br>
        gl.glBindVertexArray(0)<br>
<br>
    FS_VERTS = np.array(<br>
    [<br>
        [-1, -1, 0, 0],<br>
        [ 1, -1, 1, 0],<br>
        [-1,  1, 0, 1],<br>
        [ 1,  1, 1, 1],<br>
    ],<br>
    dtype=np.float32,<br>
    )<br>
<br>
    def draw_ui_textured_quad(self, context_key: int):<br>
        vao, vbo = self._ui_buffers.get(context_key, (None, None))<br>
        if vao is None:<br>
            vao = gl.glGenVertexArrays(1)<br>
            vbo = gl.glGenBuffers(1)<br>
            self._ui_buffers[context_key] = (vao, vbo)<br>
        gl.glBindVertexArray(vao)<br>
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)<br>
        gl.glBufferData(gl.GL_ARRAY_BUFFER, self.FS_VERTS.nbytes, self.FS_VERTS, gl.GL_DYNAMIC_DRAW)<br>
        stride = 4 * 4<br>
        gl.glEnableVertexAttribArray(0)<br>
        _gl_vertex_attrib_pointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))<br>
        gl.glEnableVertexAttribArray(1)<br>
        _gl_vertex_attrib_pointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))<br>
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)<br>
        gl.glBindVertexArray(0)<br>
<br>
    def set_polygon_mode(self, mode: str):<br>
        from OpenGL import GL as gl<br>
        if mode == &quot;line&quot;:<br>
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)<br>
        else:<br>
            gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)<br>
<br>
    def set_cull_face_enabled(self, enabled: bool):<br>
        from OpenGL import GL as gl<br>
        if enabled:<br>
            gl.glEnable(gl.GL_CULL_FACE)<br>
        else:<br>
            gl.glDisable(gl.GL_CULL_FACE)<br>
<br>
    def set_depth_test_enabled(self, enabled: bool):<br>
        from OpenGL import GL as gl<br>
        if enabled:<br>
            gl.glEnable(gl.GL_DEPTH_TEST)<br>
        else:<br>
            gl.glDisable(gl.GL_DEPTH_TEST)<br>
<br>
    def set_depth_write_enabled(self, enabled: bool):<br>
        from OpenGL import GL as gl<br>
        gl.glDepthMask(gl.GL_TRUE if enabled else gl.GL_FALSE)<br>
<br>
    def create_framebuffer(self, size: Tuple[int, int]) -&gt; FramebufferHandle:<br>
        return OpenGLFramebufferHandle(size)<br>
<br>
    def bind_framebuffer(self, framebuffer: FramebufferHandle | None):<br>
        if framebuffer is None:<br>
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)<br>
        else:<br>
            assert isinstance(framebuffer, OpenGLFramebufferHandle)<br>
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, framebuffer._fbo or 0)<br>
<br>
class _OpenGLColorTextureHandle(TextureHandle):<br>
    &quot;&quot;&quot;<br>
    Лёгкая обёртка над уже созданной GL-текстурой.<br>
    Жизненный цикл управляется фреймбуфером, delete() ничего не делает.<br>
    &quot;&quot;&quot;<br>
    def __init__(self, tex_id: int):<br>
        self._tex_id = tex_id<br>
<br>
    def bind(self, unit: int = 0):<br>
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)<br>
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._tex_id or 0)<br>
<br>
    def delete(self):<br>
        # Фактическое удаление делает владелец FBO<br>
        pass<br>
<br>
    def _set_tex_id(self, tex_id: int):<br>
        self._tex_id = tex_id<br>
<br>
class OpenGLFramebufferHandle(FramebufferHandle):<br>
    def __init__(self, size: Tuple[int, int]):<br>
        self._size = size<br>
        self._fbo: int | None = None<br>
        self._color_tex: int | None = None<br>
        self._depth_rb: int | None = None<br>
        self._color_handle = _OpenGLColorTextureHandle(0)<br>
        self._create()<br>
<br>
    def _create(self):<br>
        w, h = self._size<br>
<br>
        # создаём FBO<br>
        self._fbo = gl.glGenFramebuffers(1)<br>
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)<br>
<br>
        # цветовой attachment (RGBA8)<br>
        self._color_tex = gl.glGenTextures(1)<br>
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._color_tex)<br>
        gl.glTexImage2D(<br>
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8,<br>
            w, h, 0,<br>
            gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None<br>
        )<br>
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)<br>
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)<br>
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)<br>
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)<br>
<br>
        gl.glFramebufferTexture2D(<br>
            gl.GL_FRAMEBUFFER,<br>
            gl.GL_COLOR_ATTACHMENT0,<br>
            gl.GL_TEXTURE_2D,<br>
            self._color_tex,<br>
            0,<br>
        )<br>
<br>
        # depth renderbuffer<br>
        self._depth_rb = gl.glGenRenderbuffers(1)<br>
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth_rb)<br>
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, w, h)<br>
        gl.glFramebufferRenderbuffer(<br>
            gl.GL_FRAMEBUFFER,<br>
            gl.GL_DEPTH_ATTACHMENT,<br>
            gl.GL_RENDERBUFFER,<br>
            self._depth_rb,<br>
        )<br>
<br>
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)<br>
        if status != gl.GL_FRAMEBUFFER_COMPLETE:<br>
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)<br>
            raise RuntimeError(f&quot;Framebuffer is incomplete: 0x{status:X}&quot;)<br>
<br>
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)<br>
<br>
        # обновляем handle текстуры<br>
        self._color_handle._set_tex_id(self._color_tex)<br>
<br>
    def resize(self, size: Tuple[int, int]):<br>
        if size == self._size and self._fbo is not None:<br>
            return<br>
        self.delete()<br>
        self._size = size<br>
        self._create()<br>
<br>
    def color_texture(self) -&gt; TextureHandle:<br>
        return self._color_handle<br>
<br>
    def delete(self):<br>
        if self._fbo is not None:<br>
            gl.glDeleteFramebuffers(1, [self._fbo])<br>
            self._fbo = None<br>
        if self._color_tex is not None:<br>
            gl.glDeleteTextures(1, [self._color_tex])<br>
            self._color_tex = None<br>
        if self._depth_rb is not None:<br>
            gl.glDeleteRenderbuffers(1, [self._depth_rb])<br>
            self._depth_rb = None<br>
<!-- END SCAT CODE -->
</body>
</html>
