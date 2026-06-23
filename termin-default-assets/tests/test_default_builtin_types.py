import ast
from pathlib import Path

from termin.default_assets.builtin_types import get_default_builtin_component_specs


def test_default_builtin_components_exclude_experimental_physics_fem() -> None:
    component_specs = get_default_builtin_component_specs()

    assert not any(
        module_name == "termin.physics_fem"
        or module_name.startswith("termin.physics_fem.")
        for module_name, _class_name in component_specs
    )


def test_default_assets_package_does_not_require_physics_fem() -> None:
    setup_path = Path(__file__).resolve().parents[1] / "setup.py"
    tree = ast.parse(setup_path.read_text(encoding="utf-8"), filename=str(setup_path))
    setup_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "setup"
    )
    install_requires = next(
        keyword.value
        for keyword in setup_call.keywords
        if keyword.arg == "install_requires"
    )
    requirements = {
        item.value
        for item in install_requires.elts
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    }

    assert "termin-physics-fem" not in requirements
