"""Toolkit-neutral summary and editor handoff for pipeline assets."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable

from termin.editor_core.pipeline_editor_model import PipelineEditorController


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineInspectorSnapshot:
    available: bool
    name: str = ""
    path: str = ""
    nodes: int = 0
    connections: int = 0
    passes: tuple[str, ...] = ()
    message: str = "No pipeline selected."


class PipelineInspectorController:
    """Projects pipeline metadata and delegates editing to the graph editor."""

    def __init__(
        self,
        editor: PipelineEditorController,
        *,
        open_editor: Callable[[], None],
    ) -> None:
        self._editor = editor
        self._open_editor = open_editor
        self._snapshot = PipelineInspectorSnapshot(False)

    @property
    def snapshot(self) -> PipelineInspectorSnapshot:
        return self._snapshot

    def set_target(
        self,
        pipeline,
        *,
        name: str = "",
        file_path: str | None = None,
    ) -> PipelineInspectorSnapshot:
        if file_path:
            try:
                graph = self._editor.load(file_path)
            except Exception as exc:
                self._snapshot = PipelineInspectorSnapshot(
                    False,
                    name=Path(file_path).stem,
                    path=file_path,
                    message=f"Pipeline failed to load: {exc}",
                )
                return self._snapshot
            pass_names = tuple(
                node.title
                for node in graph.nodes.values()
                if node.data.get("node_type", node.kind) in ("pass", "effect")
            )
            self._snapshot = PipelineInspectorSnapshot(
                True,
                name=Path(file_path).stem,
                path=file_path,
                nodes=len(graph.nodes),
                connections=len(graph.edges),
                passes=pass_names,
                message="",
            )
            return self._snapshot
        if pipeline is None:
            self._snapshot = PipelineInspectorSnapshot(False)
            return self._snapshot
        passes = tuple(
            str(getattr(item, "pass_name", type(item).__name__))
            for item in getattr(pipeline, "passes", ())
        )
        self._snapshot = PipelineInspectorSnapshot(
            True,
            name=name,
            nodes=len(passes),
            passes=passes,
            message="Runtime pipeline; select its source asset to edit.",
        )
        return self._snapshot

    def edit(self) -> None:
        if self._editor.file_path is None:
            raise ValueError("pipeline inspector has no editable source file")
        self._open_editor()


__all__ = ["PipelineInspectorController", "PipelineInspectorSnapshot"]
