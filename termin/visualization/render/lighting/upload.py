"""Загрузка параметров источников света в GLSL-шейдер."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from termin.visualization.core.lighting.light import Light, LightType
from termin.visualization.render.shader import ShaderProgram

# Максимальное число источников, поддерживаемых дефолтным forward-проходом.
MAX_LIGHTS = 8


def _light_type_to_int(light_type: LightType) -> int:
    if light_type == LightType.DIRECTIONAL:
        return 0
    if light_type == LightType.POINT:
        return 1
    if light_type == LightType.SPOT:
        return 2
    if light_type == LightType.AMBIENT:
        return 3
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


def upload_lights_to_shader(shader: ShaderProgram, lights: Sequence[Light]) -> None:
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

        shader.set_uniform_int(f"{prefix}type[{index}]", _light_type_to_int(light.type))
        shader.set_uniform_vec3(f"{prefix}color[{index}]", np.asarray(light.color, dtype=np.float32))
        shader.set_uniform_float(f"{prefix}intensity[{index}]", float(light.intensity))
        shader.set_uniform_vec3(f"{prefix}direction[{index}]", np.asarray(light.direction, dtype=np.float32))
        shader.set_uniform_vec3(f"{prefix}position[{index}]", np.asarray(light.position, dtype=np.float32))

        light_range = 1e9 if light.range is None else float(light.range)
        shader.set_uniform_float(f"{prefix}range[{index}]", light_range)

        shader.set_uniform_vec3(f"{prefix}attenuation[{index}]", _attenuation_vector(light))
        shader.set_uniform_float(f"{prefix}inner_angle[{index}]", float(light.inner_angle))
        shader.set_uniform_float(f"{prefix}outer_angle[{index}]", float(light.outer_angle))
