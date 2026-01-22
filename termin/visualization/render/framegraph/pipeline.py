"""
RenderPipeline — контейнер для конвейера рендеринга.

Содержит:
- passes: список FramePass, определяющих порядок рендеринга
- pipeline_specs: спецификации ресурсов пайплайна
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from termin.visualization.render.framegraph.resource_spec import ResourceSpec

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.core import FramePass

# Import tc_pipeline functions from native module
try:
    from termin._native.render import (
        tc_pipeline_create,
        tc_pipeline_destroy,
        tc_pipeline_add_pass,
        TcPipeline,
    )
    _HAS_TC_PIPELINE = True
except ImportError:
    _HAS_TC_PIPELINE = False


@dataclass
class RenderPipeline:
    """
    Контейнер конвейера рендеринга.

    name: имя пайплайна для сериализации
    passes: список FramePass
    pipeline_specs: спецификации ресурсов пайплайна

    Спецификации ресурсов (размер, очистка, формат) теперь объявляются
    самими pass'ами через метод get_resource_specs().
    """
    name: str = "default"
    passes: List["FramePass"] = field(default_factory=list)
    pipeline_specs: List[ResourceSpec] = field(default_factory=list)

    # C handle for tc_pipeline (set in __post_init__)
    _tc_pipeline: "TcPipeline | None" = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        """Create tc_pipeline and add existing passes."""
        from termin._native import log
        if _HAS_TC_PIPELINE:
            self._tc_pipeline = tc_pipeline_create(self.name)
            # Add existing passes to tc_pipeline
            added = 0
            for p in self.passes:
                tc_pass = getattr(p, '_tc_pass', None)
                if tc_pass is not None:
                    tc_pipeline_add_pass(self._tc_pipeline, tc_pass)
                    added += 1
                else:
                    log.warn(f"[RenderPipeline] pass '{p.pass_name}' has no _tc_pass")
            log.info(f"[RenderPipeline] created '{self.name}' with {added}/{len(self.passes)} passes in tc_pipeline")

    def add_pass(self, frame_pass: "FramePass") -> None:
        """Add a pass to the pipeline."""
        self.passes.append(frame_pass)
        if _HAS_TC_PIPELINE and self._tc_pipeline is not None:
            tc_pass = getattr(frame_pass, '_tc_pass', None)
            if tc_pass is not None:
                tc_pipeline_add_pass(self._tc_pipeline, tc_pass)

    def serialize(self) -> dict:
        """Сериализует RenderPipeline в словарь."""
        from termin.visualization.render.framegraph.core import FramePass

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
        from termin.visualization.render.framegraph.core import FramePass

        passes_data = data.get("passes", [])
        passes = []

        for pass_data in passes_data:
            try:
                p = FramePass.deserialize(pass_data, resource_manager)
                passes.append(p)
            except ValueError as e:
                print(f"Warning: Failed to deserialize FramePass: {e}")

        specs_data = data.get("pipeline_specs", [])
        specs = []
        for spec_data in specs_data:
            spec = ResourceSpec.deserialize(spec_data)
            specs.append(spec)

        return cls(
            name=data.get("name", "default"),
            passes=passes,
            pipeline_specs=specs,
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
        for render_pass in self.passes:
            render_pass.destroy()

        # Destroy tc_pipeline
        if _HAS_TC_PIPELINE and self._tc_pipeline is not None:
            tc_pipeline_destroy(self._tc_pipeline)
            self._tc_pipeline = None

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