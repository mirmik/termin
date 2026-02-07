"""
Plugin loader for dynamic loading of Components and FramePasses.

Scans directories, modules, and files for plugin classes.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import pkgutil
import sys
from typing import Callable, Set

from termin._native import log


def scan_paths(
    paths: list[str],
    registry: dict[str, type],
    module_prefix: str = "_dynamic_",
) -> list[str]:
    """
    Scan paths and load classes into registry.

    Classes are auto-registered via __init_subclass__ when modules are imported.

    Args:
        paths: List of paths (files, directories, or module names)
        registry: Dict to track registered classes (before/after comparison)
        module_prefix: Prefix for dynamically loaded modules

    Returns:
        List of newly registered class names
    """
    loaded = []

    for path in paths:
        if os.path.isfile(path) and path.endswith(".py"):
            loaded.extend(_scan_file(path, registry, module_prefix))
        elif os.path.isdir(path):
            loaded.extend(_scan_directory(path, registry, module_prefix))
        else:
            loaded.extend(_scan_module(path, registry))

    return loaded


def _scan_file(
    filepath: str,
    registry: dict[str, type],
    module_prefix: str,
) -> list[str]:
    """Load classes from a single .py file."""
    before = set(registry.keys())

    filename = os.path.basename(filepath)
    module_name = f"{module_prefix}.{os.path.splitext(filename)[0]}_{id(filepath)}"

    try:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return []

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    except Exception as e:
        log.warning(f"Failed to load {filepath}: {e}")
        return []

    after = set(registry.keys())
    return list(after - before)


def _scan_module(
    module_name: str,
    registry: dict[str, type],
) -> list[str]:
    """Load module and all its submodules."""
    before = set(registry.keys())

    try:
        module = importlib.import_module(module_name)

        # If it's a package, scan submodules
        if hasattr(module, "__path__"):
            for importer, name, is_pkg in pkgutil.walk_packages(
                module.__path__, prefix=module_name + "."
            ):
                try:
                    importlib.import_module(name)
                except Exception as e:
                    log.warning(f"Failed to import {name}: {e}")

    except Exception as e:
        log.warning(f"Failed to import module {module_name}: {e}")
        return []

    after = set(registry.keys())
    return list(after - before)


def _scan_directory(
    directory: str,
    registry: dict[str, type],
    module_prefix: str,
) -> list[str]:
    """Scan directory and load all .py files as modules."""
    before = set(registry.keys())

    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]

        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            filepath = os.path.join(root, filename)

            # Create unique module name
            rel_path = os.path.relpath(filepath, directory)
            unique_name = f"{module_prefix}.{rel_path.replace(os.sep, '.')[:-3]}"

            try:
                spec = importlib.util.spec_from_file_location(unique_name, filepath)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[unique_name] = module
                spec.loader.exec_module(module)

            except Exception as e:
                log.warning(f"Failed to load {filepath}: {e}")

    after = set(registry.keys())
    return list(after - before)


def scan_for_subclasses(
    paths: list[str],
    base_class: type,
    registry: dict[str, type],
    module_prefix: str = "_dynamic_",
) -> list[str]:
    """
    Scan paths and find all subclasses of base_class.

    Unlike scan_paths(), this explicitly searches for subclasses
    (useful when classes don't auto-register via __init_subclass__).

    Args:
        paths: List of paths to scan
        base_class: Base class to find subclasses of
        registry: Dict to store found classes
        module_prefix: Prefix for dynamically loaded modules

    Returns:
        List of newly registered class names
    """
    loaded = []

    for path in paths:
        if os.path.isfile(path) and path.endswith(".py"):
            loaded.extend(_scan_file_for_subclasses(path, base_class, registry, module_prefix))
        elif os.path.isdir(path):
            loaded.extend(_scan_directory_for_subclasses(path, base_class, registry, module_prefix))
        else:
            loaded.extend(_scan_module_for_subclasses(path, base_class, registry))

    return loaded


def _scan_file_for_subclasses(
    filepath: str,
    base_class: type,
    registry: dict[str, type],
    module_prefix: str,
) -> list[str]:
    """Load subclasses from a single .py file."""
    before = set(registry.keys())

    filename = os.path.basename(filepath)
    module_name = f"{module_prefix}.{os.path.splitext(filename)[0]}_{id(filepath)}"

    try:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return []

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find subclasses in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, base_class)
                and attr is not base_class
                and attr_name not in registry
            ):
                registry[attr_name] = attr

    except Exception as e:
        log.warning(f"Failed to load {filepath}: {e}")
        return []

    after = set(registry.keys())
    return list(after - before)


def _scan_directory_for_subclasses(
    directory: str,
    base_class: type,
    registry: dict[str, type],
    module_prefix: str,
) -> list[str]:
    """Scan directory for subclasses."""
    loaded = []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]

        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            filepath = os.path.join(root, filename)
            loaded.extend(_scan_file_for_subclasses(filepath, base_class, registry, module_prefix))

    return loaded


def _scan_module_for_subclasses(
    module_name: str,
    base_class: type,
    registry: dict[str, type],
) -> list[str]:
    """Load subclasses from module."""
    before = set(registry.keys())

    try:
        module = importlib.import_module(module_name)

        # Find subclasses in the module itself
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, base_class)
                and attr is not base_class
                and attr_name not in registry
            ):
                registry[attr_name] = attr

        # If it's a package, scan submodules
        if hasattr(module, "__path__"):
            for importer, name, is_pkg in pkgutil.walk_packages(
                module.__path__, prefix=module_name + "."
            ):
                try:
                    submodule = importlib.import_module(name)
                    for attr_name in dir(submodule):
                        attr = getattr(submodule, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, base_class)
                            and attr is not base_class
                            and attr_name not in registry
                        ):
                            registry[attr_name] = attr
                except Exception as e:
                    log.warning(f"Failed to import {name}: {e}")

    except Exception as e:
        log.warning(f"Failed to import module {module_name}: {e}")
        return []

    after = set(registry.keys())
    return list(after - before)
