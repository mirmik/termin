"""Test that animation native modules are accessible via canonical paths."""

import ast
import importlib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _literal_specs_from_file(path: Path, variable_name: str) -> list[tuple[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.target.id == variable_name:
                return ast.literal_eval(statement.value)
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id == variable_name:
                    return ast.literal_eval(statement.value)
    raise AssertionError(f"{variable_name} not found in {path}")


def _builtin_component_specs_for_static_checks() -> list[tuple[str, str]]:
    from termin.assets.resources._builtins import APP_BUILTIN_COMPONENTS
    from termin.default_assets.builtin_types import DEFAULT_DOMAIN_COMPONENT_SPECS

    return [
        *_literal_specs_from_file(
            REPO_ROOT
            / "termin-components"
            / "termin-components-render"
            / "python"
            / "termin"
            / "render_components"
            / "builtins.py",
            "COMPONENT_SPECS",
        ),
        *_literal_specs_from_file(
            REPO_ROOT
            / "termin-components"
            / "termin-components-ui"
            / "python"
            / "termin"
            / "ui_components"
            / "builtins.py",
            "COMPONENT_SPECS",
        ),
        *DEFAULT_DOMAIN_COMPONENT_SPECS,
        *APP_BUILTIN_COMPONENTS,
    ]


def test_animation_native_via_canonical_path():
    """_animation_native should be importable via termin.animation."""
    mod = importlib.import_module("termin.animation._animation_native")
    assert hasattr(mod, "TcAnimationClip")


def test_components_animation_native_via_canonical_path():
    """_components_animation_native is shipped in the termin.animation namespace."""
    try:
        mod = importlib.import_module("termin.animation._components_animation_native")
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
    """TcAnimationClip should be available through the canonical native module."""
    from termin.animation._animation_native import TcAnimationClip

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
        if os.path.basename(root) == "broken":
            continue
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
    assert "._animation_native" in source


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
    for module_path, _cls in _builtin_component_specs_for_static_checks():
        assert not module_path.startswith("termin.visualization.animation"), (
            f"Legacy path found in builtin component specs: {module_path}"
        )


def test_render_components_facade_modules_removed():
    """Legacy facade modules under termin.visualization.render.components should not exist."""
    facade_modules = [
        "termin.visualization.render.components.mesh_renderer",
        "termin.visualization.render.components.light_component",
        "termin.visualization.render.components.line_renderer",
        "termin.visualization.render.components.skinned_mesh_renderer",
        "termin.visualization.render.components.skybox_renderer",
        "termin.visualization.render.components.skeleton_controller",
    ]
    for mod_name in facade_modules:
        with pytest.raises(ImportError):
            importlib.import_module(mod_name)


def test_builtins_no_legacy_render_components_paths():
    """_builtins.py should not reference legacy render components paths."""
    for module_path, _cls in _builtin_component_specs_for_static_checks():
        assert not module_path.startswith("termin.visualization.render.components"), (
            f"Legacy path found in builtin component specs: {module_path}"
        )


def test_physics_facade_modules_removed():
    """Legacy facade/component modules under termin.physics should not exist in repo tree."""
    import os
    repo_physics = os.path.join(os.path.dirname(__file__), "..", "termin", "physics")
    repo_physics = os.path.normpath(repo_physics)
    facade_files = [
        "physics_world_component.py",
        "rigid_body_component.py",
        "fem_physics_world_component.py",
        "fem_rigid_body_component.py",
        "fem_fixed_joint_component.py",
        "fem_revolute_joint_component.py",
    ]
    for fname in facade_files:
        fpath = os.path.join(repo_physics, fname)
        assert not os.path.exists(fpath), f"Legacy facade still exists: {fpath}"


def test_builtins_no_legacy_physics_paths():
    """_builtins.py should not reference legacy physics facade paths."""
    for module_path, _cls in _builtin_component_specs_for_static_checks():
        assert not module_path.startswith("termin.physics.physics_world_component"), (
            f"Legacy path found in builtin component specs: {module_path}"
        )
        assert not module_path.startswith("termin.physics.rigid_body_component"), (
            f"Legacy path found in builtin component specs: {module_path}"
        )
        assert not module_path.startswith("termin.physics.fem_"), (
            f"Legacy FEM path found in builtin component specs: {module_path}"
        )
