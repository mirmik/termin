"""Dynamic class scanning helpers."""

from __future__ import annotations

import gc
import importlib
import importlib.util
import keyword
import os
import pkgutil
import sys
import types

from tcbase import log


_filepath_to_module: dict[tuple[str, str], str] = {}


def _file_module_cache_key(filepath: str, module_prefix: str) -> tuple[str, str]:
    return (module_prefix, os.path.realpath(filepath))


def _file_module_name(filepath: str, module_prefix: str) -> str:
    filename = os.path.basename(filepath)
    stem = os.path.splitext(filename)[0]
    real_path = os.path.realpath(filepath)
    return f"{module_prefix}_{stem}_{hash(real_path) & 0xFFFFFFFF:08x}"


def _is_valid_module_part(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


def _project_namespace_module_name(
    filepath: str,
    project_root: str | None,
    namespace: str | None,
) -> str | None:
    if project_root is None or namespace is None:
        return None
    if not _is_valid_module_part(namespace):
        log.warning(f"Invalid project Python namespace: {namespace}")
        return None

    try:
        relative_path = os.path.relpath(os.path.realpath(filepath), os.path.realpath(project_root))
    except ValueError:
        return None
    if relative_path.startswith(".." + os.sep) or relative_path == "..":
        return None

    stem_path = os.path.splitext(relative_path)[0]
    parts = stem_path.split(os.sep)
    if not all(_is_valid_module_part(part) for part in parts):
        log.warning(
            f"Cannot place Python file in project namespace {namespace}: "
            f"path contains non-module identifier parts: {relative_path}"
        )
        return None
    return ".".join((namespace, *parts))


def _module_name_for_file(
    filepath: str,
    module_prefix: str,
    project_root: str | None,
    namespace: str | None,
) -> str:
    namespaced = _project_namespace_module_name(filepath, project_root, namespace)
    if namespaced is not None:
        return namespaced
    return _file_module_name(filepath, module_prefix)


def _ensure_project_namespace_packages(
    module_name: str,
    filepath: str,
    project_root: str | None,
    namespace: str | None,
) -> bool:
    if project_root is None or namespace is None or not module_name.startswith(namespace + "."):
        return True

    package_names = module_name.split(".")[:-1]
    if not package_names:
        return True

    root = os.path.realpath(project_root)
    for index, package_name in enumerate(package_names):
        if index == 0:
            package_path = root
            package_package = ""
        else:
            package_path = os.path.join(root, *package_names[1:index + 1])
            package_package = ".".join(package_names[:index])

        existing = sys.modules.get(package_name)
        if existing is not None:
            package_paths = vars(existing).get("__path__")
            if package_paths is None:
                log.warning(
                    f"Cannot use project Python namespace {namespace}: "
                    f"{package_name} is already loaded as a non-package module"
                )
                return False
            if package_path not in package_paths:
                existing.__path__ = [*package_paths, package_path]
            continue

        package = types.ModuleType(package_name)
        package.__file__ = None
        package.__package__ = package_package
        package.__path__ = [package_path]
        sys.modules[package_name] = package

    return True


def _load_source_file_module(
    module_name: str,
    filepath: str,
    project_root: str | None = None,
    namespace: str | None = None,
):
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec is None:
        log.debug(f"Cannot create module spec for {filepath}")
        return None
    if not _ensure_project_namespace_packages(module_name, filepath, project_root, namespace):
        return None

    module = importlib.util.module_from_spec(spec)
    module.__file__ = filepath
    module.__package__ = module_name.rpartition(".")[0]
    sys.modules[module_name] = module

    with open(filepath, "r", encoding="utf-8") as source_file:
        source = source_file.read()
    exec(compile(source, filepath, "exec"), module.__dict__)
    return module


def scan_paths(
    paths: list[str],
    registry: dict[str, type],
    module_prefix: str = "_dynamic_",
) -> list[str]:
    """Load modules from paths and return newly registered class names."""
    loaded: list[str] = []
    for path in paths:
        if os.path.isfile(path) and path.endswith(".py"):
            loaded.extend(_scan_file(path, registry, module_prefix))
        elif os.path.isdir(path):
            loaded.extend(_scan_directory(path, registry, module_prefix))
        else:
            loaded.extend(_scan_module(path, registry))
    return loaded


def scan_for_subclasses(
    paths: list[str],
    base_class: type,
    registry: dict[str, type],
    module_prefix: str = "_dynamic_",
    *,
    project_root: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    """Load modules from paths and register subclasses of base_class."""
    loaded: list[str] = []
    for path in paths:
        if os.path.isfile(path) and path.endswith(".py"):
            loaded.extend(
                _scan_file_for_subclasses(
                    path,
                    base_class,
                    registry,
                    module_prefix,
                    project_root=project_root,
                    namespace=namespace,
                )
            )
        elif os.path.isdir(path):
            loaded.extend(
                _scan_directory_for_subclasses(
                    path,
                    base_class,
                    registry,
                    module_prefix,
                    project_root=project_root,
                    namespace=namespace,
                )
            )
        else:
            loaded.extend(_scan_module_for_subclasses(path, base_class, registry))
    return loaded


def _scan_file(filepath: str, registry: dict[str, type], module_prefix: str) -> list[str]:
    before = set(registry.keys())
    cache_key = _file_module_cache_key(filepath, module_prefix)
    existing_module_name = _filepath_to_module.get(cache_key)

    if existing_module_name and existing_module_name in sys.modules:
        old_classes = {
            name: cls
            for name, cls in registry.items()
            if cls.__module__ == existing_module_name
        }
        try:
            module = _load_source_file_module(existing_module_name, filepath)
            if module is None:
                return []
        except Exception as e:
            log.warning(f"Failed to reload {filepath}: {e}")
            return []

        new_classes = {
            name: cls
            for name, cls in registry.items()
            if cls.__module__ == existing_module_name
        }
        _update_living_instances(old_classes, new_classes)
    else:
        module_name = _file_module_name(filepath, module_prefix)

        try:
            module = _load_source_file_module(module_name, filepath)
            if module is None:
                return []
            _filepath_to_module[cache_key] = module_name
        except Exception as e:
            log.warning(f"Failed to load {filepath}: {e}")
            return []

    after = set(registry.keys())
    return list(after - before)


def _update_living_instances(old_classes: dict[str, type], new_classes: dict[str, type]) -> None:
    for name, old_cls in old_classes.items():
        new_cls = new_classes.get(name)
        if new_cls is None or new_cls is old_cls:
            continue
        for obj in gc.get_referrers(old_cls):
            if isinstance(obj, old_cls) and type(obj) is old_cls:
                try:
                    obj.__class__ = new_cls
                except Exception as e:
                    log.warning(f"Failed to update instance of {name}: {e}")


def _scan_module(module_name: str, registry: dict[str, type]) -> list[str]:
    before = set(registry.keys())
    try:
        module = importlib.import_module(module_name)
        module_path = module.__dict__.get("__path__")
        if module_path is not None:
            for _importer, name, _is_pkg in pkgutil.walk_packages(
                module_path,
                prefix=module_name + ".",
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


def _scan_directory(directory: str, registry: dict[str, type], module_prefix: str) -> list[str]:
    before = set(registry.keys())
    for root, dirs, files in os.walk(directory):
        dirs[:] = [dirname for dirname in dirs if not dirname.startswith((".", "__"))]
        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            filepath = os.path.join(root, filename)
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


def _scan_file_for_subclasses(
    filepath: str,
    base_class: type,
    registry: dict[str, type],
    module_prefix: str,
    *,
    project_root: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    cache_key = _file_module_cache_key(filepath, module_prefix)
    module_name = _filepath_to_module.get(cache_key)
    if module_name is None:
        module_name = _module_name_for_file(filepath, module_prefix, project_root, namespace)

    old_classes = {
        name: cls
        for name, cls in registry.items()
        if cls.__module__ == module_name
    }
    try:
        module = _load_source_file_module(module_name, filepath, project_root, namespace)
        if module is None:
            return []

        _filepath_to_module[cache_key] = module_name
        changed = _register_module_subclasses(module, base_class, registry)
        new_classes = {
            name: cls
            for name, cls in registry.items()
            if cls.__module__ == module_name
        }
        _update_living_instances(old_classes, new_classes)
    except Exception as e:
        log.warning(f"Failed to load {filepath}: {e}")
        return []

    return changed


def _scan_directory_for_subclasses(
    directory: str,
    base_class: type,
    registry: dict[str, type],
    module_prefix: str,
    *,
    project_root: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    loaded: list[str] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [dirname for dirname in dirs if not dirname.startswith((".", "__"))]
        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            loaded.extend(
                _scan_file_for_subclasses(
                    os.path.join(root, filename),
                    base_class,
                    registry,
                    module_prefix,
                    project_root=project_root,
                    namespace=namespace,
                )
            )
    return loaded


def _scan_module_for_subclasses(
    module_name: str,
    base_class: type,
    registry: dict[str, type],
) -> list[str]:
    before = set(registry.keys())
    try:
        module = importlib.import_module(module_name)
        _register_module_subclasses(module, base_class, registry)

        module_path = module.__dict__.get("__path__")
        if module_path is not None:
            for _importer, name, _is_pkg in pkgutil.walk_packages(
                module_path,
                prefix=module_name + ".",
            ):
                try:
                    submodule = importlib.import_module(name)
                    _register_module_subclasses(submodule, base_class, registry)
                except Exception as e:
                    log.warning(f"Failed to import {name}: {e}")
    except Exception as e:
        log.warning(f"Failed to import module {module_name}: {e}")
        return []

    after = set(registry.keys())
    return list(after - before)


def _register_module_subclasses(module, base_class: type, registry: dict[str, type]) -> list[str]:
    changed: list[str] = []
    for attr_name, attr in vars(module).items():
        if (
            isinstance(attr, type)
            and issubclass(attr, base_class)
            and attr is not base_class
        ):
            existing = registry.get(attr_name)
            if existing is not None and existing.__module__ != attr.__module__:
                log.warning(
                    f"Skipping duplicate dynamic class {attr_name}: "
                    f"{existing.__module__} already registered"
                )
                continue
            registry[attr_name] = attr
            changed.append(attr_name)
    return changed
