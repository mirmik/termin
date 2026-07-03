from termin.editor_core.menu_bar_model import build_editor_menu_spec


def _noop():
    return None


def test_debug_menu_contains_camera_frustums_toggle():
    specs = build_editor_menu_spec(
        on_new_project=_noop,
        on_open_project=_noop,
        on_new_scene=_noop,
        on_save_scene=_noop,
        on_save_scene_as=_noop,
        on_load_scene=_noop,
        on_close_scene=_noop,
        on_load_material=_noop,
        on_load_components=_noop,
        on_deploy_stdlib=_noop,
        on_migrate_spec_to_meta=_noop,
        on_exit=_noop,
        on_undo=_noop,
        on_redo=_noop,
        on_settings=_noop,
        on_project_settings=_noop,
        on_toggle_fullscreen=_noop,
        is_fullscreen=lambda: False,
        on_show_spacemouse_settings=_noop,
        on_scene_properties=_noop,
        on_layers_settings=_noop,
        on_shadow_settings=_noop,
        on_pipeline_editor=_noop,
        on_show_agent_types=_noop,
        on_show_navmesh_areas=_noop,
        on_toggle_game_mode=_noop,
        on_build_project=_noop,
        on_build_android=_noop,
        on_build_quest_openxr=_noop,
        on_run_build=_noop,
        on_run_standalone=_noop,
        on_toggle_profiler=_noop,
        is_profiler_visible=lambda: False,
        on_toggle_modules=_noop,
        is_modules_visible=lambda: False,
        on_toggle_camera_frustums=_noop,
        is_camera_frustums_visible=lambda: True,
        on_show_undo_stack_viewer=_noop,
        on_show_framegraph_debugger=_noop,
        on_show_resource_manager_viewer=_noop,
        on_show_audio_debugger=_noop,
        on_show_core_registry_viewer=_noop,
        on_show_inspect_registry_viewer=_noop,
        on_show_navmesh_registry_viewer=_noop,
        on_show_scene_manager_viewer=_noop,
        on_show_python_console=_noop,
        on_show_about=_noop,
        set_undo_handle=_noop,
        set_redo_handle=_noop,
        set_play_handle=_noop,
        set_fullscreen_handle=_noop,
        set_profiler_handle=_noop,
        set_modules_handle=_noop,
        set_camera_frustums_handle=_noop,
    )

    debug_menu = next(spec for spec in specs if spec.name == "Debug")
    item = next(item for item in debug_menu.items if item and item.label == "Camera Frustums")

    assert item.is_checkable is True
    assert item.state_getter is not None
    assert item.state_getter() is True
