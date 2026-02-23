"""
Python module scanner for automatic Python package loading.

Scans project directory for .pymodule files and loads them automatically.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import subprocess
import sys
from typing import Callable

from tcbase import log


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
        "components": [],                # Optional: explicit component class paths
        "requirements": ["numpy", "python-chess"]  # Optional: pip packages to install
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
        requirements = data.get("requirements", [])

        # Resolve root path relative to .pymodule file
        pymodule_dir = os.path.dirname(pymodule_path)
        root_path = os.path.normpath(os.path.join(pymodule_dir, root))

        # Install requirements if specified
        if requirements:
            self._install_requirements(name, requirements)

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

    def _install_requirements(self, module_name: str, requirements: list[str]) -> None:
        """
        Install pip requirements for a module, skipping already-installed packages.

        Args:
            module_name: Name of the module (for logging)
            requirements: List of pip package specifiers (e.g. ["python-chess", "numpy>=1.20"])
        """
        missing = []
        for req in requirements:
            # Extract package name from specifier (e.g. "numpy>=1.20" -> "numpy")
            pkg_name = req.split(">=")[0].split("<=")[0].split("==")[0].split("!=")[0].split("<")[0].split(">")[0].strip()
            try:
                importlib.metadata.distribution(pkg_name)
            except importlib.metadata.PackageNotFoundError:
                missing.append(req)

        if not missing:
            log.info(f"[PyModuleScanner] Module '{module_name}': all requirements satisfied")
            return

        log.info(f"[PyModuleScanner] Module '{module_name}': installing missing requirements: {missing}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", *missing],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                log.info(f"[PyModuleScanner] Successfully installed: {missing}")
                # Ask the same Python where pip installs packages
                sp_result = subprocess.run(
                    [sys.executable, "-c",
                     "import sysconfig; print(sysconfig.get_path('purelib')); print(sysconfig.get_path('platlib'))"],
                    capture_output=True, text=True, timeout=10,
                )
                for line in sp_result.stdout.strip().splitlines():
                    line = line.strip()
                    if line and line not in sys.path:
                        sys.path.insert(0, line)
                        log.info(f"[PyModuleScanner] Added site-packages to sys.path: {line}")
                importlib.invalidate_caches()
            else:
                log.error(f"[PyModuleScanner] pip install failed (code {result.returncode}): {result.stderr}")
        except Exception as e:
            log.error(f"[PyModuleScanner] Failed to run pip: {e}")

    def cleanup(self) -> None:
        """Remove added paths from sys.path."""
        for path in self._added_paths:
            if path in sys.path:
                sys.path.remove(path)
        self._added_paths.clear()
