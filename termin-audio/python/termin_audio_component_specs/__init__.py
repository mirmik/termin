"""Lightweight builtin component specs owned by termin-audio."""

from __future__ import annotations

COMPONENT_SPECS: tuple[tuple[str, str], ...] = (
    ("termin.audio.components.audio_source", "AudioSource"),
    ("termin.audio.components.audio_listener", "AudioListener"),
)

__all__ = ["COMPONENT_SPECS"]
