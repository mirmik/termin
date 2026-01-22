"""
Module scanner for automatic C++ module loading.

Scans project directory for .module files and loads them automatically.
"""

from __future__ import annotations

import os
from typing import Callable

from termin._native import log


class ModuleScanner:
    """
    Scans project directory and loads all .module files.

    Used by both Editor and Player to automatically load C++ modules
    when a project is opened.
    """

    def __init__(
        self,
        on_module_loaded: Callable[[str, bool, str], None] | None = None,
        on_scan_complete: Callable[[int, int], None] | None = None,
    ):
        """
        Initialize the module scanner.

        Args:
            on_module_loaded: Callback (name, success, error) called after each module load
            on_scan_complete: Callback (loaded_count, failed_count) called after scan completes
        """
        self._on_module_loaded = on_module_loaded
        self._on_scan_complete = on_scan_complete
        self._engine_paths_configured = False

    def configure_engine_paths(self) -> bool:
        """
        Configure engine include/lib paths for the ModuleLoader.

        Returns:
            True if paths were configured successfully
        """
        from termin.entity._entity_native import ModuleLoader

        loader = ModuleLoader.instance()

        # Already configured
        if loader.core_c:
            self._engine_paths_configured = True
            return True

        import termin

        termin_path = os.path.dirname(termin.__file__)
        project_root = os.path.normpath(os.path.join(termin_path, ".."))

        # Try development paths first (source checkout)
        core_c_dev = os.path.join(project_root, "core_c", "include")
        core_cpp_dev = os.path.join(project_root, "cpp")

        # Check for pip install -e . (editable install) with build dir
        lib_dir_build = os.path.join(
            project_root, "build", "temp.win-amd64-cpython-312", "Release", "bin"
        )
        if not os.path.exists(lib_dir_build):
            lib_dir_build = os.path.join(project_root, "cpp", "build", "bin")

        # Installed package paths
        core_c_pkg = os.path.join(termin_path, "include", "core_c")
        core_cpp_pkg = os.path.join(termin_path, "include", "cpp")
        lib_dir_pkg = os.path.join(termin_path, "lib")

        # Use development paths if available, otherwise installed package
        if os.path.exists(core_c_dev) and os.path.exists(core_cpp_dev):
            core_c = core_c_dev
            core_cpp = core_cpp_dev
            lib_dir = lib_dir_build
        elif os.path.exists(core_c_pkg) and os.path.exists(core_cpp_pkg):
            core_c = core_c_pkg
            core_cpp = core_cpp_pkg
            lib_dir = lib_dir_pkg
        else:
            log.warning("[ModuleScanner] Could not find engine include paths")
            core_c = core_c_dev
            core_cpp = core_cpp_dev
            lib_dir = lib_dir_build

        loader.set_engine_paths(core_c, core_cpp, lib_dir)
        self._engine_paths_configured = True
        return True

    def scan_and_load(self, project_path: str) -> tuple[int, int]:
        """
        Scan project directory and load all .module files.

        Args:
            project_path: Path to the project root directory

        Returns:
            Tuple of (loaded_count, failed_count)
        """
        log.info(f"[ModuleScanner] Scanning for modules in: {project_path}")

        if not self._engine_paths_configured:
            self.configure_engine_paths()

        module_files = self._find_module_files(project_path)
        log.info(f"[ModuleScanner] Found {len(module_files)} .module file(s): {module_files}")

        if not module_files:
            if self._on_scan_complete:
                self._on_scan_complete(0, 0)
            return 0, 0

        loaded = 0
        failed = 0

        for path in module_files:
            if self._load_single_module(path):
                loaded += 1
            else:
                failed += 1

        if self._on_scan_complete:
            self._on_scan_complete(loaded, failed)

        return loaded, failed

    def _find_module_files(self, project_path: str) -> list[str]:
        """
        Recursively find all .module files in the project.

        Args:
            project_path: Path to the project root directory

        Returns:
            Sorted list of .module file paths
        """
        result = []

        for root, dirs, files in os.walk(project_path):
            # Skip hidden dirs, __pycache__, and build directories
            dirs[:] = [d for d in dirs if not d.startswith((".", "__", "build"))]

            for f in files:
                if f.endswith(".module"):
                    result.append(os.path.join(root, f))

        # Sort for deterministic load order
        return sorted(result)

    def _get_module_name(self, module_path: str) -> str:
        """Extract module name from .module JSON file."""
        import json

        try:
            with open(module_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("name", os.path.basename(module_path))
        except Exception:
            return os.path.basename(module_path)

    def _load_single_module(self, module_path: str) -> bool:
        """
        Load a single module and register it for hot-reload.

        Args:
            module_path: Path to the .module file

        Returns:
            True if module was loaded successfully
        """
        from termin.entity._entity_native import ModuleLoader

        log.info(f"[ModuleScanner] Loading module: {module_path}")

        loader = ModuleLoader.instance()
        success = loader.load_module(module_path)
        log.info(f"[ModuleScanner] load_module returned: {success}")

        module_name = self._get_module_name(module_path)

        # Register with ModuleWatcher for hot-reload (even if load failed)
        from termin.editor.module_watcher import get_module_watcher

        watcher = get_module_watcher()
        try:
            watcher.enable()
            watcher.watch_module(module_path)
        except Exception:
            # ModuleWatcher requires Qt which may not be available in Player
            pass

        if success:
            if self._on_module_loaded:
                self._on_module_loaded(module_name, True, "")

            log.info(f"[ModuleScanner] Loaded module: {module_name}")
        else:
            error = loader.last_error

            if self._on_module_loaded:
                self._on_module_loaded(module_name, False, error)

            log.error(f"[ModuleScanner] Failed to load module {module_name}: {error}")

        return success
