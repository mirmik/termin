from termin.editor_native.frame_profiler import (
    build_native_frame_profiler,
    connect_frame_profiler_command,
)
from termin.gui_native import (
    CommandData,
    CommandModel,
    EventResult,
    FrameTimelineModel,
    FrameTimelineSample,
    PointerEvent,
    PointerEventType,
    Rect,
    RichTextModel,
    TreeTableModel,
)


class FakeNativeController:
    def __init__(self) -> None:
        self.command_model = CommandModel()
        self.action = self.command_model.append(CommandData("action", "Action"))
        self.timeline_model = FrameTimelineModel()
        self.section_model = TreeTableModel()
        self.summary_model = RichTextModel()
        self.detail_model = RichTextModel()
        self.status_model = RichTextModel()
        self.capacity = 16
        self.hitch_ratio = 1.25
        self.capturing = False
        self.follow_latest = True
        self.selected_frame_number = -1
        self.update_result = False
        self.closed = False
        self.activations = []
        self.frame_selections = []
        self.section_selections = []

    def start_capture(self) -> None:
        self.capturing = True

    def pause(self) -> None:
        self.capturing = False

    def clear(self) -> None:
        self.timeline_model.clear()
        self.section_model.clear()

    def close(self) -> None:
        self.pause()
        self.closed = True

    def update(self) -> bool:
        result = self.update_result
        self.update_result = False
        return result

    def activate(self, command_id: int) -> bool:
        self.activations.append(command_id)
        if command_id != self.action:
            return False
        self.follow_latest = True
        if self.timeline_model.samples:
            self.selected_frame_number = self.timeline_model.samples[-1].stable_id
        return True

    def select_frame(self, frame_number: int) -> bool:
        self.frame_selections.append(frame_number)
        self.selected_frame_number = frame_number
        self.follow_latest = False
        return True

    def show_section_details(self, node: int) -> None:
        self.section_selections.append(node)


class FakeWindow:
    def __init__(self, on_close) -> None:
        self.closed = False
        self._on_close = on_close
        self.render_requests = 0

    def request_render_update(self) -> None:
        self.render_requests += 1

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self._on_close()


class FakeWindowManager:
    def __init__(self) -> None:
        self.created = []

    def create_window(self, title, width, height, *, document, on_close):
        window = FakeWindow(on_close)
        self.created.append((title, width, height, document, window))
        return window


class FakeMenuRoute:
    def __init__(self) -> None:
        self.callback = None

    def connect_activated(self, callback) -> None:
        self.callback = callback


def test_native_frame_profiler_hosts_controller_owned_models():
    controller = FakeNativeController()
    profiler = build_native_frame_profiler(object(), controller)

    assert profiler.timeline.model is controller.timeline_model
    assert profiler.section_table.model is controller.section_model


def test_native_frame_profiler_window_lifecycle_controls_native_capture():
    controller = FakeNativeController()
    manager = FakeWindowManager()
    profiler = build_native_frame_profiler(manager, controller)
    route = FakeMenuRoute()
    connect_frame_profiler_command(route, 42, profiler)

    route.callback(0, 42, None)
    assert controller.capturing
    assert len(manager.created) == 1
    window = manager.created[0][-1]
    assert window.render_requests > 0

    controller.timeline_model.set_samples([FrameTimelineSample(7, 20.0, 8.0)])
    controller.selected_frame_number = 7
    controller.update_result = True
    assert profiler.update()
    assert profiler.timeline.selected_id == 7

    profiler.dismiss()
    assert not controller.capturing
    profiler.close()
    assert controller.closed


def test_native_frame_profiler_clear_only_delegates_to_native_controller():
    controller = FakeNativeController()
    controller.timeline_model.set_samples([FrameTimelineSample(1, 16.0, 8.0)])
    profiler = build_native_frame_profiler(object(), controller)
    profiler.clear()
    assert controller.timeline_model.samples == []


def test_enabling_follow_does_not_feed_programmatic_selection_back_to_controller():
    controller = FakeNativeController()
    controller.follow_latest = False
    controller.timeline_model.set_samples(
        [FrameTimelineSample(1, 16.0, 8.0), FrameTimelineSample(2, 17.0, 9.0)]
    )
    profiler = build_native_frame_profiler(object(), controller)
    profiler.timeline.follow_latest = False
    profiler.timeline.select(1)
    controller.selected_frame_number = 1
    controller.frame_selections.clear()

    profiler.document.layout_roots(Rect(0.0, 0.0, 1180.0, 760.0))
    action_rect = profiler.toolbar.item_rects[0]
    pointer = PointerEvent()
    pointer.x = action_rect.x + action_rect.width / 2.0
    pointer.y = action_rect.y + action_rect.height / 2.0
    pointer.type = PointerEventType.Down
    assert profiler.document.dispatch_pointer_event(pointer) == EventResult.Handled
    pointer.type = PointerEventType.Up
    assert profiler.document.dispatch_pointer_event(pointer) == EventResult.Handled

    assert controller.frame_selections == []
    assert controller.follow_latest
    assert controller.selected_frame_number == 2
    assert profiler.timeline.follow_latest
    assert profiler.timeline.selected_id == 2
