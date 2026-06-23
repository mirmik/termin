import ast
from pathlib import Path


def test_termin_physics_does_not_depend_on_fem_stack() -> None:
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

    assert "termin-qopt" not in requirements
    assert "scipy" not in requirements
    assert "termin-voxels" not in requirements
