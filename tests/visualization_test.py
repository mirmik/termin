from unittest import mock

import numpy as np
import pytest
from PIL import Image

import termin.visualization.core.mesh as mesh_module
import termin.visualization.render.shader as shader_module
import termin.visualization.render.texture as texture_module
from termin.visualization.core.mesh import MeshDrawable
from termin.visualization.render.texture import Texture
from termin.visualization.ui.elements import UIRectangle


class FakeShaderGL:
    GL_VERTEX_SHADER = 0x8B31
    GL_FRAGMENT_SHADER = 0x8B30
    GL_COMPILE_STATUS = 0x8B81
    GL_LINK_STATUS = 0x8B82

    def __init__(self, shader_status=None, shader_logs=None, program_status=None, program_logs=None):
        self.shader_status = list(shader_status or [])
        self.shader_logs = list(shader_logs or [])
        self.program_status = list(program_status or [])
        self.program_logs = list(program_logs or [])
        self.next_id = 1
        self.created_shaders = []
        self.created_programs = []

    def _next_status(self, queue):
        return queue.pop(0) if queue else 1

    def glCreateShader(self, shader_type):
        self.created_shaders.append(shader_type)
        shader_id = self.next_id
        self.next_id += 1
        return shader_id

    def glShaderSource(self, shader, source):
        return None

    def glCompileShader(self, shader):
        return None

    @staticmethod
    def _write_pointer(ptr, value):
        if hasattr(ptr, "contents"):
            ptr.contents.value = value
        else:
            ptr._obj.value = value

    def glGetShaderiv(self, shader, pname, params):
        self._write_pointer(params, self._next_status(self.shader_status))

    def glGetShaderInfoLog(self, shader):
        if self.shader_logs:
            return self.shader_logs.pop(0)
        return b""

    def glCreateProgram(self):
        program_id = self.next_id
        self.next_id += 1
        self.created_programs.append(program_id)
        return program_id

    def glAttachShader(self, program, shader):
        return None

    def glLinkProgram(self, program):
        return None

    def glGetProgramiv(self, program, pname, params):
        self._write_pointer(params, self._next_status(self.program_status))

    def glGetProgramInfoLog(self, program):
        if self.program_logs:
            return self.program_logs.pop(0)
        return b""

    def glDetachShader(self, program, shader):
        return None

    def glDeleteShader(self, shader):
        return None

    def glDeleteProgram(self, program):
        return None

    def glUseProgram(self, program):
        return None

    def glGetUniformLocation(self, program, name):
        return 0

    def glUniformMatrix4fv(self, location, count, transpose, value):
        return None

    def glUniform3f(self, location, x, y, z):
        return None

    def glUniform1f(self, location, value):
        return None

    def glUniform1i(self, location, value):
        return None


class FakeMeshGL:
    GL_ARRAY_BUFFER = 0x8892
    GL_ELEMENT_ARRAY_BUFFER = 0x8893
    GL_STATIC_DRAW = 0x88E4
    GL_FLOAT = 0x1406
    GL_FALSE = 0
    GL_TRIANGLES = 0x0004
    GL_UNSIGNED_INT = 0x1405
    GL_DEPTH_TEST = 0x0B71

    def __init__(self):
        self.next_id = 1
        self.bound_vao = None
        self.bound_vbo = None
        self.bound_ebo = None
        self.enabled = set()
        self.draw_calls = 0
        self.last_draw_count = 0
        self.array_buffer_size = 0
        self.element_buffer_size = 0

    def _new_id(self):
        result = self.next_id
        self.next_id += 1
        return result

    def glGenVertexArrays(self, count):
        return self._new_id()

    def glGenBuffers(self, count):
        return self._new_id()

    def glBindVertexArray(self, vao):
        self.bound_vao = vao

    def glBindBuffer(self, target, buffer_id):
        if target == self.GL_ARRAY_BUFFER:
            self.bound_vbo = buffer_id
        elif target == self.GL_ELEMENT_ARRAY_BUFFER:
            self.bound_ebo = buffer_id

    def glBufferData(self, target, size, data, usage):
        if target == self.GL_ARRAY_BUFFER:
            self.array_buffer_size = size
        elif target == self.GL_ELEMENT_ARRAY_BUFFER:
            self.element_buffer_size = size

    def glEnableVertexAttribArray(self, location):
        return None

    def glVertexAttribPointer(self, index, size, dtype, normalized, stride, pointer):
        return None

    def glEnable(self, cap):
        self.enabled.add(cap)

    def glDrawElements(self, mode, count, dtype, indices):
        self.draw_calls += 1
        self.last_draw_count = count

    def glDeleteVertexArrays(self, count, vaos):
        return None

    def glDeleteBuffers(self, count, buffers):
        return None


class FakeTextureGL:
    GL_TEXTURE_2D = 0x0DE1
    GL_TEXTURE0 = 0x84C0
    GL_RGBA = 0x1908
    GL_UNSIGNED_BYTE = 0x1401
    GL_LINEAR_MIPMAP_LINEAR = 0x2703
    GL_LINEAR = 0x2601
    GL_REPEAT = 0x2901
    GL_TEXTURE_MIN_FILTER = 0x2801
    GL_TEXTURE_MAG_FILTER = 0x2800
    GL_TEXTURE_WRAP_S = 0x2802
    GL_TEXTURE_WRAP_T = 0x2803

    def __init__(self):
        self.generated_ids = []
        self.bound_texture = None
        self.active_unit = None
        self.tex_image_calls = 0
        self.params = []
        self.mipmaps = 0

    def glGenTextures(self, count):
        tex_id = len(self.generated_ids) + 1
        self.generated_ids.append(tex_id)
        return tex_id

    def glBindTexture(self, target, tex_id):
        self.bound_texture = tex_id

    def glTexImage2D(self, *args, **kwargs):
        self.tex_image_calls += 1

    def glGenerateMipmap(self, target):
        self.mipmaps += 1

    def glTexParameteri(self, target, pname, param):
        self.params.append((pname, param))

    def glActiveTexture(self, unit):
        self.active_unit = unit



def test_ui_rectangle_clip_vertices():
    rect = UIRectangle(position=(0.25, 0.25), size=(0.5, 0.5))
    verts = rect._to_clip_vertices()
    expected = np.array(
        [
            [-0.5, 0.5],
            [0.5, 0.5],
            [-0.5, -0.5],
            [0.5, -0.5],
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(verts, expected)
