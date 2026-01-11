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