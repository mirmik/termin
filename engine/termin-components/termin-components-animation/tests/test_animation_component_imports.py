"""Canonical imports owned by the animation component adapter package."""

import importlib


def test_components_animation_native_via_canonical_path():
    module = importlib.import_module("termin.animation._components_animation_native")
    assert module.AnimationPlayer is not None


def test_canonical_animation_components_import():
    from termin.animation_components import AnimationPlayer

    assert AnimationPlayer is not None
