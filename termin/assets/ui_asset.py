"""UIAsset - Asset for widget-based UI layouts (.ui.yaml files)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from tcgui.widgets.widget import Widget


class UIAsset(DataAsset["Widget"]):
    """
    Asset for widget-based UI layouts.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores Widget tree loaded from YAML files.
    """

    _uses_binary = False  # YAML text format

    def __init__(
        self,
        widget: "Widget | None" = None,
        name: str = "ui",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=widget, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def widget(self) -> "Widget | None":
        """Root widget (lazy-loaded)."""
        return self.data

    @widget.setter
    def widget(self, value: "Widget | None") -> None:
        """Set widget and bump version."""
        self.data = value

    @property
    def root(self) -> "Widget | None":
        """Alias for widget."""
        return self.data

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "Widget | None":
        """Parse YAML content into Widget tree."""
        from tcgui.widgets.loader import UILoader

        loader = UILoader()
        return loader.load_string(content)

    # --- Factory methods ---

    @classmethod
    def from_widget(
        cls,
        widget: "Widget",
        name: str | None = None,
        source_path: Path | str | None = None,
    ) -> "UIAsset":
        """Create UIAsset from existing Widget."""
        asset_name = name or widget.name or "ui"
        return cls(widget=widget, name=asset_name, source_path=source_path)
