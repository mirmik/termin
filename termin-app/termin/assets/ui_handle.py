"""
UIHandle — умная ссылка на UI layout.

Два режима:
1. Direct — хранит Widget напрямую
2. Asset — хранит UIAsset (lookup по имени через ResourceManager)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.assets.resource_handle import ResourceHandle

if TYPE_CHECKING:
    from tcgui.widgets.widget import Widget
    from termin.assets.ui_asset import UIAsset


class UIHandle(ResourceHandle["Widget", "UIAsset"]):
    """
    Умная ссылка на UI layout.

    Использование:
        handle = UIHandle.from_direct(widget)     # raw Widget
        handle = UIHandle.from_asset(asset)       # UIAsset
        handle = UIHandle.from_name("main_menu")  # lookup в ResourceManager
    """

    _asset_getter = "get_ui_asset"

    @classmethod
    def from_direct(cls, widget: "Widget") -> "UIHandle":
        """Создать handle с raw Widget."""
        handle = cls()
        handle._init_direct(widget)
        return handle

    # Alias for convenience
    from_widget = from_direct

    # --- Convenience accessors ---

    @property
    def widget(self) -> "Widget | None":
        """Получить Widget."""
        return self.get()

    @property
    def root(self) -> "Widget | None":
        """Alias for widget."""
        return self.get()

    @property
    def asset(self) -> "UIAsset | None":
        """Получить UIAsset."""
        return self.get_asset()

    def get_widget(self) -> "Widget | None":
        """Получить Widget."""
        return self.get()

    # --- Serialization ---

    def _serialize_direct(self) -> dict:
        """Сериализовать raw Widget."""
        return {"type": "direct_unsupported"}

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "UIHandle":
        """Десериализация."""
        handle_type = data.get("type", "none")

        if handle_type == "path":
            path = data.get("path")
            if path:
                # Load by path - get name from path
                import os
                name = os.path.splitext(os.path.basename(path))[0]
                return cls.from_name(name)

        if handle_type == "named":
            name = data.get("name")
            if name:
                return cls.from_name(name)

        return cls()
