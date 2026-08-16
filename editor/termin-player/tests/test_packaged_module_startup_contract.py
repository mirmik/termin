from __future__ import annotations

from pathlib import Path


PLAYER_HOST_SOURCE = Path(__file__).resolve().parents[1] / "src" / "player_runtime_host.cpp"


def _function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    opening_brace = source.index("{", start)
    depth = 0
    for position in range(opening_brace, len(source)):
        token = source[position]
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1 : position]
    raise AssertionError(f"unterminated C++ function: {signature}")


def test_packaged_module_failures_abort_before_package_loading() -> None:
    source = PLAYER_HOST_SOURCE.read_text(encoding="utf-8")
    run_body = _function_body(source, "int run(int argc, char** argv)")
    load_modules_body = _function_body(source, "void load_project_modules()")

    assert run_body.index("load_project_modules();") < run_body.index("load_package();")
    assert "if (!fs::is_directory(manifest.project_modules_root))" in load_modules_body
    assert "if (!fs::is_regular_file(manifest.module_manifest_path))" in load_modules_body
    assert "if (!modules_runtime.discover(manifest.project_modules_root))" in load_modules_body
    assert "if (!modules_runtime.load_all())" in load_modules_body
    assert load_modules_body.count("throw std::runtime_error") == 4


def test_packaged_modules_are_marked_loaded_only_after_complete_closure_load() -> None:
    source = PLAYER_HOST_SOURCE.read_text(encoding="utf-8")
    load_modules_body = _function_body(source, "void load_project_modules()")

    load_call = load_modules_body.index("if (!modules_runtime.load_all())")
    loaded_assignment = load_modules_body.index("modules_loaded = true;")
    assert load_call < loaded_assignment
    assert "modules_loaded = modules_runtime.load_all()" not in load_modules_body
