"""
RenderPipeline — контейнер для конвейера рендеринга.

Содержит:
- passes: список FramePass, определяющих порядок рендеринга (читается из tc_pipeline)
- pipeline_specs: спецификации ресурсов пайплайна
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Iterator

from termin._native.render import (
    tc_pipeline_create,
    tc_pipeline_destroy,
    tc_pipeline_add_pass,
    tc_pipeline_remove_pass,
    tc_pipeline_insert_pass_before,
    tc_pipeline_get_pass_at,
    TcPipeline,
)
from termin.visualization.render.framegraph.resource_spec import ResourceSpec

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.core import FramePass


@dataclass
class RenderPipeline:
    """
    Контейнер конвейера рендеринга.

    name: имя пайплайна для сериализации
    passes: список FramePass (property, читается из tc_pipeline)
    pipeline_specs: спецификации ресурсов пайплайна

    Спецификации ресурсов (размер, очистка, формат) теперь объявляются
    самими pass'ами через метод get_resource_specs().
    """
    name: str = "default"
    pipeline_specs: List[ResourceSpec] = field(default_factory=list)

    # C handle for tc_pipeline (set in __post_init__)
    _tc_pipeline: "TcPipeline | None" = field(default=None, repr=False, compare=False)

    # Initial passes to add (only used during construction)
    _init_passes: List["FramePass"] = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self):
        """Create tc_pipeline and add initial passes."""
        from termin._native import log

        self._tc_pipeline = tc_pipeline_create(self.name)

        # Add initial passes if provided
        for p in self._init_passes:
            self.add_pass(p)

        # Clear init list - it's no longer needed
        self._init_passes = []

        log.info(f"[RenderPipeline] created '{self.name}' with {self._tc_pipeline.pass_count} passes")

    @property
    def passes(self) -> List["FramePass"]:
        """
        Returns list of passes from tc_pipeline.

        Each tc_pass stores a wrapper pointer to the Python FramePass object.
        """
        if self._tc_pipeline is None:
            return []

        result = []
        count = self._tc_pipeline.pass_count
        for i in range(count):
            tc_pass = tc_pipeline_get_pass_at(self._tc_pipeline, i)
            if tc_pass is not None:
                wrapper = tc_pass.wrapper
                if wrapper is not None:
                    result.append(wrapper)
        return result

    def __iter__(self) -> Iterator["FramePass"]:
        """Iterate over passes."""
        return iter(self.passes)

    def __len__(self) -> int:
        """Return number of passes."""
        if self._tc_pipeline is None:
            return 0
        return self._tc_pipeline.pass_count

    def add_pass(self, frame_pass: "FramePass") -> None:
        """Add a pass to the pipeline."""
        from termin._native import log

        if self._tc_pipeline is None:
            log.error(f"[RenderPipeline.add_pass] _tc_pipeline is None! Cannot add '{frame_pass.pass_name}'")
            return

        tc_pass = frame_pass._tc_pass
        if tc_pass is not None:
            tc_pipeline_add_pass(self._tc_pipeline, tc_pass)
        else:
            log.error(f"[RenderPipeline.add_pass] pass '{frame_pass.pass_name}' ({type(frame_pass).__name__}) has no _tc_pass")

    def remove_pass(self, frame_pass: "FramePass") -> None:
        """Remove a pass from the pipeline."""
        from termin._native import log

        if self._tc_pipeline is None:
            log.error(f"[RenderPipeline.remove_pass] _tc_pipeline is None!")
            return

        tc_pass = frame_pass._tc_pass
        if tc_pass is not None:
            tc_pipeline_remove_pass(self._tc_pipeline, tc_pass)
        else:
            log.error(f"[RenderPipeline.remove_pass] pass '{frame_pass.pass_name}' has no _tc_pass")

    def insert_pass(self, index: int, frame_pass: "FramePass") -> None:
        """
        Insert a pass at the specified index.

        Args:
            index: Position to insert at. If >= len(passes), appends to end.
            frame_pass: The pass to insert.
        """
        from termin._native import log

        if self._tc_pipeline is None:
            log.error(f"[RenderPipeline.insert_pass] _tc_pipeline is None!")
            return

        tc_pass = frame_pass._tc_pass
        if tc_pass is None:
            log.error(f"[RenderPipeline.insert_pass] pass '{frame_pass.pass_name}' has no _tc_pass")
            return

        count = self._tc_pipeline.pass_count
        if index >= count:
            # Append to end
            tc_pipeline_add_pass(self._tc_pipeline, tc_pass)
        else:
            # Insert before the pass at index
            before_tc_pass = tc_pipeline_get_pass_at(self._tc_pipeline, index)
            if before_tc_pass is not None:
                tc_pipeline_insert_pass_before(self._tc_pipeline, tc_pass, before_tc_pass)
            else:
                # Fallback to append
                tc_pipeline_add_pass(self._tc_pipeline, tc_pass)

    def move_pass(self, from_index: int, to_index: int) -> None:
        """
        Move a pass from one position to another.

        Args:
            from_index: Current position of the pass.
            to_index: Target position for the pass.
        """
        from termin._native import log

        if self._tc_pipeline is None:
            log.error(f"[RenderPipeline.move_pass] _tc_pipeline is None!")
            return

        count = self._tc_pipeline.pass_count
        if from_index < 0 or from_index >= count:
            log.error(f"[RenderPipeline.move_pass] from_index {from_index} out of range")
            return
        if to_index < 0 or to_index >= count:
            log.error(f"[RenderPipeline.move_pass] to_index {to_index} out of range")
            return
        if from_index == to_index:
            return

        # Get the pass to move
        tc_pass = tc_pipeline_get_pass_at(self._tc_pipeline, from_index)
        if tc_pass is None:
            return

        # Remove from current position
        tc_pipeline_remove_pass(self._tc_pipeline, tc_pass)

        # Insert at new position
        # After removal, indices shift, so adjust if needed
        insert_index = to_index if to_index < from_index else to_index
        if insert_index >= self._tc_pipeline.pass_count:
            tc_pipeline_add_pass(self._tc_pipeline, tc_pass)
        else:
            before_tc_pass = tc_pipeline_get_pass_at(self._tc_pipeline, insert_index)
            if before_tc_pass is not None:
                tc_pipeline_insert_pass_before(self._tc_pipeline, tc_pass, before_tc_pass)
            else:
                tc_pipeline_add_pass(self._tc_pipeline, tc_pass)

    def serialize(self) -> dict:
        """Сериализует RenderPipeline в словарь."""
        return {
            "name": self.name,
            "passes": [p.serialize() for p in self.passes],
            "pipeline_specs": [spec.serialize() for spec in self.pipeline_specs],
        }

    @classmethod
    def deserialize(cls, data: dict, resource_manager=None) -> "RenderPipeline":
        """
        Десериализует RenderPipeline из словаря.

        Args:
            data: Словарь с сериализованными данными
            resource_manager: ResourceManager для поиска классов

        Returns:
            RenderPipeline
        """
        from termin._native import log
        from termin.visualization.render.framegraph.core import FramePass

        passes_data = data.get("passes", [])
        passes = []

        for pass_data in passes_data:
            try:
                p = FramePass.deserialize(pass_data, resource_manager)
                passes.append(p)
            except ValueError as e:
                log.error(f"[RenderPipeline] Failed to deserialize FramePass: {e}")

        specs_data = data.get("pipeline_specs", [])
        specs = []
        for spec_data in specs_data:
            spec = ResourceSpec.deserialize(spec_data)
            specs.append(spec)

        return cls(
            name=data.get("name", "default"),
            pipeline_specs=specs,
            _init_passes=passes,
        )

    def copy(self) -> "RenderPipeline":
        """Create a deep copy of this pipeline via serialize/deserialize."""
        return RenderPipeline.deserialize(self.serialize())

    def destroy(self) -> None:
        """
        Clean up pipeline resources and callbacks.

        Iterates through all passes and destroys them (clears FBOs and callbacks).
        Should be called before discarding a pipeline to prevent dangling references.
        """
        # Collect passes before destroying tc_pipeline
        passes_to_destroy = list(self.passes)

        if self._tc_pipeline is not None:
            tc_pipeline_destroy(self._tc_pipeline)
            self._tc_pipeline = None

        # Now destroy the passes
        for render_pass in passes_to_destroy:
            render_pass.destroy()

    def get_pass(self, name: str) -> "FramePass | None":
        """
        Find a pass by name.

        Args:
            name: Pass name to find (matches pass_name attribute).

        Returns:
            FramePass with matching name or None.
        """
        for render_pass in self.passes:
            if render_pass.pass_name == name:
                return render_pass
        return None

    def get_passes_by_type(self, pass_type: type) -> List["FramePass"]:
        """
        Find all passes of a given type.

        Args:
            pass_type: Type of passes to find.

        Returns:
            List of passes matching the type.
        """
        return [p for p in self.passes if isinstance(p, pass_type)]

    def get_pass_by_name(self, name: str) -> "FramePass | None":
        """
        Find a pass by its name.

        Args:
            name: Name of the pass to find.

        Returns:
            FramePass with the specified name, or None if not found.
        """
        for render_pass in self.passes:
            if render_pass.pass_name == name:
                return render_pass
        return None
