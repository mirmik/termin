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


def _top_level_call_from_statement(statement: ast.stmt) -> tuple[ast.Call, str] | None:
    if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
        targets = ", ".join(_assignment_target_name(target) for target in statement.targets)
        return statement.value, targets
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.value, ast.Call):
        return statement.value, _assignment_target_name(statement.target)
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        return statement.value, "<expr>"
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


def audit_file(path: Path, *, root: Path | None = None) -> list[Finding]:
    root = root or Path.cwd()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))

    findings: list[Finding] = []
    for statement in tree.body:
        call_info = _top_level_call_from_statement(statement)
        if call_info is None:
            continue
        call, target = call_info
        if _is_allowed(lines, call.lineno):
            continue
        classification = _classify_call(call)
        if classification is None:
            continue
        category, confidence = classification
        call_name = _call_name(call.func) or "<call>"
        rel_path = path.relative_to(root) if path.is_relative_to(root) else path
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
        "--fail-on",
        choices=("none", "high", "medium"),
        default="none",
        help="Return exit code 1 when findings at this confidence or higher exist.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    roots = [path.resolve() for path in args.paths] if args.paths else default_roots(repo_root)
    findings: list[Finding] = []
    for path in iter_python_files(roots, DEFAULT_EXCLUDED_DIRS):
        findings.extend(audit_file(path.resolve(), root=repo_root))
    findings.sort(key=lambda item: (item.path, item.line, item.column))

    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        print(format_text(findings))

    if args.fail_on == "high":
        return int(any(finding.confidence == "high" for finding in findings))
    if args.fail_on == "medium":
        return int(bool(findings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
