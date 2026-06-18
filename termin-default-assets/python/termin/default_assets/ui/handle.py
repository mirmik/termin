"""UIHandle - smart reference to a UI layout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin_assets import ResourceHandle

if TYPE_CHECKING:
    from tcgui.widgets.widget import Widget
    from termin.default_assets.ui.asset import UIAsset


class UIHandle(ResourceHandle["Widget", "UIAsset"]):
    """Smart reference to a UI layout."""

    _asset_getter = "get_ui_asset"
    _asset_by_uuid_getter = "get_ui_asset_by_uuid"

    @classmethod
    def from_direct(cls, widget: "Widget") -> "UIHandle":
        """Create a handle from a raw Widget."""
        handle = cls()
        handle._init_direct(widget)
        return handle

    from_widget = from_direct

    @property
    def widget(self) -> "Widget | None":
        """Return the Widget."""
        return self.get()

    @property
    def root(self) -> "Widget | None":
        """Alias for widget."""
        return self.get()

    @property
    def asset(self) -> "UIAsset | None":
        """Return the UIAsset."""
        return self.get_asset()

    def get_widget(self) -> "Widget | None":
        """Return the Widget."""
        return self.get()

    def _serialize_direct(self) -> dict:
        """Raw Widgets are not serializable through asset specs."""
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "UIHandle":
        """Deserialize UI handle data."""
        handle_type = data.get("type", "none")

        if handle_type == "uuid":
            uuid = data.get("uuid")
            if uuid:
                return cls.from_uuid(uuid)

        if handle_type == "path":
            path = data.get("path")
            if path:
                from pathlib import Path

                return cls.from_name(Path(path).stem)

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()
