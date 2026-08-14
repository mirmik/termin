import ast
import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "python" / "termin" / "kinematic"
FORBIDDEN_IMPORTS = ("scipy", "termin.linalg", "termin_qopt")


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            result.append(node.module)
    return tuple(result)


def _install_requires() -> tuple[str, ...]:
    setup_path = PACKAGE_ROOT / "setup.py"
    tree = ast.parse(setup_path.read_text(encoding="utf-8"), filename=str(setup_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "install_requires":
                continue
            assert isinstance(keyword.value, (ast.List, ast.Tuple))
            return tuple(
                element.value
                for element in keyword.value.elts
                if isinstance(element, ast.Constant)
                and isinstance(element.value, str)
            )
    raise AssertionError("setup.py has no literal install_requires")


def test_base_kinematic_has_no_qopt_or_scipy_dependency() -> None:
    assert not (SOURCE_ROOT / "conditions.py").exists()

    violations = []
    for source in sorted(SOURCE_ROOT.rglob("*.py")):
        for imported in _imports(source):
            if any(
                imported == forbidden or imported.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_IMPORTS
            ):
                violations.append(f"{source.relative_to(PACKAGE_ROOT)}: {imported}")

    assert violations == []
    requirements = {
        re.split(r"[<>=!~\s]", requirement.partition(";")[0], maxsplit=1)[0]
        .partition("[")[0]
        .lower()
        for requirement in _install_requires()
    }
    assert requirements.isdisjoint({"scipy", "termin-qopt"})
