#!/usr/bin/env python3
"""Report suspicious import-time resource creation in Python modules."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ALLOW_MARKER = "termin-import-ok"
DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "install",
    "sdk",
    "termin-thirdparty",
}
DEFAULT_ROOT_PREFIXES = ("termin-", "tcplot")

RISKY_CALL_NAMES = {
    "AudioEngine",
    "Canvas2DRenderer",
    "CanvasColor",
    "Color4",
    "DefaultResourceManager",
    "FontTextureAtlas",
    "Profiler",
    "RenderPipeline",
    "TcAnimationClip",
    "TcMaterial",
    "TcMesh",
    "TcShader",
    "TcTexture",
    "Tgfx2Context",
}
RISKY_CALL_PREFIXES = ("Tc", "Tgfx")
RISKY_FUNCTION_NAMES = {
    "get_default_font",
    "get_resource_manager",
    "open",
}
RISKY_METHOD_NAMES = {
    "instance",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
}
REGISTRATION_PREFIXES = ("init_", "load_", "register_", "set_")
SAFE_CALLS = {
    "dataclass",
    "field",
    "logging.getLogger",
    "re.compile",
    "TypeVar",
}
MUTABLE_CALL_NAMES = {
    "defaultdict",
    "deque",
    "dict",
    "list",
    "OrderedDict",
    "set",
    "WeakKeyDictionary",
    "WeakValueDictionary",
}
MUTABLE_STATE_NAME_HINTS = {
    "builtin",
    "cache",
    "catalog",
    "component",
    "extension",
    "factory",
    "handler",
    "instance",
    "kind",
    "loader",
    "manager",
    "pending",
    "plugin",
    "processor",
    "provider",
    "registry",
    "resource",
    "runtime",
    "singleton",
    "state",
    "store",
    "type",
}
IMPORTANT_UPPERCASE_STATE_NAMES = {
    "DEFAULT_DOMAIN_COMPONENT_SPECS",
}
IMMUTABLE_INITIALIZER_CALLS = {
    "frozenset",
    "tuple",
}
CONFIDENCE_RANKS = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    column: int
    category: str
    confidence: str
    target: str
    code: str


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _assignment_target_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Tuple):
        return ",".join(_assignment_target_name(item) for item in node.elts)
    return type(node).__name__


def _assignment_target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, ast.Tuple):
        names: list[str] = []
        for item in node.elts:
            names.extend(_assignment_target_names(item))
        return names
    return []


def _looks_like_mutable_state_name(name: str) -> bool:
    if name == "__all__" or (name.startswith("__") and name.endswith("__")):
        return False
    if name in IMPORTANT_UPPERCASE_STATE_NAMES:
        return True
    if name.isupper() and "BUILTIN" in name:
        return True
    if name.isupper() and (
        name.endswith("_FACTORIES")
        or name.endswith("_REGISTRIES")
        or name.endswith("_REGISTRY")
    ):
        return True
    if name.isupper():
        return False
    lowered = name.lower()
    if any(hint in lowered for hint in MUTABLE_STATE_NAME_HINTS):
        return True
    return name.startswith("_") and not name.startswith("__") and not name.isupper()


def _statement_target_names(statement: ast.Assign | ast.AnnAssign) -> list[str]:
    if isinstance(statement, ast.Assign):
        names: list[str] = []
        for target in statement.targets:
            names.extend(_assignment_target_names(target))
        return names
    return _assignment_target_names(statement.target)


def _statement_looks_like_mutable_state(statement: ast.Assign | ast.AnnAssign) -> bool:
    return any(
        _looks_like_mutable_state_name(name) for name in _statement_target_names(statement)
    )


def _top_level_call_from_statement(statement: ast.stmt) -> tuple[ast.Call, str] | None:
    if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
        targets = ", ".join(_assignment_target_name(target) for target in statement.targets)
        return statement.value, targets
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.value, ast.Call):
        return statement.value, _assignment_target_name(statement.target)
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        return statement.value, "<expr>"
    return None


def _top_level_mutable_state_from_statement(
    statement: ast.stmt,
) -> tuple[ast.AST, str, str] | None:
    if isinstance(statement, ast.Assign):
        targets = ", ".join(_assignment_target_name(target) for target in statement.targets)
        value = statement.value
    elif isinstance(statement, ast.AnnAssign):
        targets = _assignment_target_name(statement.target)
        value = statement.value
    else:
        return None

    if value is None:
        return None
    if not _statement_looks_like_mutable_state(statement):
        return None
    if isinstance(value, (ast.Dict, ast.List, ast.Set)):
        return value, targets, type(value).__name__.lower()
    if isinstance(value, ast.Call):
        call_name = _call_name(value.func)
        if call_name is None:
            return None
        leaf = call_name.rsplit(".", 1)[-1]
        if leaf in MUTABLE_CALL_NAMES:
            return value, targets, call_name
    return None


def _is_allowed(lines: list[str], line_number: int) -> bool:
    if line_number <= 0:
        return False
    current = lines[line_number - 1]
    previous = lines[line_number - 2] if line_number >= 2 else ""
    return ALLOW_MARKER in current or ALLOW_MARKER in previous


def _classify_call(call: ast.Call) -> tuple[str, str] | None:
    call_name = _call_name(call.func)
    if call_name is None or call_name in SAFE_CALLS:
        return None

    leaf = call_name.rsplit(".", 1)[-1]
    if leaf in RISKY_CALL_NAMES or leaf.startswith(RISKY_CALL_PREFIXES):
        return "native-resource-constructor", "high"
    if leaf in RISKY_FUNCTION_NAMES:
        return "runtime-resource-factory", "high"
    if leaf in RISKY_METHOD_NAMES:
        return "runtime-singleton-or-io", "high"
    if leaf.startswith(REGISTRATION_PREFIXES):
        return "module-registration-call", "medium"
    return None


def audit_file(
    path: Path,
    *,
    root: Path | None = None,
    include_mutable_state: bool = False,
) -> list[Finding]:
    root = root or Path.cwd()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))

    findings: list[Finding] = []
    for statement in tree.body:
        call_info = _top_level_call_from_statement(statement)
        rel_path = path.relative_to(root) if path.is_relative_to(root) else path

        if call_info is not None:
            call, target = call_info
            if not _is_allowed(lines, call.lineno):
                classification = _classify_call(call)
                if classification is not None:
                    category, confidence = classification
                    call_name = _call_name(call.func) or "<call>"
                    findings.append(
                        Finding(
                            path=str(rel_path),
                            line=call.lineno,
                            column=call.col_offset + 1,
                            category=category,
                            confidence=confidence,
                            target=f"{target} = {call_name}",
                            code=lines[call.lineno - 1].strip(),
                        )
                    )
                elif include_mutable_state and isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    if (
                        _statement_looks_like_mutable_state(statement)
                        and _call_name(call.func) not in SAFE_CALLS
                        and _call_name(call.func) not in IMMUTABLE_INITIALIZER_CALLS
                        and _top_level_mutable_state_from_statement(statement) is None
                    ):
                        call_name = _call_name(call.func) or "<call>"
                        findings.append(
                            Finding(
                                path=str(rel_path),
                                line=call.lineno,
                                column=call.col_offset + 1,
                                category="module-state-initializer-call",
                                confidence="low",
                                target=f"{target} = {call_name}",
                                code=lines[call.lineno - 1].strip(),
                            )
                        )

        if not include_mutable_state:
            continue
        mutable_info = _top_level_mutable_state_from_statement(statement)
        if mutable_info is None:
            continue
        value, target, value_name = mutable_info
        if _is_allowed(lines, value.lineno):
            continue
        findings.append(
            Finding(
                path=str(rel_path),
                line=value.lineno,
                column=value.col_offset + 1,
                category="module-mutable-state",
                confidence="low",
                target=f"{target} = {value_name}",
                code=lines[value.lineno - 1].strip(),
            )
        )
    return findings


def iter_python_files(roots: Iterable[Path], excluded_dirs: set[str]) -> Iterable[Path]:
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            yield root
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if any(part in excluded_dirs for part in path.parts):
                continue
            yield path


def default_roots(repo_root: Path) -> list[Path]:
    return [
        path
        for path in sorted(repo_root.iterdir())
        if path.is_dir() and path.name.startswith(DEFAULT_ROOT_PREFIXES)
    ]


def format_text(findings: list[Finding]) -> str:
    if not findings:
        return "No suspicious import-time resource creation found."
    rows = []
    for finding in findings:
        rows.append(
            f"{finding.path}:{finding.line}:{finding.column}: "
            f"{finding.confidence} {finding.category}: {finding.target}\n"
            f"    {finding.code}"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories to audit. Defaults to termin-* and tcplot.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root used for default path discovery and relative paths.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a text report.",
    )
    parser.add_argument(
        "--include-mutable-state",
        action="store_true",
        help="Also report top-level mutable containers as low-confidence bootstrap debt.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "high", "medium", "low"),
        default="none",
        help="Return exit code 1 when findings at this confidence or higher exist.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    roots = [path.resolve() for path in args.paths] if args.paths else default_roots(repo_root)
    findings: list[Finding] = []
    for path in iter_python_files(roots, DEFAULT_EXCLUDED_DIRS):
        findings.extend(
            audit_file(
                path.resolve(),
                root=repo_root,
                include_mutable_state=args.include_mutable_state,
            )
        )
    findings.sort(key=lambda item: (item.path, item.line, item.column))

    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        print(format_text(findings))

    if args.fail_on != "none":
        threshold = CONFIDENCE_RANKS[args.fail_on]
        return int(
            any(CONFIDENCE_RANKS[finding.confidence] >= threshold for finding in findings)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
