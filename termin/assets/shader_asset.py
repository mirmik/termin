"""ShaderAsset - Asset for shader programs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm


class ShaderAsset(DataAsset["ShaderMultyPhaseProgramm"]):
    """
    Asset for shader program definition.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores ShaderMultyPhaseProgramm (parsed shader with phases, uniforms).
    GPU compilation is handled by ShaderProgram inside MaterialPhase.
    """

    _uses_binary = False  # Shader text format

    def __init__(
        self,
        program: "ShaderMultyPhaseProgramm | None" = None,
        name: str = "shader",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=program, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def program(self) -> "ShaderMultyPhaseProgramm | None":
        """Shader program definition (lazy-loaded)."""
        return self.data

    @program.setter
    def program(self, value: "ShaderMultyPhaseProgramm | None") -> None:
        """Set program and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "ShaderMultyPhaseProgramm | None":
        """Parse shader source text into ShaderMultyPhaseProgramm."""
        from termin.visualization.render.shader_parser import (
            parse_shader_text,
            ShaderMultyPhaseProgramm,
        )

        tree = parse_shader_text(content)
        return ShaderMultyPhaseProgramm.from_tree(tree)

    # --- Factory methods ---

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "ShaderAsset":
        """Create ShaderAsset from .shader file."""
        from termin.visualization.render.shader_parser import (
            parse_shader_text,
            ShaderMultyPhaseProgramm,
        )

        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            shader_text = f.read()

        tree = parse_shader_text(shader_text)
        program = ShaderMultyPhaseProgramm.from_tree(tree)

        return cls(
            program=program,
            name=name or path.stem,
            source_path=path,
        )

    @classmethod
    def from_program(
        cls,
        program: "ShaderMultyPhaseProgramm",
        name: str | None = None,
        source_path: str | Path | None = None,
        uuid: str | None = None,
    ) -> "ShaderAsset":
        """Create ShaderAsset from existing ShaderMultyPhaseProgramm."""
        return cls(
            program=program,
            name=name or program.program or "shader",
            source_path=source_path,
            uuid=uuid,
        )
