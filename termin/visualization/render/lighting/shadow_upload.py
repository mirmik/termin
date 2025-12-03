"""Загрузка shadow map данных в GLSL-шейдер."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.render.shader import ShaderProgram
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource


# Максимальное число shadow maps, поддерживаемых шейдером
MAX_SHADOW_MAPS = 4

# Начальный texture unit для shadow maps
SHADOW_MAP_TEXTURE_UNIT_START = 8


def upload_shadow_maps_to_shader(
    shader: "ShaderProgram",
    shadow_array: "ShadowMapArrayResource",
) -> None:
    """
    Загружает данные shadow maps в uniform'ы шейдера.
    
    Uniform'ы, ожидаемые шейдером:
        u_shadow_map_count — int, количество активных shadow maps
        u_shadow_map[i] — sampler2D, текстура i-го shadow map
        u_light_space_matrix[i] — mat4, матрица преобразования в light-space
        u_shadow_light_index[i] — int, индекс источника света в массиве lights
    
    Shadow maps биндятся на texture units начиная с SHADOW_MAP_TEXTURE_UNIT_START.
    ColorPass биндит текстуры, этот метод только устанавливает uniform'ы.
    
    Параметры:
        shader: Активный шейдер (после use())
        shadow_array: Массив shadow maps из ShadowPass
    """
    if shadow_array is None:
        shader.set_uniform_int("u_shadow_map_count", 0)
        return
    
    count = min(len(shadow_array), MAX_SHADOW_MAPS)
    shader.set_uniform_int("u_shadow_map_count", count)
    
    for i in range(count):
        entry = shadow_array[i]
        unit = SHADOW_MAP_TEXTURE_UNIT_START + i
        
        # Texture unit для sampler2D
        shader.set_uniform_int(f"u_shadow_map[{i}]", unit)
        
        # Матрица light-space: P_light * V_light
        # Преобразует мировые координаты в clip-пространство источника
        shader.set_uniform_matrix4(f"u_light_space_matrix[{i}]", entry.light_space_matrix)
        
        # Индекс источника света (для соответствия с u_light_* массивами)
        shader.set_uniform_int(f"u_shadow_light_index[{i}]", entry.light_index)
