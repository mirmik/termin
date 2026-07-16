"""Component and frame pass facade for default resource managers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.scene import Component


class DefaultComponentsMixin:
    """Default component and frame pass registry facade."""

    def register_component(self, name: str, cls: type["Component"]):
        self.component_registry.register(name, cls)

    def get_component(self, name: str) -> type["Component"] | None:
        return self.component_registry.get(name)

    def list_component_names(self) -> list[str]:
        return self.component_registry.list_names()

    def register_builtin_components(self) -> list[str]:
        """Register default built-in components."""
        from termin.default_assets.builtin_types import get_default_builtin_component_specs

        return self.component_registry.register_builtins(get_default_builtin_component_specs())

    def register_frame_pass(self, name: str, cls: type):
        self.frame_pass_registry.register(name, cls)

    def get_frame_pass(self, name: str) -> type | None:
        return self.frame_pass_registry.get(name)

    def list_frame_pass_names(self) -> list[str]:
        return self.frame_pass_registry.list_names()

    def register_builtin_frame_passes(self) -> list[str]:
        """Register default built-in frame passes."""
        from termin.default_assets.builtin_types import get_default_builtin_frame_pass_specs

        return self.frame_pass_registry.register_builtins(get_default_builtin_frame_pass_specs())
