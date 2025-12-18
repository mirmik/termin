"""GlslAsset - Asset for GLSL include files."""

from __future__ import annotations

from pathlib import Path

from termin.visualization.core.data_asset import DataAsset


class GlslAsset(DataAsset[str]):
    """
    Asset for GLSL include files (.glsl).

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    GlslAsset stores raw GLSL source code that can be included
    into shaders via #include directive. The asset is registered
    by name in ResourceManager.glsl registry.

    Example:
        # Register a GLSL include file
        rm = ResourceManager.instance()
        asset = rm.glsl.get_or_create_asset("shadows", source_path="path/to/shadows.glsl")

        # In shader:
        #include "shadows"
    """

    _uses_binary = False  # GLSL is text

    def __init__(
        self,
        source: str | None = None,
        name: str = "glsl",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize GlslAsset.

        Args:
            source: GLSL source code (can be None for lazy loading)
            name: Include name (used in #include "name")
            source_path: Path to .glsl file
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(data=source, name=name, source_path=source_path, uuid=uuid)

    @property
    def source(self) -> str | None:
        """GLSL source code (lazy-loaded)."""
        return self.data

    @source.setter
    def source(self, value: str | None) -> None:
        """Set source and bump version."""
        self.data = value

    def _parse_content(self, content: str) -> str | None:
        """Parse GLSL content (just return as-is, it's raw GLSL)."""
        return content

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "GlslAsset":
        """
        Create GlslAsset from .glsl file.

        Args:
            path: Path to .glsl file
            name: Include name (defaults to filename without extension)

        Returns:
            GlslAsset with source loaded
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()

        return cls(
            source=source,
            name=name or path.stem,
            source_path=path,
        )

    @classmethod
    def from_source(
        cls,
        source: str,
        name: str,
        uuid: str | None = None,
    ) -> "GlslAsset":
        """
        Create GlslAsset from source string.

        Args:
            source: GLSL source code
            name: Include name
            uuid: Optional fixed UUID

        Returns:
            GlslAsset with source set
        """
        return cls(
            source=source,
            name=name,
            uuid=uuid,
        )
