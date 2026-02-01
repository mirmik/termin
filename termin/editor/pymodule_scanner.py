"""
Python module scanner for automatic Python package loading.

Scans project directory for .pymodule files and loads them automatically.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from typing import Callable

from termin._native import log


class PyModuleScanner:
    """
    Scans project directory and loads all .pymodule files.

    Used by both Editor and Player to automatically load Python packages
    when a project is opened.

    .pymodule file format:
    {
        "name": "module_name",           # Name for logging/UI
        "root": ".",                      # Directory to add to sys.path (relative to .pymodule)
        "packages": ["core", "scripts"], # Packages to import
        "components": []                  # Optional: explicit component class paths
    }
    """

    def __init__(
        self,
        on_module_loaded: Callable[[str, bool, str], None] | None = None,
        on_scan_complete: Callable[[int, int], None] | None = None,
    ):
        """
        Initialize the Python module scanner.

        Args:
            on_module_loaded: Callback (name, success, error) called after each module load
            on_scan_complete: Callback (loaded_count, failed_count) called after scan completes
        """
        self._on_module_loaded = on_module_loaded
        self._on_scan_complete = on_scan_complete
        self._added_paths: list[str] = []

    def scan_and_load(self, project_path: str) -> tuple[int, int]:
        """
        Scan project directory and load all .pymodule files.

        Args:
            project_path: Path to the project root directory

        Returns:
            Tuple of (loaded_count, failed_count)
        """
        module_files = self._find_pymodule_files(project_path)

        if not module_files:
            if self._on_scan_complete:
                self._on_scan_complete(0, 0)
            return 0, 0

        loaded = 0
        failed = 0

        for path in module_files:
            if self._load_single_pymodule(path):
                loaded += 1
            else:
                failed += 1

        if self._on_scan_complete:
            self._on_scan_complete(loaded, failed)

        return loaded, failed

    def _find_pymodule_files(self, project_path: str) -> list[str]:
        """
        Recursively find all .pymodule files in the project.

        Args:
            project_path: Path to the project root directory

        Returns:
            Sorted list of .pymodule file paths
        """
        result = []

        for root, dirs, files in os.walk(project_path):
            # Skip hidden dirs, __pycache__, and build directories
            dirs[:] = [d for d in dirs if not d.startswith((".", "__", "build"))]

            for f in files:
                if f.endswith(".pymodule"):
                    result.append(os.path.join(root, f))

        # Sort for deterministic load order
        return sorted(result)

    def _load_single_pymodule(self, pymodule_path: str) -> bool:
        """
        Load a single .pymodule file.

        Args:
            pymodule_path: Path to the .pymodule file

        Returns:
            True if module was loaded successfully
        """
        try:
            with open(pymodule_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            error = f"Failed to parse {pymodule_path}: {e}"
            log.error(f"[PyModuleScanner] {error}")
            if self._on_module_loaded:
                self._on_module_loaded(os.path.basename(pymodule_path), False, error)
            return False

        name = data.get("name", os.path.basename(pymodule_path))

        # Check if module is ignored
        if data.get("ignore", False):
            log.info(f"[PyModuleScanner] Skipping ignored module: {name}")
            return True  # Treat as success (intentionally skipped)

        root = data.get("root", ".")
        packages = data.get("packages", [])

        # Resolve root path relative to .pymodule file
        pymodule_dir = os.path.dirname(pymodule_path)
        root_path = os.path.normpath(os.path.join(pymodule_dir, root))

        # Add root to sys.path if not already there
        if root_path not in sys.path:
            sys.path.insert(0, root_path)
            self._added_paths.append(root_path)
            log.info(f"[PyModuleScanner] Added to sys.path: {root_path}")

        # Import packages
        errors = []
        for package in packages:
            try:
                importlib.import_module(package)
                log.info(f"[PyModuleScanner] Imported package: {package}")
            except Exception as e:
                error = f"Failed to import {package}: {e}"
                log.error(f"[PyModuleScanner] {error}")
                errors.append(error)

        if errors:
            if self._on_module_loaded:
                self._on_module_loaded(name, False, "; ".join(errors))
            return False

        if self._on_module_loaded:
            self._on_module_loaded(name, True, "")

        return True

    def cleanup(self) -> None:
        """Remove added paths from sys.path."""
        for path in self._added_paths:
            if path in sys.path:
                sys.path.remove(path)
        self._added_paths.clear()
