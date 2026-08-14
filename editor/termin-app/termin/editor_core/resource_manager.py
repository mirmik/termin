"""Editor resource-manager composition policy."""

from __future__ import annotations

from termin.default_assets.resource_manager import DefaultResourceManager

EditorResourceManager = DefaultResourceManager
ResourceManager = EditorResourceManager


def configure_editor_resource_manager_factory() -> None:
    """Register the editor ResourceManager factory in an explicit bootstrap step."""
    from termin.bootstrap import configure_resource_manager_factory

    configure_resource_manager_factory(EditorResourceManager.instance)


__all__ = [
    "EditorResourceManager",
    "ResourceManager",
    "configure_editor_resource_manager_factory",
]
