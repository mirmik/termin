"""Загрузка параметров источников света в GLSL-шейдер."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from termin.lighting import Light, LightType
from tgfx import TcShader

# Максимальное число источников, поддерживаемых дефолтным forward-проходом.
MAX_LIGHTS = 8


def _light_type_to_int(light_type: LightType) -> int:
    if light_type == LightType.DIRECTIONAL:
        return 0
    if light_type == LightType.POINT:
        return 1
    if light_type == LightType.SPOT:
        return 2
    raise ValueError(f"Unknown LightType: {light_type}")


def _attenuation_vector(light: Light) -> np.ndarray:
    """
    Собираем коэффициенты затухания ``w(d) = 1 / (k_c + k_l d + k_q d^2)``.
    Они напрямую падают в шейдер.
    """
    coeffs = light.attenuation
    return np.array(
        [coeffs.constant, coeffs.linear, coeffs.quadratic],
        dtype=np.float32,
    )


def upload_lights_to_shader(shader: TcShader, lights: Sequence[Light]) -> None:
    """
    Передать массив источников в uniform-пакет.

    Геометрия источников задаётся явными векторами ``position`` и ``direction`` —
    никаких getattr и магии, только строгие поля.
    """
    count = min(len(lights), MAX_LIGHTS)
    shader.set_uniform_int("u_light_count", count)

    prefix = "u_light_"

    for index in range(count):
        light = lights[index]

        light_type_int = _light_type_to_int(light.type)
        shader.set_uniform_int(f"{prefix}type[{index}]", light_type_int)
        color = light.color
        shader.set_uniform_vec3(f"{prefix}color[{index}]", float(color[0]), float(color[1]), float(color[2]))
        shader.set_uniform_float(f"{prefix}intensity[{index}]", float(light.intensity))
        direction = light.direction
        shader.set_uniform_vec3(f"{prefix}direction[{index}]", float(direction[0]), float(direction[1]), float(direction[2]))
        position = light.position
        shader.set_uniform_vec3(f"{prefix}position[{index}]", float(position[0]), float(position[1]), float(position[2]))

        light_range = 1e9 if light.range is None else float(light.range)
        shader.set_uniform_float(f"{prefix}range[{index}]", light_range)

        attn = _attenuation_vector(light)
        shader.set_uniform_vec3(f"{prefix}attenuation[{index}]", float(attn[0]), float(attn[1]), float(attn[2]))
        shader.set_uniform_float(f"{prefix}inner_angle[{index}]", float(light.inner_angle))
        shader.set_uniform_float(f"{prefix}outer_angle[{index}]", float(light.outer_angle))


def upload_ambient_to_shader(
    shader: TcShader,
    ambient_color: np.ndarray,
    ambient_intensity: float,
) -> None:
    """Upload scene-level ambient lighting uniforms."""
    ac = ambient_color
    shader.set_uniform_vec3("u_ambient_color", float(ac[0]), float(ac[1]), float(ac[2]))
    shader.set_uniform_float("u_ambient_intensity", float(ambient_intensity))
