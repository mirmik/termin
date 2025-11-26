<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/shader.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Shader wrapper delegating compilation and uniform uploads to a graphics backend.&quot;&quot;&quot;

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from .backends import get_default_graphics_backend
from .backends.base import GraphicsBackend, ShaderHandle


class ShaderCompilationError(RuntimeError):
    &quot;&quot;&quot;Raised when GLSL compilation or program linking fails.&quot;&quot;&quot;


class ShaderProgram:
    &quot;&quot;&quot;A GLSL shader program (vertex + fragment).

    Uniform setters inside the class assume column-major matrices and they set the
    combined MVP transform ``P * V * M`` in homogeneous coordinates.
    &quot;&quot;&quot;

    def __init__(
        self,
        vertex_source: str,
        fragment_source: str,
        geometry_source: str | None = None
    ):
        self.vertex_source = vertex_source
        self.fragment_source = fragment_source
        self.geometry_source = geometry_source
        self._compiled = False
        self._handle: ShaderHandle | None = None
        self._backend: GraphicsBackend | None = None

    def __post_init__(self):
        self._handle = None
        self._backend = None

    @staticmethod
    def default_shader() -&gt; &quot;ShaderProgram&quot;:
        vert = &quot;&quot;&quot;#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;     // n_world = (M^{-1})^T * n_model
out vec3 v_world_pos;  // p_world = M * p_model

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;

    gl_Position = u_projection * u_view * world;
}
&quot;&quot;&quot;

        frag = &quot;&quot;&quot;#version 330 core

in vec3 v_normal;
in vec3 v_world_pos;

uniform vec4 u_color;        // base material color (RGBA)
uniform vec3 u_light_dir;    // direction from light to object (world space)
uniform vec3 u_light_color;  // light tint

out vec4 FragColor;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_dir);

    // Lambertian diffuse term: I_diffuse = max(dot(N, L), 0)
    float ndotl = max(dot(N, L), 0.0);

    const float ambient_strength = 0.2;
    const float diffuse_strength = 0.8;

    vec3 ambient = ambient_strength * u_color.rgb;
    vec3 diffuse = diffuse_strength * ndotl * u_color.rgb;

    vec3 color = (ambient + diffuse) * u_light_color;
    FragColor = vec4(color, u_color.a);
}
&quot;&quot;&quot;

        return ShaderProgram(vertex_source=vert, fragment_source=frag)

    def ensure_ready(self, graphics: GraphicsBackend | None = None):
        if self._compiled:
            return
        backend = graphics or self._backend or get_default_graphics_backend()
        if backend is None:
            raise RuntimeError(&quot;Graphics backend is not available for shader compilation.&quot;)
        self._backend = backend
        self._handle = backend.create_shader(self.vertex_source, self.fragment_source, self.geometry_source)
        self._compiled = True

    def _require_handle(self) -&gt; ShaderHandle:
        if self._handle is None:
            raise RuntimeError(&quot;ShaderProgram is not compiled. Call ensure_ready() first.&quot;)
        return self._handle

    def use(self):
        self._require_handle().use()

    def stop(self):
        if self._handle:
            self._handle.stop()

    def delete(self):
        if self._handle:
            self._handle.delete()
            self._handle = None

    def set_uniform_matrix4(self, name: str, matrix: np.ndarray):
        &quot;&quot;&quot;Upload a 4x4 matrix (float32) to uniform ``name``.&quot;&quot;&quot;
        self._require_handle().set_uniform_matrix4(name, matrix)

    def set_uniform_vec2(self, name: str, vector: np.ndarray):
        self._require_handle().set_uniform_vec2(name, vector)

    def set_uniform_vec3(self, name: str, vector: np.ndarray):
        self._require_handle().set_uniform_vec3(name, vector)

    def set_uniform_vec4(self, name: str, vector: np.ndarray):
        self._require_handle().set_uniform_vec4(name, vector)

    def set_uniform_float(self, name: str, value: float):
        self._require_handle().set_uniform_float(name, value)

    def set_uniform_int(self, name: str, value: int):
        self._require_handle().set_uniform_int(name, value)

    def set_uniform_auto(self, name: str, value: Any):
        &quot;&quot;&quot;Best-effort setter that infers uniform type based on ``value``.&quot;&quot;&quot;
        if isinstance(value, (list, tuple, np.ndarray)):
            arr = np.asarray(value)
            if arr.shape == (4, 4):
                self.set_uniform_matrix4(name, arr)
            elif arr.shape == (2,):
                self.set_uniform_vec2(name, arr)
            elif arr.shape == (3,):
                self.set_uniform_vec3(name, arr)
            elif arr.shape == (4,):
                self.set_uniform_vec4(name, arr)
            else:
                raise ValueError(f&quot;Unsupported uniform array shape for {name}: {arr.shape}&quot;)
        elif isinstance(value, bool):
            self.set_uniform_int(name, int(value))
        elif isinstance(value, int):
            self.set_uniform_int(name, value)
        else:
            self.set_uniform_float(name, float(value))

    @classmethod
    def from_files(cls, vertex_path: str | Path, fragment_path: str | Path) -&gt; &quot;ShaderProgram&quot;:
        vertex_source = Path(vertex_path).read_text(encoding=&quot;utf-8&quot;)
        fragment_source = Path(fragment_path).read_text(encoding=&quot;utf-8&quot;)
        return cls(vertex_source=vertex_source, fragment_source=fragment_source)

</code></pre>
</body>
</html>
