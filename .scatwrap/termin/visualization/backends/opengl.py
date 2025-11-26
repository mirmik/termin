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
&#9;GraphicsBackend,<br>
&#9;MeshHandle,<br>
&#9;PolylineHandle,<br>
&#9;ShaderHandle,<br>
&#9;TextureHandle,<br>
&#9;FramebufferHandle,<br>
)<br>
<br>
_OPENGL_INITED = False<br>
<br>
<br>
def _compile_shader(source: str, shader_type: int) -&gt; int:<br>
&#9;shader = gl.glCreateShader(shader_type)<br>
&#9;gl.glShaderSource(shader, source)<br>
&#9;gl.glCompileShader(shader)<br>
&#9;status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)<br>
&#9;if not status:<br>
&#9;&#9;log = gl.glGetShaderInfoLog(shader)<br>
&#9;&#9;raise RuntimeError(log.decode(&quot;utf-8&quot;) if isinstance(log, bytes) else str(log))<br>
&#9;return shader<br>
<br>
<br>
def _link_program(shaders: list[int]) -&gt; int:<br>
&#9;program = gl.glCreateProgram()<br>
&#9;<br>
&#9;for shader in shaders:<br>
&#9;&#9;gl.glAttachShader(program, shader)<br>
&#9;<br>
&#9;gl.glLinkProgram(program)<br>
&#9;status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)<br>
&#9;if not status:<br>
&#9;&#9;log = gl.glGetProgramInfoLog(program)<br>
&#9;&#9;raise RuntimeError(log.decode(&quot;utf-8&quot;) if isinstance(log, bytes) else str(log))<br>
&#9;<br>
&#9;for shader in shaders:<br>
&#9;&#9;gl.glDetachShader(program, shader)<br>
&#9;&#9;gl.glDeleteShader(shader)<br>
<br>
&#9;return program<br>
<br>
<br>
class OpenGLShaderHandle(ShaderHandle):<br>
&#9;def __init__(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None):<br>
&#9;&#9;self.vertex_source = vertex_source<br>
&#9;&#9;self.fragment_source = fragment_source<br>
&#9;&#9;self.geometry_source = geometry_source<br>
&#9;&#9;self.program: int | None = None<br>
&#9;&#9;self._uniform_cache: Dict[str, int] = {}<br>
<br>
&#9;def _ensure_compiled(self):<br>
&#9;&#9;if self.program is not None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;shaders = []<br>
&#9;&#9;vert = _compile_shader(self.vertex_source, gl.GL_VERTEX_SHADER)<br>
&#9;&#9;shaders.append(vert)<br>
<br>
&#9;&#9;if self.geometry_source:<br>
&#9;&#9;&#9;geom = _compile_shader(self.geometry_source, gl.GL_GEOMETRY_SHADER)<br>
&#9;&#9;&#9;shaders.append(geom)<br>
<br>
&#9;&#9;frag = _compile_shader(self.fragment_source, gl.GL_FRAGMENT_SHADER)<br>
&#9;&#9;shaders.append(frag)<br>
&#9;&#9;self.program = _link_program(shaders)<br>
<br>
&#9;def use(self):<br>
&#9;&#9;self._ensure_compiled()<br>
&#9;&#9;gl.glUseProgram(self.program)<br>
<br>
&#9;def stop(self):<br>
&#9;&#9;gl.glUseProgram(0)<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;if self.program is not None:<br>
&#9;&#9;&#9;gl.glDeleteProgram(self.program)<br>
&#9;&#9;&#9;self.program = None<br>
&#9;&#9;self._uniform_cache.clear()<br>
<br>
&#9;def _uniform_location(self, name: str) -&gt; int:<br>
&#9;&#9;if name not in self._uniform_cache:<br>
&#9;&#9;&#9;location = gl.glGetUniformLocation(self.program, name.encode(&quot;utf-8&quot;))<br>
&#9;&#9;&#9;self._uniform_cache[name] = location<br>
&#9;&#9;return self._uniform_cache[name]<br>
<br>
&#9;def set_uniform_matrix4(self, name: str, matrix):<br>
&#9;&#9;self._ensure_compiled()<br>
&#9;&#9;mat = np.asarray(matrix, dtype=np.float32)<br>
&#9;&#9;gl.glUniformMatrix4fv(self._uniform_location(name), 1, True, mat.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))<br>
<br>
&#9;def set_uniform_vec2(self, name: str, vector):<br>
&#9;&#9;self._ensure_compiled()<br>
&#9;&#9;vec = np.asarray(vector, dtype=np.float32)<br>
&#9;&#9;gl.glUniform2f(self._uniform_location(name), float(vec[0]), float(vec[1]))<br>
<br>
&#9;def set_uniform_vec3(self, name: str, vector):<br>
&#9;&#9;self._ensure_compiled()<br>
&#9;&#9;vec = np.asarray(vector, dtype=np.float32)<br>
&#9;&#9;gl.glUniform3f(self._uniform_location(name), float(vec[0]), float(vec[1]), float(vec[2]))<br>
<br>
&#9;def set_uniform_vec4(self, name: str, vector):<br>
&#9;&#9;self._ensure_compiled()<br>
&#9;&#9;vec = np.asarray(vector, dtype=np.float32)<br>
&#9;&#9;gl.glUniform4f(self._uniform_location(name), float(vec[0]), float(vec[1]), float(vec[2]), float(vec[3]))<br>
<br>
&#9;def set_uniform_float(self, name: str, value: float):<br>
&#9;&#9;self._ensure_compiled()<br>
&#9;&#9;gl.glUniform1f(self._uniform_location(name), float(value))<br>
<br>
&#9;def set_uniform_int(self, name: str, value: int):<br>
&#9;&#9;self._ensure_compiled()<br>
&#9;&#9;gl.glUniform1i(self._uniform_location(name), int(value))<br>
<br>
<br>
GL_TYPE_MAP = {<br>
&#9;VertexAttribType.FLOAT32: gl.GL_FLOAT,<br>
&#9;VertexAttribType.INT32:   gl.GL_INT,<br>
&#9;VertexAttribType.UINT32:  gl.GL_UNSIGNED_INT,<br>
}<br>
<br>
class OpenGLMeshHandle(MeshHandle):<br>
&#9;def __init__(self, mesh: Mesh):<br>
&#9;&#9;self._mesh = mesh<br>
&#9;&#9;if self._mesh.type == &quot;triangles&quot;:<br>
&#9;&#9;&#9;if self._mesh.vertex_normals is None:<br>
&#9;&#9;&#9;&#9;self._mesh.compute_vertex_normals()<br>
&#9;&#9;self._vao: int | None = None<br>
&#9;&#9;self._vbo: int | None = None<br>
&#9;&#9;self._ebo: int | None = None<br>
&#9;&#9;self._index_count = self._mesh.indices.size<br>
&#9;&#9;self._upload()<br>
<br>
&#9;def _upload(self):<br>
&#9;&#9;buf = self._mesh.interleaved_buffer()<br>
&#9;&#9;layout = self._mesh.get_vertex_layout()<br>
<br>
&#9;&#9;self._vao = gl.glGenVertexArrays(1)<br>
&#9;&#9;self._vbo = gl.glGenBuffers(1)<br>
&#9;&#9;self._ebo = gl.glGenBuffers(1)<br>
<br>
&#9;&#9;gl.glBindVertexArray(self._vao)<br>
<br>
&#9;&#9;gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)<br>
&#9;&#9;gl.glBufferData(gl.GL_ARRAY_BUFFER, buf.nbytes, buf, gl.GL_STATIC_DRAW)<br>
<br>
&#9;&#9;gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self._ebo)<br>
&#9;&#9;gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self._mesh.indices.nbytes, self._mesh.indices, gl.GL_STATIC_DRAW)<br>
<br>
<br>
&#9;&#9;for index, attr in enumerate(layout.attributes):<br>
&#9;&#9;&#9;gl_type = GL_TYPE_MAP[attr.vtype]<br>
&#9;&#9;&#9;gl.glEnableVertexAttribArray(index)<br>
&#9;&#9;&#9;_gl_vertex_attrib_pointer(<br>
&#9;&#9;&#9;&#9;index,<br>
&#9;&#9;&#9;&#9;attr.size,<br>
&#9;&#9;&#9;&#9;gl_type,<br>
&#9;&#9;&#9;&#9;gl.GL_FALSE,<br>
&#9;&#9;&#9;&#9;layout.stride,<br>
&#9;&#9;&#9;&#9;ctypes.c_void_p(attr.offset),<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;gl.glBindVertexArray(0)<br>
<br>
<br>
&#9;def draw(self):<br>
&#9;&#9;gl.glEnable(gl.GL_DEPTH_TEST)<br>
&#9;&#9;gl.glBindVertexArray(self._vao or 0)<br>
<br>
&#9;&#9;mode = gl.GL_TRIANGLES<br>
&#9;&#9;if getattr(self._mesh, &quot;type&quot;, &quot;triangles&quot;) == &quot;lines&quot;:<br>
&#9;&#9;&#9;mode = gl.GL_LINES<br>
<br>
&#9;&#9;gl.glDrawElements(mode, self._index_count, gl.GL_UNSIGNED_INT, ctypes.c_void_p(0))<br>
&#9;&#9;gl.glBindVertexArray(0)<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;if self._vao is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;gl.glDeleteVertexArrays(1, [self._vao])<br>
&#9;&#9;gl.glDeleteBuffers(1, [self._vbo])<br>
&#9;&#9;gl.glDeleteBuffers(1, [self._ebo])<br>
&#9;&#9;self._vao = self._vbo = self._ebo = None<br>
<br>
<br>
class OpenGLPolylineHandle(PolylineHandle):<br>
&#9;def __init__(self, vertices: np.ndarray, indices: np.ndarray | None, is_strip: bool):<br>
&#9;&#9;self._vertices = vertices.astype(np.float32)<br>
&#9;&#9;self._indices = indices.astype(np.uint32) if indices is not None else None<br>
&#9;&#9;self._is_strip = is_strip<br>
&#9;&#9;self._vao: int | None = None<br>
&#9;&#9;self._vbo: int | None = None<br>
&#9;&#9;self._ebo: int | None = None<br>
&#9;&#9;self._upload()<br>
<br>
&#9;def _upload(self):<br>
&#9;&#9;vertex_block = self._vertices.ravel()<br>
&#9;&#9;self._vao = gl.glGenVertexArrays(1)<br>
&#9;&#9;self._vbo = gl.glGenBuffers(1)<br>
&#9;&#9;gl.glBindVertexArray(self._vao)<br>
&#9;&#9;gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._vbo)<br>
&#9;&#9;gl.glBufferData(gl.GL_ARRAY_BUFFER, vertex_block.nbytes, vertex_block, gl.GL_STATIC_DRAW)<br>
&#9;&#9;if self._indices is not None:<br>
&#9;&#9;&#9;self._ebo = gl.glGenBuffers(1)<br>
&#9;&#9;&#9;gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self._ebo)<br>
&#9;&#9;&#9;gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, self._indices.nbytes, self._indices, gl.GL_STATIC_DRAW)<br>
&#9;&#9;stride = 3 * 4<br>
&#9;&#9;gl.glEnableVertexAttribArray(0)<br>
&#9;&#9;_gl_vertex_attrib_pointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))<br>
&#9;&#9;gl.glBindVertexArray(0)<br>
<br>
&#9;def draw(self):<br>
&#9;&#9;mode = gl.GL_LINE_STRIP if self._is_strip else gl.GL_LINES<br>
&#9;&#9;gl.glBindVertexArray(self._vao or 0)<br>
&#9;&#9;gl.glEnable(gl.GL_DEPTH_TEST)<br>
&#9;&#9;if self._indices is not None:<br>
&#9;&#9;&#9;gl.glDrawElements(mode, self._indices.size, gl.GL_UNSIGNED_INT, ctypes.c_void_p(0))<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;gl.glDrawArrays(mode, 0, self._vertices.shape[0])<br>
&#9;&#9;gl.glBindVertexArray(0)<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;if self._vao is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;gl.glDeleteVertexArrays(1, [self._vao])<br>
&#9;&#9;gl.glDeleteBuffers(1, [self._vbo])<br>
&#9;&#9;if self._ebo is not None:<br>
&#9;&#9;&#9;gl.glDeleteBuffers(1, [self._ebo])<br>
&#9;&#9;self._vao = self._vbo = self._ebo = None<br>
<br>
<br>
class OpenGLTextureHandle(TextureHandle):<br>
&#9;def __init__(self, image_data: np.ndarray, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False):<br>
&#9;&#9;self._handle: int | None = None<br>
&#9;&#9;self._channels = channels<br>
&#9;&#9;self._data = image_data<br>
&#9;&#9;self._size = size<br>
&#9;&#9;self._mipmap = mipmap<br>
&#9;&#9;self._clamp = clamp<br>
&#9;&#9;self._upload()<br>
<br>
&#9;def _upload(self):<br>
&#9;&#9;self._handle = gl.glGenTextures(1)<br>
&#9;&#9;gl.glBindTexture(gl.GL_TEXTURE_2D, self._handle)<br>
&#9;&#9;internal_format = gl.GL_RGBA if self._channels != 1 else gl.GL_RED<br>
&#9;&#9;gl_format = internal_format<br>
&#9;&#9;gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, internal_format, self._size[0], self._size[1], 0, gl_format, gl.GL_UNSIGNED_BYTE, self._data)<br>
&#9;&#9;if self._mipmap:<br>
&#9;&#9;&#9;gl.glGenerateMipmap(gl.GL_TEXTURE_2D)<br>
&#9;&#9;min_filter = gl.GL_LINEAR_MIPMAP_LINEAR if self._mipmap else gl.GL_LINEAR<br>
&#9;&#9;gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, min_filter)<br>
&#9;&#9;gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)<br>
&#9;&#9;wrap_mode = gl.GL_CLAMP_TO_EDGE if self._clamp else gl.GL_REPEAT<br>
&#9;&#9;gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, wrap_mode)<br>
&#9;&#9;gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, wrap_mode)<br>
&#9;&#9;if self._channels == 1:<br>
&#9;&#9;&#9;swizzle = np.array([gl.GL_RED, gl.GL_RED, gl.GL_RED, gl.GL_RED], dtype=np.int32)<br>
&#9;&#9;&#9;gl.glTexParameteriv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_SWIZZLE_RGBA, swizzle)<br>
<br>
&#9;def bind(self, unit: int = 0):<br>
&#9;&#9;gl.glActiveTexture(gl.GL_TEXTURE0 + unit)<br>
&#9;&#9;gl.glBindTexture(gl.GL_TEXTURE_2D, self._handle or 0)<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;if self._handle is not None:<br>
&#9;&#9;&#9;gl.glDeleteTextures(1, [self._handle])<br>
&#9;&#9;&#9;self._handle = None<br>
<br>
<br>
class OpenGLGraphicsBackend(GraphicsBackend):<br>
&#9;def __init__(self):<br>
&#9;&#9;self._ui_buffers: Dict[int, Tuple[int, int]] = {}<br>
<br>
&#9;def ensure_ready(self):<br>
&#9;&#9;global _OPENGL_INITED<br>
&#9;&#9;if _OPENGL_INITED:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;gl.glEnable(gl.GL_DEPTH_TEST)<br>
&#9;&#9;gl.glEnable(gl.GL_CULL_FACE)<br>
&#9;&#9;gl.glCullFace(gl.GL_BACK)<br>
&#9;&#9;gl.glFrontFace(gl.GL_CCW)<br>
&#9;&#9;_OPENGL_INITED = True<br>
<br>
&#9;def read_pixel(self, framebuffer, x: int, y: int):<br>
&#9;&#9;# привязываем FBO, из которого читаем<br>
&#9;&#9;self.bind_framebuffer(framebuffer)<br>
&#9;&#9;#print(&quot;Reading pixel at:&quot;, x, y, &quot;from framebuffer:&quot;, framebuffer._fbo)  # --- DEBUG ---<br>
<br>
&#9;&#9;data = GL.glReadPixels(x, y, 1, 1, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)<br>
&#9;&#9;# data = 4 байта<br>
&#9;&#9;if isinstance(data, (bytes, bytearray)):<br>
&#9;&#9;&#9;arr = np.frombuffer(data, dtype=np.uint8)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;arr = np.array(data, dtype=np.uint8)<br>
<br>
&#9;&#9;r, g, b, a = arr<br>
&#9;&#9;return r / 255.0, g / 255.0, b / 255.0, a / 255.0<br>
<br>
&#9;def set_viewport(self, x: int, y: int, w: int, h: int):<br>
&#9;&#9;gl.glViewport(x, y, w, h)<br>
<br>
&#9;def enable_scissor(self, x: int, y: int, w: int, h: int):<br>
&#9;&#9;gl.glEnable(gl.GL_SCISSOR_TEST)<br>
&#9;&#9;gl.glScissor(x, y, w, h)<br>
<br>
&#9;def disable_scissor(self):<br>
&#9;&#9;gl.glDisable(gl.GL_SCISSOR_TEST)<br>
<br>
&#9;def clear_color_depth(self, color):<br>
&#9;&#9;gl.glClearColor(float(color[0]), float(color[1]), float(color[2]), float(color[3]))<br>
&#9;&#9;gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)<br>
<br>
&#9;def set_depth_test(self, enabled: bool):<br>
&#9;&#9;if enabled:<br>
&#9;&#9;&#9;gl.glEnable(gl.GL_DEPTH_TEST)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;gl.glDisable(gl.GL_DEPTH_TEST)<br>
<br>
&#9;def set_depth_mask(self, enabled: bool):<br>
&#9;&#9;gl.glDepthMask(gl.GL_TRUE if enabled else gl.GL_FALSE)<br>
<br>
&#9;def set_depth_func(self, func: str):<br>
&#9;&#9;mapping = {&quot;less&quot;: gl.GL_LESS, &quot;lequal&quot;: gl.GL_LEQUAL}<br>
&#9;&#9;gl.glDepthFunc(mapping.get(func, gl.GL_LESS))<br>
<br>
&#9;def set_cull_face(self, enabled: bool):<br>
&#9;&#9;if enabled:<br>
&#9;&#9;&#9;gl.glEnable(gl.GL_CULL_FACE)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;gl.glDisable(gl.GL_CULL_FACE)<br>
<br>
&#9;def set_blend(self, enabled: bool):<br>
&#9;&#9;if enabled:<br>
&#9;&#9;&#9;gl.glEnable(gl.GL_BLEND)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;gl.glDisable(gl.GL_BLEND)<br>
<br>
&#9;def set_blend_func(self, src: str, dst: str):<br>
&#9;&#9;mapping = {<br>
&#9;&#9;&#9;&quot;src_alpha&quot;: gl.GL_SRC_ALPHA,<br>
&#9;&#9;&#9;&quot;one_minus_src_alpha&quot;: gl.GL_ONE_MINUS_SRC_ALPHA,<br>
&#9;&#9;&#9;&quot;one&quot;: gl.GL_ONE,<br>
&#9;&#9;&#9;&quot;zero&quot;: gl.GL_ZERO,<br>
&#9;&#9;}<br>
&#9;&#9;gl.glBlendFunc(mapping.get(src, gl.GL_SRC_ALPHA), mapping.get(dst, gl.GL_ONE_MINUS_SRC_ALPHA))<br>
<br>
&#9;def create_shader(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None) -&gt; ShaderHandle:<br>
&#9;&#9;return OpenGLShaderHandle(vertex_source, fragment_source, geometry_source)<br>
<br>
&#9;def create_mesh(self, mesh: Mesh) -&gt; MeshHandle:<br>
&#9;&#9;return OpenGLMeshHandle(mesh)<br>
<br>
&#9;def create_polyline(self, polyline) -&gt; PolylineHandle:<br>
&#9;&#9;return OpenGLPolylineHandle(polyline.vertices, polyline.indices, polyline.is_strip)<br>
<br>
&#9;def create_texture(self, image_data, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False) -&gt; TextureHandle:<br>
&#9;&#9;return OpenGLTextureHandle(image_data, size, channels=channels, mipmap=mipmap, clamp=clamp)<br>
<br>
&#9;def draw_ui_vertices(self, context_key: int, vertices):<br>
&#9;&#9;vao, vbo = self._ui_buffers.get(context_key, (None, None))<br>
&#9;&#9;if vao is None:<br>
&#9;&#9;&#9;vao = gl.glGenVertexArrays(1)<br>
&#9;&#9;&#9;vbo = gl.glGenBuffers(1)<br>
&#9;&#9;&#9;self._ui_buffers[context_key] = (vao, vbo)<br>
&#9;&#9;gl.glBindVertexArray(vao)<br>
&#9;&#9;gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)<br>
&#9;&#9;gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_DYNAMIC_DRAW)<br>
&#9;&#9;gl.glEnableVertexAttribArray(0)<br>
&#9;&#9;_gl_vertex_attrib_pointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 0, ctypes.c_void_p(0))<br>
&#9;&#9;gl.glDisableVertexAttribArray(1)<br>
&#9;&#9;gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)<br>
&#9;&#9;gl.glBindVertexArray(0)<br>
<br>
&#9;FS_VERTS = np.array(<br>
&#9;[<br>
&#9;&#9;[-1, -1, 0, 0],<br>
&#9;&#9;[ 1, -1, 1, 0],<br>
&#9;&#9;[-1,  1, 0, 1],<br>
&#9;&#9;[ 1,  1, 1, 1],<br>
&#9;],<br>
&#9;dtype=np.float32,<br>
&#9;)<br>
<br>
&#9;def draw_ui_textured_quad(self, context_key: int):<br>
&#9;&#9;vao, vbo = self._ui_buffers.get(context_key, (None, None))<br>
&#9;&#9;if vao is None:<br>
&#9;&#9;&#9;vao = gl.glGenVertexArrays(1)<br>
&#9;&#9;&#9;vbo = gl.glGenBuffers(1)<br>
&#9;&#9;&#9;self._ui_buffers[context_key] = (vao, vbo)<br>
&#9;&#9;gl.glBindVertexArray(vao)<br>
&#9;&#9;gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)<br>
&#9;&#9;gl.glBufferData(gl.GL_ARRAY_BUFFER, self.FS_VERTS.nbytes, self.FS_VERTS, gl.GL_DYNAMIC_DRAW)<br>
&#9;&#9;stride = 4 * 4<br>
&#9;&#9;gl.glEnableVertexAttribArray(0)<br>
&#9;&#9;_gl_vertex_attrib_pointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))<br>
&#9;&#9;gl.glEnableVertexAttribArray(1)<br>
&#9;&#9;_gl_vertex_attrib_pointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))<br>
&#9;&#9;gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)<br>
&#9;&#9;gl.glBindVertexArray(0)<br>
<br>
&#9;def set_polygon_mode(self, mode: str):<br>
&#9;&#9;from OpenGL import GL as gl<br>
&#9;&#9;if mode == &quot;line&quot;:<br>
&#9;&#9;&#9;gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)<br>
<br>
&#9;def set_cull_face_enabled(self, enabled: bool):<br>
&#9;&#9;from OpenGL import GL as gl<br>
&#9;&#9;if enabled:<br>
&#9;&#9;&#9;gl.glEnable(gl.GL_CULL_FACE)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;gl.glDisable(gl.GL_CULL_FACE)<br>
<br>
&#9;def set_depth_test_enabled(self, enabled: bool):<br>
&#9;&#9;from OpenGL import GL as gl<br>
&#9;&#9;if enabled:<br>
&#9;&#9;&#9;gl.glEnable(gl.GL_DEPTH_TEST)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;gl.glDisable(gl.GL_DEPTH_TEST)<br>
<br>
&#9;def set_depth_write_enabled(self, enabled: bool):<br>
&#9;&#9;from OpenGL import GL as gl<br>
&#9;&#9;gl.glDepthMask(gl.GL_TRUE if enabled else gl.GL_FALSE)<br>
<br>
&#9;def create_framebuffer(self, size: Tuple[int, int]) -&gt; FramebufferHandle:<br>
&#9;&#9;return OpenGLFramebufferHandle(size)<br>
<br>
&#9;def bind_framebuffer(self, framebuffer: FramebufferHandle | None):<br>
&#9;&#9;if framebuffer is None:<br>
&#9;&#9;&#9;gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;assert isinstance(framebuffer, OpenGLFramebufferHandle)<br>
&#9;&#9;&#9;gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, framebuffer._fbo or 0)<br>
<br>
class _OpenGLColorTextureHandle(TextureHandle):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Лёгкая обёртка над уже созданной GL-текстурой.<br>
&#9;Жизненный цикл управляется фреймбуфером, delete() ничего не делает.<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, tex_id: int):<br>
&#9;&#9;self._tex_id = tex_id<br>
<br>
&#9;def bind(self, unit: int = 0):<br>
&#9;&#9;gl.glActiveTexture(gl.GL_TEXTURE0 + unit)<br>
&#9;&#9;gl.glBindTexture(gl.GL_TEXTURE_2D, self._tex_id or 0)<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;# Фактическое удаление делает владелец FBO<br>
&#9;&#9;pass<br>
<br>
&#9;def _set_tex_id(self, tex_id: int):<br>
&#9;&#9;self._tex_id = tex_id<br>
<br>
class OpenGLFramebufferHandle(FramebufferHandle):<br>
&#9;def __init__(self, size: Tuple[int, int]):<br>
&#9;&#9;self._size = size<br>
&#9;&#9;self._fbo: int | None = None<br>
&#9;&#9;self._color_tex: int | None = None<br>
&#9;&#9;self._depth_rb: int | None = None<br>
&#9;&#9;self._color_handle = _OpenGLColorTextureHandle(0)<br>
&#9;&#9;self._create()<br>
<br>
&#9;def _create(self):<br>
&#9;&#9;w, h = self._size<br>
<br>
&#9;&#9;# создаём FBO<br>
&#9;&#9;self._fbo = gl.glGenFramebuffers(1)<br>
&#9;&#9;gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)<br>
<br>
&#9;&#9;# цветовой attachment (RGBA8)<br>
&#9;&#9;self._color_tex = gl.glGenTextures(1)<br>
&#9;&#9;gl.glBindTexture(gl.GL_TEXTURE_2D, self._color_tex)<br>
&#9;&#9;gl.glTexImage2D(<br>
&#9;&#9;&#9;gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8,<br>
&#9;&#9;&#9;w, h, 0,<br>
&#9;&#9;&#9;gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None<br>
&#9;&#9;)<br>
&#9;&#9;gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)<br>
&#9;&#9;gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)<br>
&#9;&#9;gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)<br>
&#9;&#9;gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)<br>
<br>
&#9;&#9;gl.glFramebufferTexture2D(<br>
&#9;&#9;&#9;gl.GL_FRAMEBUFFER,<br>
&#9;&#9;&#9;gl.GL_COLOR_ATTACHMENT0,<br>
&#9;&#9;&#9;gl.GL_TEXTURE_2D,<br>
&#9;&#9;&#9;self._color_tex,<br>
&#9;&#9;&#9;0,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;# depth renderbuffer<br>
&#9;&#9;self._depth_rb = gl.glGenRenderbuffers(1)<br>
&#9;&#9;gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._depth_rb)<br>
&#9;&#9;gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, w, h)<br>
&#9;&#9;gl.glFramebufferRenderbuffer(<br>
&#9;&#9;&#9;gl.GL_FRAMEBUFFER,<br>
&#9;&#9;&#9;gl.GL_DEPTH_ATTACHMENT,<br>
&#9;&#9;&#9;gl.GL_RENDERBUFFER,<br>
&#9;&#9;&#9;self._depth_rb,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)<br>
&#9;&#9;if status != gl.GL_FRAMEBUFFER_COMPLETE:<br>
&#9;&#9;&#9;gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)<br>
&#9;&#9;&#9;raise RuntimeError(f&quot;Framebuffer is incomplete: 0x{status:X}&quot;)<br>
<br>
&#9;&#9;gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)<br>
<br>
&#9;&#9;# обновляем handle текстуры<br>
&#9;&#9;self._color_handle._set_tex_id(self._color_tex)<br>
<br>
&#9;def resize(self, size: Tuple[int, int]):<br>
&#9;&#9;if size == self._size and self._fbo is not None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self.delete()<br>
&#9;&#9;self._size = size<br>
&#9;&#9;self._create()<br>
<br>
&#9;def color_texture(self) -&gt; TextureHandle:<br>
&#9;&#9;return self._color_handle<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;if self._fbo is not None:<br>
&#9;&#9;&#9;gl.glDeleteFramebuffers(1, [self._fbo])<br>
&#9;&#9;&#9;self._fbo = None<br>
&#9;&#9;if self._color_tex is not None:<br>
&#9;&#9;&#9;gl.glDeleteTextures(1, [self._color_tex])<br>
&#9;&#9;&#9;self._color_tex = None<br>
&#9;&#9;if self._depth_rb is not None:<br>
&#9;&#9;&#9;gl.glDeleteRenderbuffers(1, [self._depth_rb])<br>
&#9;&#9;&#9;self._depth_rb = None<br>
<!-- END SCAT CODE -->
</body>
</html>
