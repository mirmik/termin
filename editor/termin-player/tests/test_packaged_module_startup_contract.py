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
    assert "requires packaged owner module" in load_modules_body
    assert load_modules_body.count("throw std::runtime_error") == 5


def test_packaged_modules_are_marked_loaded_only_after_complete_closure_load() -> None:
    source = PLAYER_HOST_SOURCE.read_text(encoding="utf-8")
    load_modules_body = _function_body(source, "void load_project_modules()")

    load_call = load_modules_body.index("if (!modules_runtime.load_all())")
    loaded_assignment = load_modules_body.index("modules_loaded = true;")
    assert load_call < loaded_assignment
    assert "modules_loaded = modules_runtime.load_all()" not in load_modules_body


def test_packaged_manifest_requires_matching_world_controller_metadata() -> None:
    source = PLAYER_HOST_SOURCE.read_text(encoding="utf-8")
    load_manifest_body = _function_body(source, "AppManifest load_app_manifest(")
    load_package_body = _function_body(source, "void load_package()")

    assert "app manifest requires schema version 2" in load_manifest_body
    assert "required_world_controller_selection(" in load_manifest_body
    assert "package_contract.world_controller" in load_manifest_body
    assert "package.world_controller != manifest.world_controller" in load_package_body


def test_packaged_player_starts_session_before_loading_scenes_and_uses_engine_safe_point() -> None:
    source = PLAYER_HOST_SOURCE.read_text(encoding="utf-8")
    run_body = _function_body(source, "int run(int argc, char** argv)")
    begin_body = _function_body(source, "void begin_runtime_session()")
    register_body = _function_body(source, "void register_scenes()")
    activate_body = _function_body(source, "void activate_initial_scene()")

    assert run_body.index("load_project_modules();") < run_body.index("begin_runtime_session();")
    assert run_body.index("begin_runtime_session();") < run_body.index("load_package();")
    assert run_body.index("load_package();") < run_body.index("register_scenes();")
    assert run_body.index("initialize_window_and_rendering();") < run_body.index(
        "activate_initial_scene();"
    )
    assert "WorldControllerInstance::create(" in begin_body
    assert "selection.type.c_str(), selection.module.c_str()" in begin_body
    assert "engine->begin_session()" in begin_body
    assert "engine->bind_runtime_scene(packaged_scene.scene.handle())" in register_body
    assert "TC_SCENE_MODE_PLAY" not in register_body
    assert "world_context.transition_to(scene_name)" in activate_body
    assert "engine->tick_and_render(0.0)" in activate_body


def test_packaged_player_tears_down_project_objects_before_module_runtime() -> None:
    source = PLAYER_HOST_SOURCE.read_text(encoding="utf-8")
    shutdown_body = _function_body(source, "void shutdown()")
    unload_body = _function_body(source, "void unload_project_modules()")

    end_session = shutdown_body.index("engine->end_session()")
    destroy_package = shutdown_body.index("package.destroy();")
    shutdown_engine = shutdown_body.index("engine->shutdown()")
    unload_modules = shutdown_body.index("unload_project_modules();")
    assert end_session < destroy_package < shutdown_engine < unload_modules
    assert "modules_runtime.shutdown()" in unload_body
