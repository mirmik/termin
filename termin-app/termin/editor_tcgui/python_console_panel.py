"""Embedded Python console panel for the tcgui editor."""

from __future__ import annotations

import code
import contextlib
import io
from collections.abc import Callable

from tcbase import log
from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack


class PythonConsolePanel(VStack):
    """Small in-process Python REPL for editor diagnostics."""

    def __init__(self) -> None:
        super().__init__()
        self.spacing = 4

        self._editor = None
        self._get_scene: Callable[[], object | None] | None = None
        self._get_project_path: Callable[[], str | None] | None = None
        self._console = code.InteractiveConsole(locals={})

        self._output = TextArea()
        self._output.read_only = True
        self._output.word_wrap = False
        self._output.stretch = True
        self.add_child(self._output)

        input_row = HStack()
        input_row.spacing = 4
        input_row.preferred_height = px(28)

        self._prompt = Label()
        self._prompt.text = ">>>"
        self._prompt.preferred_width = px(32)
        input_row.add_child(self._prompt)

        self._input = TextInput()
        self._input.stretch = True
        self._input.on_submit = self._on_submit
        input_row.add_child(self._input)

        run_button = Button()
        run_button.text = "Run"
        run_button.preferred_width = px(54)
        run_button.on_click = self._run_current_input
        input_row.add_child(run_button)

        clear_button = Button()
        clear_button.text = "Clear"
        clear_button.preferred_width = px(62)
        clear_button.on_click = self.clear
        input_row.add_child(clear_button)

        self.add_child(input_row)
        self._append("Python console ready.")

    def set_context(
        self,
        *,
        editor: object,
        get_scene: Callable[[], object | None],
        get_project_path: Callable[[], str | None],
    ) -> None:
        self._editor = editor
        self._get_scene = get_scene
        self._get_project_path = get_project_path
        self._refresh_context()

    def clear(self) -> None:
        self._output.text = ""

    def _refresh_context(self) -> None:
        namespace = self._console.locals
        namespace["editor"] = self._editor
        namespace["scene"] = self._get_scene() if self._get_scene is not None else None
        namespace["scene_manager"] = self._editor.scene_manager if self._editor is not None else None
        namespace["project_path"] = self._get_project_path() if self._get_project_path is not None else None

        from termin.assets.resources import ResourceManager
        import termin

        namespace["rm"] = ResourceManager.instance()
        namespace["resource_manager"] = namespace["rm"]
        namespace["termin"] = termin

    def _append(self, text: str) -> None:
        if not text:
            return
        current = self._output.text or ""
        if current and not current.endswith("\n"):
            current += "\n"
        self._output.text = current + text.rstrip("\n") + "\n"

    def _on_submit(self, text: str) -> None:
        self._execute(text)
        self._input.text = ""
        self._input.cursor_pos = 0

    def _run_current_input(self) -> None:
        self._on_submit(self._input.text)

    def _execute(self, text: str) -> None:
        if not text.strip():
            return

        prompt = self._prompt.text
        self._append(f"{prompt} {text}")
        self._refresh_context()

        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
                wants_more = self._console.push(text)
        except Exception:
            log.error("[PythonConsolePanel] internal console execution failure", exc_info=True)
            self._append("Internal console error; see log.")
            self._prompt.text = ">>>"
            return

        captured = stdout.getvalue()
        if captured:
            self._append(captured)

        self._prompt.text = "..." if wants_more else ">>>"
