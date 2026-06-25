"""Component and frame pass facade mixin for ResourceManager."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.scene import Component


class ComponentsMixin:
    """Compatibility facade for component and frame pass registries."""

    # --------- Компоненты ---------
    def register_component(self, name: str, cls: type["Component"]):
        self.component_registry.register(name, cls)

    def get_component(self, name: str) -> Optional[type["Component"]]:
        return self.component_registry.get(name)

    def list_component_names(self) -> list[str]:
        return self.component_registry.list_names()

    def register_builtin_components(self) -> List[str]:
        """
        Регистрирует все встроенные компоненты из default providers и app additions.

        Вызывается при инициализации редактора, чтобы гарантировать
        доступность стандартных компонентов независимо от порядка импортов.

        Returns:
            Список имён успешно зарегистрированных компонентов.
        """
        from ._builtins import get_builtin_component_specs

        return self.component_registry.register_builtins(get_builtin_component_specs())

    def scan_components(
        self,
        paths: list[str],
        *,
        project_root: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        """
        Сканирует директории/модули/файлы и загружает все Component подклассы.

        Args:
            paths: Список путей к директориям, .py файлам или имён модулей.

        Returns:
            Список имён загруженных компонентов.
        """
        return self.component_registry.scan(
            paths,
            project_root=project_root,
            namespace=namespace,
        )

    # --------- FramePass'ы ---------
    def register_frame_pass(self, name: str, cls: type):
        """Регистрирует класс FramePass по имени."""
        self.frame_pass_registry.register(name, cls)

    def get_frame_pass(self, name: str) -> Optional[type]:
        """Получить класс FramePass по имени."""
        return self.frame_pass_registry.get(name)

    def list_frame_pass_names(self) -> list[str]:
        """Список имён всех зарегистрированных FramePass'ов."""
        return self.frame_pass_registry.list_names()

    def register_builtin_frame_passes(self) -> List[str]:
        """
        Регистрирует все встроенные FramePass'ы из default providers и app additions.

        Returns:
            Список имён успешно зарегистрированных FramePass'ов.
        """
        from ._builtins import get_builtin_frame_pass_specs

        return self.frame_pass_registry.register_builtins(get_builtin_frame_pass_specs())

    def scan_frame_passes(self, paths: list[str]) -> list[str]:
        """
        Сканирует директории/модули/файлы и загружает все FramePass подклассы.

        Args:
            paths: Список путей к директориям, .py файлам или имён модулей.

        Returns:
            Список имён загруженных FramePass'ов.
        """
        return self.frame_pass_registry.scan(paths)
