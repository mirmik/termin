"""Native implementation of the editor-core asynchronous dialog boundary."""

from __future__ import annotations

from collections.abc import Callable
import logging
import weakref

from termin.editor_core.dialog_service import DialogService
from termin.gui_native import (
    Color,
    DialogAction,
    TcDocument,
    FileDialogMode,
    FileDialogModel,
    MessageBoxKind,
    Rect,
    Size,
)

from .metrics import EDITOR_UI_METRICS


_logger = logging.getLogger(__name__)


class NativeDialogService(DialogService):
    def __init__(
        self,
        document: TcDocument,
        *,
        viewport: Callable[[], Rect],
        request_render: Callable[[], None],
        register_color_picker: Callable[[object], None] | None = None,
        unregister_color_picker: Callable[[object], None] | None = None,
    ) -> None:
        self._document = document
        self._viewport = viewport
        self._request_render = request_render
        self._next_key = 1
        self._active: dict[int, object] = {}
        self._callbacks: dict[int, Callable] = {}
        self._register_color_picker = register_color_picker
        self._unregister_color_picker = unregister_color_picker
        self._color_pickers: dict[int, object] = {}

    @property
    def active_count(self) -> int:
        return len(self._active)

    def _retain(self, dialog, callback: Callable) -> int:
        key = self._next_key
        self._next_key += 1
        self._active[key] = dialog
        self._callbacks[key] = callback
        return key

    def _finish(self, key: int, value) -> None:
        callback = self._callbacks.pop(key, None)
        dialog = self._active.pop(key, None)
        try:
            if callback is None:
                _logger.error("Native dialog finished without callback: %d", key)
            else:
                callback(value)
        finally:
            self._destroy_dialog(key, dialog)
            self._request_render()

    def _discard(self, key: int) -> None:
        self._callbacks.pop(key, None)
        self._destroy_dialog(key, self._active.pop(key, None))

    def _destroy_dialog(self, key: int, dialog) -> None:
        picker = self._color_pickers.pop(key, None)
        if picker is not None and self._unregister_color_picker is not None:
            self._unregister_color_picker(picker)
        if dialog is not None and self._document.is_alive(dialog.handle):
            if not self._document.destroy_widget_recursive(dialog.handle):
                _logger.error("Failed to destroy native dialog: %d", key)

    def show_error(
        self,
        title: str,
        message: str,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        dialog = self._document.create_message_box(title, message, MessageBoxKind.Error)
        key = self._retain(dialog, lambda _result: on_close() if on_close is not None else None)
        weak_service = weakref.ref(self)

        def finished(_result) -> None:
            service = weak_service()
            if service is not None:
                service._finish(key, None)

        dialog.connect_finished(finished)
        if not dialog.show(self._viewport()):
            self._discard(key)
            raise RuntimeError("failed to show native error dialog")
        self._request_render()

    def show_input(
        self,
        title: str,
        message: str,
        default: str,
        on_result: Callable[[str | None], None],
    ) -> None:
        dialog = self._document.create_input_dialog(title, message, default)
        key = self._retain(dialog, on_result)
        weak_service = weakref.ref(self)

        def finished(value: str | None) -> None:
            service = weak_service()
            if service is not None:
                service._finish(key, value)

        dialog.connect_value_finished(finished)
        if not dialog.show(self._viewport()):
            self._discard(key)
            raise RuntimeError("failed to show native input dialog")
        self._request_render()

    def show_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        on_result: Callable[[str | None], None],
        default: str | None = None,
        cancel: str | None = None,
    ) -> None:
        if not choices:
            raise ValueError("native choice dialog requires at least one choice")
        dialog = self._document.create_dialog(title)
        label = self._document.create_label(message, "native-choice-message")
        dialog.set_content(self._document.ref(label.handle))
        action_labels: dict[str, str] = {}
        actions = []
        for index, choice in enumerate(choices):
            action_id = f"choice-{index}"
            action_labels[action_id] = choice
            actions.append(
                DialogAction(
                    action_id,
                    choice,
                    is_default=choice == default,
                    is_cancel=choice == cancel,
                )
            )
        dialog.actions = actions
        key = self._retain(dialog, on_result)
        weak_service = weakref.ref(self)

        def finished(result) -> None:
            service = weak_service()
            if service is None:
                return
            value = action_labels.get(result.action_id)
            if value == cancel:
                value = None
            service._finish(key, value)

        dialog.connect_finished(finished)
        if not dialog.show(self._viewport()):
            self._discard(key)
            raise RuntimeError("failed to show native choice dialog")
        self._request_render()

    def show_color(
        self,
        initial: tuple[float, float, float, float],
        on_result: Callable[[tuple[float, float, float, float] | None], None],
        *,
        title: str = "Color Picker",
        show_alpha: bool = True,
    ) -> None:
        if len(initial) != 4:
            raise ValueError("native color dialog requires four color components")
        dialog = self._document.create_color_dialog(
            Color(*initial),
            show_alpha,
            title,
        )
        key = self._retain(dialog, on_result)
        weak_service = weakref.ref(self)

        def finished(value) -> None:
            service = weak_service()
            if service is None:
                return
            color = None if value is None else (value.r, value.g, value.b, value.a)
            service._finish(key, color)

        dialog.connect_color_finished(finished)
        if not dialog.show(self._viewport()):
            self._discard(key)
            raise RuntimeError("failed to show native color dialog")
        picker = dialog.picker
        if picker is None:
            self._discard(key)
            raise RuntimeError("native color dialog did not create its ColorPicker")
        self._color_pickers[key] = picker
        if self._register_color_picker is not None:
            self._register_color_picker(picker)
        self._request_render()

    def show_layer_mask(
        self,
        current_mask: int,
        layer_names: tuple[str, ...],
        on_result: Callable[[int | None], None],
    ) -> None:
        if len(layer_names) != 64:
            raise ValueError("native layer mask dialog requires 64 layer names")
        dialog = self._document.create_dialog("Layer Mask")
        content = self._document.create_vstack("native-layer-mask-content")
        content.set_layout_spacing(EDITOR_UI_METRICS.spacing)
        content.set_layout_padding(EDITOR_UI_METRICS.collection_insets)
        button_row = self._document.create_hstack("native-layer-mask-buttons")
        button_row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
        all_button = self._document.create_button("All", "native-layer-mask-all")
        none_button = self._document.create_button("None", "native-layer-mask-none")
        button_row.add_stretch_child(all_button.widget)
        button_row.add_stretch_child(none_button.widget)
        content.add_fixed_child(button_row, EDITOR_UI_METRICS.field_row)

        layer_list = self._document.create_vstack("native-layer-mask-list")
        layer_list.set_layout_spacing(EDITOR_UI_METRICS.compact_spacing)
        checkboxes = []
        for index, name in enumerate(layer_names):
            row = self._document.create_hstack(f"native-layer-mask-row-{index}")
            row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
            checkbox = self._document.create_checkbox(bool(current_mask & (1 << index)))
            label = self._document.create_label(
                f"{index}: {name}",
                f"native-layer-mask-label-{index}",
            )
            row.add_fixed_child(checkbox.widget, 26.0)
            row.add_stretch_child(label)
            layer_list.add_fixed_child(row, EDITOR_UI_METRICS.compact_row)
            checkboxes.append(checkbox)
        layer_list.preferred_size = Size(320.0, 64.0 * 30.0)
        scroll = self._document.create_scroll_area("native-layer-mask-scroll")
        scroll.set_scroll_axes(False, True)
        scroll.set_content(layer_list)
        content.add_stretch_child(scroll.widget)
        content.preferred_size = Size(340.0, 430.0)
        dialog.set_content(content)
        dialog.actions = [
            DialogAction("ok", "OK", is_default=True),
            DialogAction("cancel", "Cancel", is_cancel=True),
        ]

        def select_all() -> None:
            for checkbox in checkboxes:
                checkbox.checked = True

        def select_none() -> None:
            for checkbox in checkboxes:
                checkbox.checked = False

        all_button.connect_clicked(select_all)
        none_button.connect_clicked(select_none)
        key = self._retain(dialog, on_result)
        weak_service = weakref.ref(self)

        def finished(result) -> None:
            service = weak_service()
            if service is None:
                return
            if result.action_id != "ok":
                service._finish(key, None)
                return
            mask = 0
            for index, checkbox in enumerate(checkboxes):
                if checkbox.checked:
                    mask |= 1 << index
            service._finish(key, mask)

        dialog.connect_finished(finished)
        if not dialog.show(self._viewport()):
            self._discard(key)
            raise RuntimeError("failed to show native layer mask dialog")
        self._request_render()

    def show_open_file(
        self,
        title: str,
        directory: str,
        filter_string: str,
        on_result: Callable[[str | None], None],
    ) -> None:
        self._show_file_dialog(
            FileDialogMode.OpenFile,
            title,
            directory,
            filter_string,
            on_result,
        )

    def show_save_file(
        self,
        title: str,
        directory: str,
        filter_string: str,
        on_result: Callable[[str | None], None],
        *,
        default_name: str = "",
    ) -> None:
        self._show_file_dialog(
            FileDialogMode.SaveFile,
            title,
            directory,
            filter_string,
            on_result,
            default_name=default_name,
        )

    def _show_file_dialog(
        self,
        mode,
        title: str,
        directory: str,
        filter_string: str,
        on_result: Callable[[str | None], None],
        *,
        default_name: str = "",
    ) -> None:
        dialog = self._document.create_file_dialog(mode)
        dialog.widget.debug_name = title
        dialog.set_initial_directory(directory)
        dialog.set_filters(FileDialogModel.parse_filter_string(filter_string))
        if default_name:
            dialog.set_file_name(default_name)
        key = self._retain(dialog, on_result)
        weak_service = weakref.ref(self)

        def finished(path: str | None) -> None:
            service = weak_service()
            if service is not None:
                service._finish(key, path)

        dialog.connect_path_finished(finished)
        if not dialog.show(self._viewport()):
            self._discard(key)
            raise RuntimeError("failed to show native file dialog")
        self._request_render()


__all__ = ["NativeDialogService"]
