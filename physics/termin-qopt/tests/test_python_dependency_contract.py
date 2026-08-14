import ast
from pathlib import Path


QOPT_ROOT = Path(__file__).resolve().parents[1]


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.partition(".")[0])
    return roots


def _install_requirements() -> set[str]:
    setup_path = QOPT_ROOT / "setup.py"
    tree = ast.parse(setup_path.read_text(encoding="utf-8"), filename=str(setup_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "install_requires":
                continue
            assert isinstance(keyword.value, (ast.List, ast.Tuple))
            return {
                element.value
                for element in keyword.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
    raise AssertionError("termin-qopt setup.py does not declare install_requires")


def test_python_qopt_does_not_require_scipy() -> None:
    imported_by = {
        path.relative_to(QOPT_ROOT).as_posix()
        for path in (QOPT_ROOT / "python").rglob("*.py")
        if "scipy" in _imported_roots(path)
    }

    assert imported_by == set()
    assert "scipy" not in _install_requirements()
