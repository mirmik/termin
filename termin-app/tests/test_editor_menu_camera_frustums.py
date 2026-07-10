from termin.editor_core.menu_bar_model import (
    DebugMenuActions,
    EditMenuActions,
    EditorMenuActions,
    EditorMenuHandleSetters,
    EditorMenuSpecConfig,
    EditorMenuStateGetters,
    FileMenuActions,
    GameMenuActions,
    HelpMenuActions,
    NavigationMenuActions,
    SceneMenuActions,
    ViewMenuActions,
    build_editor_menu_spec,
)


def _noop():
    return None


def _menu_config() -> EditorMenuSpecConfig:
    return EditorMenuSpecConfig(
        actions=EditorMenuActions(
            file=FileMenuActions(
                new_project=_noop,
                open_project=_noop,
                new_scene=_noop,
                save_scene=_noop,
                save_scene_as=_noop,
                load_scene=_noop,
                close_scene=_noop,
                load_material=_noop,
                load_components=_noop,
                deploy_stdlib=_noop,
                exit=_noop,
            ),
            edit=EditMenuActions(
                undo=_noop,
                redo=_noop,
                settings=_noop,
                project_settings=_noop,
            ),
            view=ViewMenuActions(
                toggle_fullscreen=_noop,
                show_spacemouse_settings=_noop,
            ),
            scene=SceneMenuActions(
                scene_properties=_noop,
                layers_settings=_noop,
                shadow_settings=_noop,
                pipeline_editor=_noop,
            ),
            navigation=NavigationMenuActions(
                show_agent_types=_noop,
                show_navmesh_areas=_noop,
            ),
            game=GameMenuActions(
                toggle_game_mode=_noop,
                build_project=_noop,
                build_android=_noop,
                build_quest_openxr=_noop,
                run_build=_noop,
                run_standalone=_noop,
            ),
            debug=DebugMenuActions(
                toggle_profiler=_noop,
                toggle_modules=_noop,
                toggle_camera_frustums=_noop,
                show_undo_stack_viewer=_noop,
                show_framegraph_debugger=_noop,
                show_audio_debugger=_noop,
                show_scene_manager_viewer=_noop,
                show_python_console=_noop,
            ),
            help=HelpMenuActions(
                show_about=_noop,
            ),
        ),
        states=EditorMenuStateGetters(
            fullscreen=lambda: False,
            profiler_visible=lambda: False,
            modules_visible=lambda: False,
            camera_frustums_visible=lambda: True,
        ),
        handles=EditorMenuHandleSetters(
            undo=_noop,
            redo=_noop,
            play=_noop,
            fullscreen=_noop,
            profiler=_noop,
            modules=_noop,
            camera_frustums=_noop,
        ),
    )


def test_debug_menu_contains_camera_frustums_toggle():
    specs = build_editor_menu_spec(_menu_config())

    debug_menu = next(spec for spec in specs if spec.name == "Debug")
    item = next(item for item in debug_menu.items if item and item.label == "Camera Frustums")

    assert item.is_checkable is True
    assert item.state_getter is not None
    assert item.state_getter() is True
