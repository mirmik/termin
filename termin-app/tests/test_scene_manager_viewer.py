from termin.editor_tcgui.dialogs import scene_manager_viewer as tcgui_viewer


def test_scene_manager_viewers_format_scene_handle_object():
    from termin.engine import SceneManager

    scene_manager = SceneManager()
    scene = scene_manager.create_scene("ViewerHandle", [])
    assert scene is not None

    try:
        handle = scene.scene_handle()
        expected = f"{handle.index}:{handle.generation}"

        assert tcgui_viewer._format_scene_handle(handle) == expected
    finally:
        scene_manager.close_all_scenes()
