"""Components, FramePasses, and PostEffects mixin for ResourceManager."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from ._builtins import BUILTIN_COMPONENTS, BUILTIN_FRAME_PASSES, BUILTIN_POST_EFFECTS

if TYPE_CHECKING:
    from termin.visualization.core.entity import Component


class ComponentsMixin:
    """Mixin for component, frame pass, and post effect management."""

    # --------- Компоненты ---------
    def register_component(self, name: str, cls: type["Component"]):
        self.components[name] = cls

    def get_component(self, name: str) -> Optional[type["Component"]]:
        return self.components.get(name)

    def list_component_names(self) -> list[str]:
        return sorted(self.components.keys())

    def register_builtin_components(self) -> List[str]:
        """
        Регистрирует все встроенные компоненты из BUILTIN_COMPONENTS.

        Вызывается при инициализации редактора, чтобы гарантировать
        доступность стандартных компонентов независимо от порядка импортов.

        Returns:
            Список имён успешно зарегистрированных компонентов.
        """
        import importlib
        from tcbase import log

        registered = []

        for module_name, class_name in BUILTIN_COMPONENTS:
            if class_name in self.components:
                # Уже зарегистрирован (например, через __init_subclass__)
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.components[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                log.warning(f"Failed to register component {class_name} from {module_name}: {e}")

        return registered

    def scan_components(self, paths: list[str]) -> list[str]:
        """
        Сканирует директории/модули/файлы и загружает все Component подклассы.

        Args:
            paths: Список путей к директориям, .py файлам или имён модулей.

        Returns:
            Список имён загруженных компонентов.
        """
        from termin.visualization.core.plugin_loader import scan_paths
        return scan_paths(paths, self.components, "_dynamic_components_")

    # --------- FramePass'ы ---------
    def register_frame_pass(self, name: str, cls: type):
        """Регистрирует класс FramePass по имени."""
        self.frame_passes[name] = cls

    def get_frame_pass(self, name: str) -> Optional[type]:
        """Получить класс FramePass по имени."""
        return self.frame_passes.get(name)

    def list_frame_pass_names(self) -> list[str]:
        """Список имён всех зарегистрированных FramePass'ов."""
        return sorted(self.frame_passes.keys())

    def register_builtin_frame_passes(self) -> List[str]:
        """
        Регистрирует все встроенные FramePass'ы из BUILTIN_FRAME_PASSES.

        Returns:
            Список имён успешно зарегистрированных FramePass'ов.
        """
        import importlib
        from tcbase import log

        registered = []

        for module_name, class_name in BUILTIN_FRAME_PASSES:
            if class_name in self.frame_passes:
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.frame_passes[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                log.warning(f"Failed to register frame pass {class_name} from {module_name}: {e}")

        return registered

    def scan_frame_passes(self, paths: list[str]) -> list[str]:
        """
        Сканирует директории/модули/файлы и загружает все FramePass подклассы.

        Args:
            paths: Список путей к директориям, .py файлам или имён модулей.

        Returns:
            Список имён загруженных FramePass'ов.
        """
        from termin.visualization.core.plugin_loader import scan_for_subclasses
        from termin.visualization.render.framegraph.core import FramePass
        return scan_for_subclasses(paths, FramePass, self.frame_passes, "_dynamic_frame_passes_")

    # --------- PostEffect'ы ---------
    def register_post_effect(self, name: str, cls: type):
        """Регистрирует класс PostEffect по имени."""
        self.post_effects[name] = cls

    def get_post_effect(self, name: str) -> Optional[type]:
        """Получить класс PostEffect по имени."""
        return self.post_effects.get(name)

    def list_post_effect_names(self) -> list[str]:
        """Список имён всех зарегистрированных PostEffect'ов."""
        return sorted(self.post_effects.keys())

    def register_builtin_post_effects(self) -> List[str]:
        """
        Регистрирует все встроенные PostEffect'ы из BUILTIN_POST_EFFECTS.

        Returns:
            Список имён успешно зарегистрированных PostEffect'ов.
        """
        import importlib
        from tcbase import log

        registered = []

        for module_name, class_name in BUILTIN_POST_EFFECTS:
            if class_name in self.post_effects:
                registered.append(class_name)
                continue

            try:
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is not None:
                    self.post_effects[class_name] = cls
                    registered.append(class_name)
            except Exception as e:
                log.warning(f"Failed to register post effect {class_name} from {module_name}: {e}")

        return registered
