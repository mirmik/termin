"""Классические кривые затухания для точечных и прожекторных источников."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AttenuationCoefficients:
    """Параметры полиномиального затухания ``w(d) = 1 / (k_c + k_l d + k_q d^2)``.

    Формула — классическая модель в стиле OpenGL. Для физически корректного
    обратного квадрата задаём ``k_c = k_l = 0`` и ``k_q = 1``, тогда
    ``w(d) = 1 / d^2``.
    """

    constant: float = 1.0
    linear: float = 0.0
    quadratic: float = 0.0

    def evaluate(self, distance: float) -> float:
        """Вычислить вес затухания для заданной дистанции."""
        d = max(distance, 0.0)
        denom = self.constant + self.linear * d + self.quadratic * d * d
        if denom <= 0.0:
            return 0.0
        return 1.0 / denom

    @classmethod
    def match_range(cls, falloff_range: float, cutoff: float = 0.01) -> "AttenuationCoefficients":
        """Подобрать квадратичный коэффициент, чтобы ``w(r) = cutoff`` на дистанции ``r``.

        При ``k_c = 1`` и ``k_l = 0`` уравнение
        ``cutoff = 1 / (1 + k_q r^2)`` даёт
        ``k_q = (1 / cutoff - 1) / r^2``. Удобно для «range» слайдеров.
        """
        r = max(falloff_range, 1e-6)
        k_q = (1.0 / cutoff - 1.0) / (r * r)
        return cls(constant=1.0, linear=0.0, quadratic=k_q)

    @classmethod
    def inverse_square(cls) -> "AttenuationCoefficients":
        """Физическое затухание ``w(d) = 1 / d^2``."""
        return cls(constant=0.0, linear=0.0, quadratic=1.0)

    def clamp_range(self, max_range: float, cutoff: float = 0.01) -> "AttenuationCoefficients":
        """Вернуть коэффициенты, затухающие до ``cutoff`` на дистанции ``max_range``."""
        return self.match_range(max_range, cutoff=cutoff)
