def test_app_native_no_longer_reexports_render_surface():
    import termin._native as native

    assert "render" not in dir(native)


def test_editor_native_is_the_editor_private_binding_surface():
    from termin.editor import _editor_native as editor_native

    assert "EditorInteractionSystem" in dir(editor_native)
    assert "FrameGraphDebuggerCore" in dir(editor_native)
    assert "SolidPrimitiveRenderer" in dir(editor_native)
