<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/shader.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Shader wrapper delegating compilation and uniform uploads to a graphics backend.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from pathlib import Path<br>
from typing import Any, Optional<br>
<br>
import numpy as np<br>
<br>
from .backends import get_default_graphics_backend<br>
from .backends.base import GraphicsBackend, ShaderHandle<br>
<br>
<br>
class ShaderCompilationError(RuntimeError):<br>
    &quot;&quot;&quot;Raised when GLSL compilation or program linking fails.&quot;&quot;&quot;<br>
<br>
<br>
class ShaderProgram:<br>
    &quot;&quot;&quot;A GLSL shader program (vertex + fragment).<br>
<br>
    Uniform setters inside the class assume column-major matrices and they set the<br>
    combined MVP transform ``P * V * M`` in homogeneous coordinates.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        vertex_source: str,<br>
        fragment_source: str,<br>
        geometry_source: str | None = None<br>
    ):<br>
        self.vertex_source = vertex_source<br>
        self.fragment_source = fragment_source<br>
        self.geometry_source = geometry_source<br>
        self._compiled = False<br>
        self._handle: ShaderHandle | None = None<br>
        self._backend: GraphicsBackend | None = None<br>
<br>
    def __post_init__(self):<br>
        self._handle = None<br>
        self._backend = None<br>
<br>
    @staticmethod<br>
    def default_shader() -&gt; &quot;ShaderProgram&quot;:<br>
        vert = &quot;&quot;&quot;#version 330 core<br>
<br>
layout(location = 0) in vec3 a_position;<br>
layout(location = 1) in vec3 a_normal;<br>
<br>
uniform mat4 u_model;<br>
uniform mat4 u_view;<br>
uniform mat4 u_projection;<br>
<br>
out vec3 v_normal;     // n_world = (M^{-1})^T * n_model<br>
out vec3 v_world_pos;  // p_world = M * p_model<br>
<br>
void main() {<br>
    vec4 world = u_model * vec4(a_position, 1.0);<br>
    v_world_pos = world.xyz;<br>
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;<br>
<br>
    gl_Position = u_projection * u_view * world;<br>
}<br>
&quot;&quot;&quot;<br>
<br>
        frag = &quot;&quot;&quot;#version 330 core<br>
<br>
in vec3 v_normal;<br>
in vec3 v_world_pos;<br>
<br>
uniform vec4 u_color;        // base material color (RGBA)<br>
uniform vec3 u_light_dir;    // direction from light to object (world space)<br>
uniform vec3 u_light_color;  // light tint<br>
<br>
out vec4 FragColor;<br>
<br>
void main() {<br>
    vec3 N = normalize(v_normal);<br>
    vec3 L = normalize(-u_light_dir);<br>
<br>
    // Lambertian diffuse term: I_diffuse = max(dot(N, L), 0)<br>
    float ndotl = max(dot(N, L), 0.0);<br>
<br>
    const float ambient_strength = 0.2;<br>
    const float diffuse_strength = 0.8;<br>
<br>
    vec3 ambient = ambient_strength * u_color.rgb;<br>
    vec3 diffuse = diffuse_strength * ndotl * u_color.rgb;<br>
<br>
    vec3 color = (ambient + diffuse) * u_light_color;<br>
    FragColor = vec4(color, u_color.a);<br>
}<br>
&quot;&quot;&quot;<br>
<br>
        return ShaderProgram(vertex_source=vert, fragment_source=frag)<br>
<br>
    def ensure_ready(self, graphics: GraphicsBackend | None = None):<br>
        if self._compiled:<br>
            return<br>
        backend = graphics or self._backend or get_default_graphics_backend()<br>
        if backend is None:<br>
            raise RuntimeError(&quot;Graphics backend is not available for shader compilation.&quot;)<br>
        self._backend = backend<br>
        self._handle = backend.create_shader(self.vertex_source, self.fragment_source, self.geometry_source)<br>
        self._compiled = True<br>
<br>
    def _require_handle(self) -&gt; ShaderHandle:<br>
        if self._handle is None:<br>
            raise RuntimeError(&quot;ShaderProgram is not compiled. Call ensure_ready() first.&quot;)<br>
        return self._handle<br>
<br>
    def use(self):<br>
        self._require_handle().use()<br>
<br>
    def stop(self):<br>
        if self._handle:<br>
            self._handle.stop()<br>
<br>
    def delete(self):<br>
        if self._handle:<br>
            self._handle.delete()<br>
            self._handle = None<br>
<br>
    def set_uniform_matrix4(self, name: str, matrix: np.ndarray):<br>
        &quot;&quot;&quot;Upload a 4x4 matrix (float32) to uniform ``name``.&quot;&quot;&quot;<br>
        self._require_handle().set_uniform_matrix4(name, matrix)<br>
<br>
    def set_uniform_vec2(self, name: str, vector: np.ndarray):<br>
        self._require_handle().set_uniform_vec2(name, vector)<br>
<br>
    def set_uniform_vec3(self, name: str, vector: np.ndarray):<br>
        self._require_handle().set_uniform_vec3(name, vector)<br>
<br>
    def set_uniform_vec4(self, name: str, vector: np.ndarray):<br>
        self._require_handle().set_uniform_vec4(name, vector)<br>
<br>
    def set_uniform_float(self, name: str, value: float):<br>
        self._require_handle().set_uniform_float(name, value)<br>
<br>
    def set_uniform_int(self, name: str, value: int):<br>
        self._require_handle().set_uniform_int(name, value)<br>
<br>
    def set_uniform_auto(self, name: str, value: Any):<br>
        &quot;&quot;&quot;Best-effort setter that infers uniform type based on ``value``.&quot;&quot;&quot;<br>
        if isinstance(value, (list, tuple, np.ndarray)):<br>
            arr = np.asarray(value)<br>
            if arr.shape == (4, 4):<br>
                self.set_uniform_matrix4(name, arr)<br>
            elif arr.shape == (2,):<br>
                self.set_uniform_vec2(name, arr)<br>
            elif arr.shape == (3,):<br>
                self.set_uniform_vec3(name, arr)<br>
            elif arr.shape == (4,):<br>
                self.set_uniform_vec4(name, arr)<br>
            else:<br>
                raise ValueError(f&quot;Unsupported uniform array shape for {name}: {arr.shape}&quot;)<br>
        elif isinstance(value, bool):<br>
            self.set_uniform_int(name, int(value))<br>
        elif isinstance(value, int):<br>
            self.set_uniform_int(name, value)<br>
        else:<br>
            self.set_uniform_float(name, float(value))<br>
<br>
    @classmethod<br>
    def from_files(cls, vertex_path: str | Path, fragment_path: str | Path) -&gt; &quot;ShaderProgram&quot;:<br>
        vertex_source = Path(vertex_path).read_text(encoding=&quot;utf-8&quot;)<br>
        fragment_source = Path(fragment_path).read_text(encoding=&quot;utf-8&quot;)<br>
        return cls(vertex_source=vertex_source, fragment_source=fragment_source)<br>
<!-- END SCAT CODE -->
</body>
</html>
