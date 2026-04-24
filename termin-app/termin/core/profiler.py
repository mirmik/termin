"""Profiler re-export.

The actual implementation moved to ``tcbase.profiler`` so hosts that
don't pull termin-app (standalone tcgui demos etc.) can still push
sections. Existing ``from termin.core.profiler import ...`` call sites
keep working via these re-exports.
"""

from tcbase.profiler import (
    FrameProfile,
    Profiler,
    SectionStats,
    SectionTiming,
)

__all__ = ["FrameProfile", "Profiler", "SectionStats", "SectionTiming"]
