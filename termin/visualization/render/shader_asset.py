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
            with open(self._source_path, "r", encoding="utf-8") as f:
                content = f.read()
            return self.load_from_content(content)
        except Exception:
            return False

    def load_from_content(self, content: str | None, has_uuid_in_spec: bool = False) -> bool:
        """
        Load shader from text content.

        Args:
            content: Shader source text
            has_uuid_in_spec: If True, spec file already has UUID (don't save)

        Returns:
            True if loaded successfully.
        """
        if content is None:
            return False

        try:
            from termin.visualization.render.shader_parser import (
                parse_shader_text,
                ShaderMultyPhaseProgramm,
            )

            tree = parse_shader_text(content)
            self._program = ShaderMultyPhaseProgramm.from_tree(tree)
            self._loaded = True

            # Save spec file if no UUID was in spec
            if not has_uuid_in_spec and self._source_path:
                self._save_spec_file()

            return True
        except Exception as e:
            print(f"[ShaderAsset] Failed to parse content: {e}")
            return False

    def _save_spec_file(self) -> bool:
        """Save UUID to spec file."""
        if self._source_path is None:
            return False

        from termin.editor.project_file_watcher import FilePreLoader

        spec_data = {"uuid": self.uuid}
        if FilePreLoader.write_spec_file(str(self._source_path), spec_data):
            self.mark_just_saved()
            print(f"[ShaderAsset] Added UUID to spec: {self._name}")
            return True
        return False

    def unload(self) -> None:
        """Unload shader to free memory."""
        self._program = None
        self._loaded = False

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
