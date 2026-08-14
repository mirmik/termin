"""Lightweight builtin component specs owned by termin-components-physics."""

from __future__ import annotations

# The canonical component types are registered by the C++ bootstrap. Keeping
# this package allows old entry-point discovery metadata to remain importable
# without publishing a second Python-owned runtime type.
COMPONENT_SPECS: tuple[tuple[str, str], ...] = ()

__all__ = ["COMPONENT_SPECS"]
