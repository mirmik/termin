"""Embedded Python console panel for the tcgui editor."""

from __future__ import annotations

from collections.abc import Callable

from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.units import px
from tcgui.widgets.vstack import VStack

from termin.editor_core.python_executor import EditorPythonExecutor


class PythonConsolePanel(VStack):
    """Small in-process Python REPL for editor diagnostics."""

    def __init__(self) -> None:
        super().__init__()
        self.spacing = 4

        self._editor = None
        self._get_scene: Callable[[], object | None] | None = None
        self._get_project_path: Callable[[], str | None] | None = None
        self._executor: EditorPythonExecutor | None = None

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
        executor: EditorPythonExecutor | None = None,
    ) -> None:
        self._editor = editor
        self._get_scene = get_scene
        self._get_project_path = get_project_path
        self._executor = executor or EditorPythonExecutor(self._build_context)

    def clear(self) -> None:
        self._output.text = ""

    def _build_context(self) -> dict[str, object | None]:
        scene = self._get_scene() if self._get_scene is not None else None
        scene_name = self._editor.editor_scene_name if self._editor is not None else None
        selected = self._editor.selected_entity if self._editor is not None else None
        return {
            "editor": self._editor,
            "scene": scene,
            "scene_name": scene_name,
            "editor_scene_name": scene_name,
            "current_scene": scene,
            "current_scene_name": scene_name,
            "selected": selected,
            "selected_entity": selected,
            "scene_manager": self._editor.scene_manager if self._editor is not None else None,
            "project_path": (
                self._get_project_path() if self._get_project_path is not None else None
            ),
        }

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
        if self._executor is None:
            self._executor = EditorPythonExecutor(self._build_context)

        result = self._executor.execute_repl_line(text)
        if result.output:
            self._append(result.output)
        if result.error:
            self._append(result.error)

        self._prompt.text = "..." if result.wants_more else ">>>"
