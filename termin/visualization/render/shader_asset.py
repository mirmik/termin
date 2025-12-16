"""ShaderAsset - Asset for shader programs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.visualization.core.asset import Asset

if TYPE_CHECKING:
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm


class ShaderAsset(Asset):
    """
    Asset for shader program definition.

    Stores ShaderMultyPhaseProgramm (parsed shader with phases, uniforms).
    GPU compilation is handled by ShaderProgram inside MaterialPhase.
    """

    def __init__(
        self,
        program: "ShaderMultyPhaseProgramm | None" = None,
        name: str = "shader",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize ShaderAsset.

        Args:
            program: ShaderMultyPhaseProgramm (can be None for lazy loading)
            name: Human-readable name
            source_path: Path to .shader file for loading/reloading
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(name=name, source_path=source_path, uuid=uuid)
        self._program: "ShaderMultyPhaseProgramm | None" = program
        self._loaded = program is not None

    @property
    def program(self) -> "ShaderMultyPhaseProgramm | None":
        """Shader program definition."""
        return self._program

    @program.setter
    def program(self, value: "ShaderMultyPhaseProgramm | None") -> None:
        """Set program and bump version."""
        self._program = value
        self._loaded = value is not None
        self._bump_version()

    def load(self) -> bool:
        """
        Load shader from source_path.

        Returns:
            True if loaded successfully.
        """
        if self._source_path is None:
            return False

        try:
            from termin.visualization.render.shader_parser import (
                parse_shader_text,
                ShaderMultyPhaseProgramm,
            )

            with open(self._source_path, "r", encoding="utf-8") as f:
                shader_text = f.read()

            tree = parse_shader_text(shader_text)
            self._program = ShaderMultyPhaseProgramm.from_tree(tree)
            self._loaded = True
            return True
        except Exception:
            return False

    def unload(self) -> None:
        """Unload shader to free memory."""
        self._program = None
        self._loaded = False

    # --- Serialization ---

    def serialize(self) -> dict:
        """Serialize shader asset reference."""
        return {
            "uuid": self.uuid,
            "name": self._name,
            "source_path": str(self._source_path) if self._source_path else None,
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "ShaderAsset":
        """Deserialize shader asset (lazy - doesn't load shader)."""
        return cls(
            program=None,
            name=data.get("name", "shader"),
            source_path=data.get("source_path"),
            uuid=data.get("uuid"),
        )

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
    ) -> "ShaderAsset":
        """Create ShaderAsset from existing ShaderMultyPhaseProgramm."""
        return cls(
            program=program,
            name=name or program.program or "shader",
            source_path=source_path,
        )
