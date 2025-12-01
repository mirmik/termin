"""Shader wrapper delegating compilation and uniform uploads to a graphics backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from termin.visualization.platform.backends import get_default_graphics_backend
from termin.visualization.platform.backends.base import GraphicsBackend, ShaderHandle


class ShaderCompilationError(RuntimeError):
    """Raised when GLSL compilation or program linking fails."""


class ShaderProgram:
    """A GLSL shader program (vertex + fragment).

    Uniform setters inside the class assume column-major matrices and they set the
    combined MVP transform ``P * V * M`` in homogeneous coordinates.
    """

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
    def default_shader() -> "ShaderProgram":
        vert = """#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_pos;
out vec3 v_normal;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_world_pos = world.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * world;
}
"""

        frag = """#version 330 core

in vec3 v_world_pos;
in vec3 v_normal;

uniform vec4 u_color; // RGBA базового материала

const int LIGHT_TYPE_DIRECTIONAL = 0;
const int LIGHT_TYPE_POINT       = 1;
const int LIGHT_TYPE_SPOT        = 2;
const int LIGHT_TYPE_AMBIENT     = 3;

const int MAX_LIGHTS = 8;

uniform int   u_light_count;
uniform int   u_light_type[MAX_LIGHTS];
uniform vec3  u_light_color[MAX_LIGHTS];
uniform float u_light_intensity[MAX_LIGHTS];
uniform vec3  u_light_direction[MAX_LIGHTS];
uniform vec3  u_light_position[MAX_LIGHTS];
uniform float u_light_range[MAX_LIGHTS];
uniform vec3  u_light_attenuation[MAX_LIGHTS]; // (constant, linear, quadratic)
uniform float u_light_inner_angle[MAX_LIGHTS];
uniform float u_light_outer_angle[MAX_LIGHTS];

out vec4 FragColor;

float compute_distance_attenuation(int idx, float dist) {
    vec3 att = u_light_attenuation[idx];
    float denom = att.x + att.y * dist + att.z * dist * dist;
    if (denom <= 0.0) {
        return 1.0;
    }
    float w = 1.0 / denom;
    float range = u_light_range[idx];
    if (range > 0.0 && dist > range) {
        w = 0.0;
    }
    return w;
}

float compute_spot_weight(int idx, vec3 L) {
    float cos_theta = dot(u_light_direction[idx], -L);
    float cos_outer = cos(u_light_outer_angle[idx]);
    float cos_inner = cos(u_light_inner_angle[idx]);

    if (cos_theta <= cos_outer) return 0.0;
    if (cos_theta >= cos_inner) return 1.0;

    float t = (cos_theta - cos_outer) / (cos_inner - cos_outer);
    return t * t * (3.0 - 2.0 * t); // smoothstep
}

void main() {
    vec3 N = normalize(v_normal);
    vec3 base_color = u_color.rgb;
    vec3 result = vec3(0.0);

    for (int i = 0; i < u_light_count; ++i) {
        int type = u_light_type[i];
        vec3 radiance = u_light_color[i] * u_light_intensity[i];

        if (type == LIGHT_TYPE_AMBIENT) {
            result += base_color * radiance;
            continue;
        }

        vec3 L;
        float dist;
        float weight = 1.0;

        if (type == LIGHT_TYPE_DIRECTIONAL) {
            L = normalize(-u_light_direction[i]); // направление на свет
            dist = 1e9;
        } else {
            vec3 to_light = u_light_position[i] - v_world_pos;
            dist = length(to_light);
            if (dist > 0.0001)
                L = to_light / dist;
            else
                L = vec3(0.0, 1.0, 0.0);

            weight *= compute_distance_attenuation(i, dist);

            if (type == LIGHT_TYPE_SPOT) {
                weight *= compute_spot_weight(i, L);
            }
        }

        float ndotl = max(dot(N, L), 0.0);
        vec3 diffuse = base_color * ndotl;

        vec3 V = normalize(-v_world_pos); // камера в (0,0,0) для простоты
        vec3 H = normalize(L + V);
        float ndoth = max(dot(N, H), 0.0);
        float shininess = 16.0;
        float spec = pow(ndoth, shininess);

        vec3 specular_color = vec3(1.0);
        vec3 specular = spec * specular_color;

        result += (diffuse + specular) * radiance * weight;
    }

    FragColor = vec4(result, u_color.a);
}
"""

        return ShaderProgram(vertex_source=vert, fragment_source=frag)

    def ensure_ready(self, graphics: GraphicsBackend | None = None):
        if self._compiled:
            return
        backend = graphics or self._backend or get_default_graphics_backend()
        if backend is None:
            raise RuntimeError("Graphics backend is not available for shader compilation.")
        self._backend = backend
        self._handle = backend.create_shader(self.vertex_source, self.fragment_source, self.geometry_source)
        self._compiled = True

    def _require_handle(self) -> ShaderHandle:
        if self._handle is None:
            raise RuntimeError("ShaderProgram is not compiled. Call ensure_ready() first.")
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
        """Upload a 4x4 matrix (float32) to uniform ``name``."""
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
        """Best-effort setter that infers uniform type based on ``value``."""
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
                raise ValueError(f"Unsupported uniform array shape for {name}: {arr.shape}")
        elif isinstance(value, bool):
            self.set_uniform_int(name, int(value))
        elif isinstance(value, int):
            self.set_uniform_int(name, value)
        else:
            self.set_uniform_float(name, float(value))

    @classmethod
    def from_files(cls, vertex_path: str | Path, fragment_path: str | Path) -> "ShaderProgram":
        vertex_source = Path(vertex_path).read_text(encoding="utf-8")
        fragment_source = Path(fragment_path).read_text(encoding="utf-8")
        return cls(vertex_source=vertex_source, fragment_source=fragment_source)
