"""Аналитические помощники шейдинга (Ламберт + Блинн–Фонг)."""

from __future__ import annotations

import numpy as np

from .light import LightSample


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def lambert_diffuse(normal: np.ndarray, sample: LightSample, albedo: np.ndarray) -> np.ndarray:
    """Диффузная составляющая по закону Ламберта.

    Косинус ``max(dot(N, L), 0)`` появляется из проекции падающего облучения
    на поверхность. Физически нормированный Ламберт-коэффициент — это
    ``albedo / pi``; здесь ``pi`` оставляем вне формулы для удобства настройки.
    """
    N = _normalize(normal)
    L = _normalize(sample.L)
    ndotl = max(float(np.dot(N, L)), 0.0)
    return albedo * ndotl * sample.radiance


def fresnel_schlick(cos_theta: float, f0: np.ndarray) -> np.ndarray:
    """Аппроксимация Френеля по Шлику:
    ``F = F0 + (1 - F0) (1 - cos(theta))^5``."""
    return f0 + (1.0 - f0) * ((1.0 - cos_theta) ** 5)


def blinn_phong_specular(
    normal: np.ndarray,
    view_dir: np.ndarray,
    sample: LightSample,
    shininess: float,
    f0: np.ndarray | None = None,
) -> np.ndarray:
    """Блик Блинна–Фонга с опциональным весом Френеля.

    Подсветка использует ``H = normalize(L + V)`` и ``spec = max(dot(N, H), 0)^s``.
    Если задан ``f0``, аппроксимация Шлика модифицирует лобу, имитируя
    перераспределение энергии между диффузной и зеркальной составляющими.
    """
    N = _normalize(normal)
    L = _normalize(sample.L)
    V = _normalize(view_dir)
    H = _normalize(L + V)

    ndoth = max(float(np.dot(N, H)), 0.0)
    spec = (ndoth ** shininess) if shininess > 0.0 else 0.0

    if f0 is not None:
        cos_theta = max(float(np.dot(H, V)), 0.0)
        specular_color = fresnel_schlick(cos_theta, np.asarray(f0, dtype=np.float32))
    else:
        specular_color = 1.0

    return specular_color * spec * sample.radiance
