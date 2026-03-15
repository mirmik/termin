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


def test_no_legacy_imports_in_examples():
    """Example files should not import from legacy facade paths."""
    import os
    import re

    legacy_pattern = re.compile(
        r"from\s+termin\.visualization\.(animation|render\.components)\s+import"
        r"|import\s+termin\.visualization\.(animation|render\.components)"
    )

    examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    examples_dir = os.path.normpath(examples_dir)
    violations = []

    for root, _dirs, files in os.walk(examples_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath) as f:
                for i, line in enumerate(f, 1):
                    if legacy_pattern.search(line):
                        rel = os.path.relpath(fpath, examples_dir)
                        violations.append(f"{rel}:{i}: {line.strip()}")

    assert not violations, "Legacy imports found in examples:\n" + "\n".join(violations)


def test_no_legacy_imports_in_canonical_modules():
    """Canonical modules should not import from termin.visualization.animation._*native."""
    import inspect
    from termin.animation import clip

    source = inspect.getsource(clip)
    assert "termin.visualization.animation._animation_native" not in source
    assert "termin.animation._animation_native" in source


def test_animation_facade_modules_removed():
    """Legacy facade modules under termin.visualization.animation should not exist."""
    facade_modules = [
        "termin.visualization.animation.channel",
        "termin.visualization.animation.clip",
        "termin.visualization.animation.clip_io",
        "termin.visualization.animation.player",
        "termin.visualization.animation.animation_clip_asset",
        "termin.visualization.animation.keyframe",
    ]
    for mod_name in facade_modules:
        with pytest.raises(ImportError):
            importlib.import_module(mod_name)


def test_builtins_no_legacy_animation_paths():
    """_builtins.py should not reference legacy animation paths."""
    from termin.assets.resources._builtins import BUILTIN_COMPONENTS

    for module_path, _cls in BUILTIN_COMPONENTS:
        assert not module_path.startswith("termin.visualization.animation"), (
            f"Legacy path found in BUILTIN_COMPONENTS: {module_path}"
        )
