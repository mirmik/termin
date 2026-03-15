"""Test that animation native modules are accessible via canonical paths."""

import importlib
import pytest


def test_animation_native_via_canonical_path():
    """_animation_native should be importable via termin.animation."""
    mod = importlib.import_module("termin.animation._animation_native")
    assert hasattr(mod, "TcAnimationClip")


def test_components_animation_native_via_canonical_path():
    """_components_animation_native should be findable via termin.animation_components."""
    try:
        mod = importlib.import_module("termin.animation_components._components_animation_native")
        assert hasattr(mod, "AnimationPlayer")
    except ImportError as e:
        if "libtermin_skeleton" in str(e) or "initializing the extension" in str(e):
            pytest.skip("native skeleton libs not available in test environment")
        raise


def test_canonical_clip_import():
    """termin.animation.clip should import TcAnimationClip from canonical path."""
    from termin.animation.clip import TcAnimationClip
    assert TcAnimationClip is not None


def test_canonical_clip_io_import():
    """termin.animation.clip_io should work with canonical native imports."""
    from termin.animation.clip_io import load_animation_clip, save_animation_clip
    assert load_animation_clip is not None
    assert save_animation_clip is not None


def test_canonical_animation_components_import():
    """termin.animation_components should import AnimationPlayer from canonical path."""
    try:
        from termin.animation_components import AnimationPlayer
        assert AnimationPlayer is not None
    except ImportError as e:
        if "libtermin_skeleton" in str(e) or "initializing the extension" in str(e):
            pytest.skip("native skeleton libs not available in test environment")
        raise


def test_canonical_animation_clip_handle_import():
    """termin.assets.animation_clip_handle should use canonical path."""
    from termin.assets.animation_clip_handle import TcAnimationClip
    assert TcAnimationClip is not None


def test_no_legacy_imports_in_canonical_modules():
    """Canonical modules should not import from termin.visualization.animation._*native."""
    import inspect
    from termin.animation import clip

    source = inspect.getsource(clip)
    assert "termin.visualization.animation._animation_native" not in source
    assert "termin.animation._animation_native" in source
