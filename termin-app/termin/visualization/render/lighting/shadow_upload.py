"""Загрузка shadow map данных в GLSL-шейдер."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tgfx import TcShader
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
    from termin.visualization.core.scene.lighting import ShadowSettings


# Максимальное число shadow maps, поддерживаемых шейдером
MAX_SHADOW_MAPS = 4

# Начальный texture unit для shadow maps
SHADOW_MAP_TEXTURE_UNIT_START = 8


def upload_shadow_settings_to_shader(
    shader: "TcShader",
    shadow_settings: "ShadowSettings",
) -> None:
    """
    Загружает настройки теней в uniform'ы шейдера.

    Uniform'ы:
        u_shadow_method — int, метод (0=hard, 1=pcf, 2=poisson)
        u_shadow_softness — float, множитель радиуса сэмплирования
        u_shadow_bias — float, смещение глубины

    Параметры:
        shader: Активный шейдер (после use())
        shadow_settings: Настройки теней из Scene
    """
    shader.set_uniform_int("u_shadow_method", shadow_settings.method)
    shader.set_uniform_float("u_shadow_softness", shadow_settings.softness)
    shader.set_uniform_float("u_shadow_bias", shadow_settings.bias)


def upload_shadow_maps_to_shader(
    shader: "TcShader",
    shadow_array: "ShadowMapArrayResource",
) -> None:
    """
    Загружает данные shadow maps в uniform'ы шейдера.

    Uniform'ы, ожидаемые шейдером:
        u_shadow_map_count — int, количество активных shadow maps
        u_shadow_map[i] — sampler2DShadow, depth texture с hardware PCF
        u_light_space_matrix[i] — mat4, матрица преобразования в light-space
        u_shadow_light_index[i] — int, индекс источника света в массиве lights

    Shadow maps — depth текстуры с GL_TEXTURE_COMPARE_MODE для hardware PCF.
    texture() возвращает 0.0 (в тени) или 1.0 (освещено).

    Shadow maps биндятся на texture units начиная с SHADOW_MAP_TEXTURE_UNIT_START.
    ColorPass биндит текстуры, этот метод только устанавливает uniform'ы.

    Параметры:
        shader: Активный шейдер (после use())
        shadow_array: Массив shadow maps из ShadowPass
    """
    if shadow_array is None or len(shadow_array) == 0:
        shader.set_uniform_int("u_shadow_map_count", 0)
        # ВАЖНО: Всё равно установить uniform'ы для sampler'ов чтобы они
        # указывали на units 8+ (не 0, где u_albedo_texture).
        # AMD драйверы не позволяют sampler2D и sampler2DShadow на одном unit.
        for i in range(MAX_SHADOW_MAPS):
            shader.set_uniform_int(f"u_shadow_map[{i}]", SHADOW_MAP_TEXTURE_UNIT_START + i)
        return

    count = min(len(shadow_array), MAX_SHADOW_MAPS)
    shader.set_uniform_int("u_shadow_map_count", count)

    for i in range(count):
        entry = shadow_array[i]
        unit = SHADOW_MAP_TEXTURE_UNIT_START + i

        # Texture unit для sampler2DShadow
        shader.set_uniform_int(f"u_shadow_map[{i}]", unit)

        # Матрица light-space: P_light * V_light
        # Преобразует мировые координаты в clip-пространство источника
        shader.set_uniform_mat4(f"u_light_space_matrix[{i}]", entry.light_space_matrix.data, False)

        # Индекс источника света (для соответствия с u_light_* массивами)
        shader.set_uniform_int(f"u_shadow_light_index[{i}]", entry.light_index)

    # Установить оставшиеся sampler'ы на их unit'ы (для AMD)
    for i in range(count, MAX_SHADOW_MAPS):
        shader.set_uniform_int(f"u_shadow_map[{i}]", SHADOW_MAP_TEXTURE_UNIT_START + i)
