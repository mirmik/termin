"""Unit system for UI layout: pixels and NDC (normalized device coordinates)."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Unit(Enum):
    PX = "px"    # pixels
    NDC = "ndc"  # normalized 0..1


@dataclass
class Value:
    """A value with unit (pixels or NDC)."""
    amount: float
    unit: Unit = Unit.PX

    def to_pixels(self, reference: float) -> float:
        """Convert to pixels given reference size (viewport width or height)."""
        if self.unit == Unit.PX:
            return self.amount
        else:  # NDC
            return self.amount * reference

    def to_ndc(self, reference: float) -> float:
        """Convert to NDC given reference size."""
        if self.unit == Unit.NDC:
            return self.amount
        else:  # PX
            return self.amount / reference if reference > 0 else 0

    @staticmethod
    def parse(v) -> Value:
        """
        Parse value from various formats:
        - 100 or 100.0 -> 100px
        - "100" or "100px" -> 100px
        - "0.5ndc" or "50%" -> 0.5ndc
        """
        if isinstance(v, Value):
            return v

        if isinstance(v, (int, float)):
            return Value(float(v), Unit.PX)

        if isinstance(v, str):
            v = v.strip().lower()

            if v.endswith("px"):
                return Value(float(v[:-2]), Unit.PX)
            elif v.endswith("ndc"):
                return Value(float(v[:-3]), Unit.NDC)
            elif v.endswith("%"):
                return Value(float(v[:-1]) / 100.0, Unit.NDC)
            else:
                # bare number -> pixels
                return Value(float(v), Unit.PX)

        raise ValueError(f"Cannot parse value: {v}")


def px(amount: float) -> Value:
    """Shortcut for pixel value."""
    return Value(amount, Unit.PX)


def ndc(amount: float) -> Value:
    """Shortcut for NDC value."""
    return Value(amount, Unit.NDC)


def pct(amount: float) -> Value:
    """Shortcut for percentage (converted to NDC)."""
    return Value(amount / 100.0, Unit.NDC)
