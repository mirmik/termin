from __future__ import annotations

from types import SimpleNamespace

import pytest

from termin.editor_native.editor_viewport import NativeEditorViewport
from termin.gui_native import Document, UiScriptLoader


class _Surface:
    def __init__(self, device, width: int, height: int) -> None:
        self.device = device
        self.size = (width, height)
        self.closed = False

    def is_valid(self) -> bool:
        return not self.closed

    def get_tgfx_color_tex_id(self) -> int:
        return 17

    def framebuffer_size(self) -> tuple[int, int]:
        return self.size

    def resize(self, width: int, height: int) -> bool:
        self.size = (width, height)
        return True

    def dispatch_pointer_move(self, _x: float, _y: float) -> bool:
        return True

    def dispatch_pointer_button(
        self,
        _button: int,
        _action: int,
        _modifiers: int,
        _click_count: int,
    ) -> bool:
        return True

    def dispatch_scroll(self, _x: float, _y: float, _modifiers: int) -> bool:
        return True

    def dispatch_key(
        self,
        _key: int,
        _scancode: int,
        _action: int,
        _modifiers: int,
    ) -> bool:
        return True

    def dispatch_text(self, _codepoint: int) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


class _Display:
    def __init__(self, *, surface, name: str, editor_only: bool) -> None:
        self.surface = surface
        self.name = name
        self.editor_only = editor_only
        self.tc_display_ptr = 41
        self.destroyed = False

    def is_valid(self) -> bool:
        return not self.destroyed

    def dispatch_pointer_move(self, _x, _y) -> bool:
        return True

    def dispatch_pointer_button(self, *_args) -> bool:
        return True

    def dispatch_wheel(self, *_args) -> bool:
        return True

    def dispatch_key(self, *_args) -> bool:
        return True

    def dispatch_text(self, _codepoint) -> bool:
        return True

    def destroy(self) -> None:
        self.destroyed = True


class _Selection:
    def __init__(self) -> None:
        self.selected = None
        self.on_selection_changed = None
        self.on_hover_changed = None

    def clear(self) -> None:
        self.selected = None

    def select(self, value) -> None:
        self.selected = value


class _Interaction:
    _instance = None

    def __init__(self) -> None:
        self.selection = _Selection()
        self.on_request_update = None
        self.on_entity_click = None
        self.on_viewport_pointer_event = None
        self.on_key = None
        self.on_transform_end = None
        self.after_render_count = 0
        self.gizmo_target = None
        self.transform_gizmo = _TransformGizmo()

    @classmethod
    def instance(cls):
        return cls._instance

    @classmethod
    def set_instance(cls, value) -> None:
        cls._instance = value

    def after_render(self) -> None:
        self.after_render_count += 1

    def set_gizmo_target(self, value) -> None:
        self.gizmo_target = value
        self.transform_gizmo.target = value

    def clear_callbacks(self) -> None:
        self.on_request_update = None
        self.on_transform_end = None
        self.on_key = None
        self.on_entity_click = None
        self.on_viewport_pointer_event = None
        self.selection.on_selection_changed = None
        self.selection.on_hover_changed = None


class _TransformGizmo:
    def __init__(self) -> None:
        self.target = None
        self.screen_scales = []

    def set_screen_scale(self, scale: float) -> None:
        self.screen_scales.append(scale)


class _Point:
    def __init__(self, value: float) -> None:
        self.value = value

    def __sub__(self, other: "_Point") -> "_Point":
        return _Point(self.value - other.value)

    def norm(self) -> float:
        return abs(self.value)


class _Entity:
    def __init__(self, position: float) -> None:
        self.transform = SimpleNamespace(
            global_pose=lambda: SimpleNamespace(lin=_Point(position))
        )

    def valid(self) -> bool:
        return True


class _Attachment:
    instances = []

    def __init__(
        self,
        *,
        display,
        rendering_controller,
        rendering_manager,
        make_editor_pipeline,
    ) -> None:
        self.display = display
        self.rendering_controller = rendering_controller
        self.rendering_manager = rendering_manager
        self.make_editor_pipeline = make_editor_pipeline
        self.viewport = None
        self.camera = object()
        self.closed = False
        self.__class__.instances.append(self)

    def attach(self, scene, restore_state: bool) -> None:
        self.scene = scene
        self.restore_state = restore_state
        self.viewport = SimpleNamespace(_viewport_handle=lambda: (3, 9))

    def close(self, save_state: bool = True) -> None:
        self.save_state = save_state
        self.closed = True


class _RenderingManager:
    def __init__(self) -> None:
        self.added = []
        self.removed = []

    def add_editor_display(self, display) -> None:
        self.added.append(display)

    def remove_editor_display(self, display) -> None:
        self.removed.append(display)


def test_native_editor_viewport_uses_legacy_camera_relative_gizmo_scale():
    runtime = object.__new__(NativeEditorViewport)
    target = _Entity(3.0)
    interaction = _Interaction()
    interaction.selection.selected = target
    runtime.interaction = interaction
    runtime.attachment = SimpleNamespace(
        camera=SimpleNamespace(entity=_Entity(8.0))
    )
    renders = []
    runtime._request_render = lambda: renders.append(True)

    runtime.sync_gizmo_target(active_tools=0)

    assert interaction.gizmo_target is target
    assert interaction.transform_gizmo.screen_scales == [0.5]
    assert renders == [True]


def test_native_editor_viewport_owns_render_input_and_shutdown_chain(monkeypatch):
    import termin.display
    import termin.editor._editor_native as editor_native
    import termin.editor_core.editor_scene_attachment as attachment_module
    import termin.editor_native.camera_overlay as camera_overlay_module

    class CameraOverlay:
        instances = []

        def __init__(self, viewport) -> None:
            self.viewport = viewport
            self.rebind_count = 0
            self.closed = False
            self.__class__.instances.append(self)

        @classmethod
        def create(cls, viewport):
            return cls(viewport)

        def rebind_camera(self) -> None:
            self.rebind_count += 1

        def close(self) -> None:
            self.closed = True

    class InputManager:
        def __init__(self, index: int, generation: int, display_ptr: int) -> None:
            self.args = (index, generation, display_ptr)
            self.rebinds = []
            self.detached = False

        def rebind(self, index: int, generation: int, display_ptr: int) -> bool:
            self.rebinds.append((index, generation, display_ptr))
            self.args = (index, generation, display_ptr)
            self.detached = False
            return True

        def detach(self) -> None:
            self.detached = True

    monkeypatch.setattr(termin.display, "FBOSurface", _Surface)
    monkeypatch.setattr(termin.display, "Display", _Display)
    monkeypatch.setattr(editor_native, "EditorInteractionSystem", _Interaction)
    monkeypatch.setattr(editor_native, "EditorViewportInputManager", InputManager)
    monkeypatch.setattr(attachment_module, "EditorSceneAttachment", _Attachment)
    monkeypatch.setattr(
        camera_overlay_module,
        "NativeEditorCameraOverlayProjection",
        CameraOverlay,
    )
    _Attachment.instances.clear()
    _Interaction._instance = None

    document = Document()
    parent = document.create_vstack("viewport-parent")
    manager = _RenderingManager()
    renders = []
    runtime = NativeEditorViewport.create(
        document,
        parent,
        device="device",
        rendering_manager=manager,
        scene="scene",
        request_render=lambda: renders.append(True),
    )

    assert runtime.root.stable_id == "editor.viewport"
    assert manager.added == [runtime.display]
    assert runtime.attachment.scene == "scene"
    assert runtime.attachment.restore_state is False
    assert runtime.input_manager.args == (3, 9, 41)
    assert runtime.widget.has_surface
    assert _Interaction.instance() is runtime.interaction

    loaded_overlay = UiScriptLoader().load_string(
        """
uiscript: 1
root:
  type: Overlay
  name: test_overlay
  children:
    - type: IconButton
      name: test_button
      icon: T
      size: 26
""",
        document=document,
    )
    overlay_root = loaded_overlay.root.widget
    runtime.install_overlay("test", loaded_overlay)
    assert runtime.overlay_names == ("test",)
    assert document.root_count == 0
    with pytest.raises(ValueError, match="already installed"):
        runtime.install_overlay("test", loaded_overlay)
    assert renders == [True]
    renders.clear()

    runtime.attachment.viewport = SimpleNamespace(_viewport_handle=lambda: (7, 11))
    runtime.rebind_input_manager()
    assert runtime.input_manager.rebinds == [(7, 11, 41)]
    assert runtime._camera_overlay.rebind_count == 1

    overlay_enabled = False

    def draw_overlays() -> bool:
        return overlay_enabled

    runtime.configure_interaction(
        on_selection_changed=lambda _entity: None,
        on_hover_changed=lambda _entity: None,
        on_entity_click=lambda _event: False,
        on_pointer=lambda _event: False,
        on_key=lambda _event: False,
        draw_overlays=draw_overlays,
    )
    runtime.after_render()
    assert runtime.interaction.after_render_count == 1
    assert not renders
    overlay_enabled = True
    runtime.after_render()
    assert renders == [True]

    runtime.close()
    assert CameraOverlay.instances[0].closed
    runtime.close()
    assert runtime.input_manager.detached
    assert runtime.attachment.closed
    assert manager.removed == [runtime.display]
    assert runtime.display.destroyed
    assert runtime.surface.closed
    assert _Interaction.instance() is None
    assert not overlay_root.alive
    assert not runtime.root.alive
    assert document.live_widget_count == 1


def test_editor_interaction_callbacks_can_be_cleared_for_owner_shutdown():
    from termin.bootstrap import bootstrap_editor
    from termin.editor._editor_native import EditorInteractionSystem

    bootstrap_editor()
    interaction = EditorInteractionSystem()
    interaction.on_request_update = lambda: None
    interaction.on_transform_end = lambda _old, _new: None
    interaction.on_key = lambda _event: None
    interaction.on_entity_click = lambda _event: False
    interaction.on_viewport_pointer_event = lambda _event: False
    interaction.selection.on_selection_changed = lambda _entity: None
    interaction.selection.on_hover_changed = lambda _entity: None

    interaction.clear_callbacks()
    assert interaction.on_request_update is None
    assert interaction.on_transform_end is None
    assert interaction.on_key is None
