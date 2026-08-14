def test_editor_native_is_the_editor_private_binding_surface():
    from termin.editor import _editor_native as editor_native

    assert "EditorInteractionSystem" in dir(editor_native)
    assert "FrameGraphDebugger" in dir(editor_native)
    assert "SolidPrimitiveRenderer" in dir(editor_native)
