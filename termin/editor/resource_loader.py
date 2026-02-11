"""
Resource loading utilities for the editor.

Handles loading materials, components, and scanning project resources.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import QWidget, QFileDialog, QMessageBox
from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.core.scene import Scene


class ResourceLoader:
    """
    Handles resource loading operations for the editor.

    Provides:
    - Loading materials from .shader files
    - Loading components from Python files
    - Scanning project directories for resources
    - Registering scene resources in ResourceManager
    """

    def __init__(
        self,
        parent: QWidget,
        resource_manager: "ResourceManager",
        get_scene: Callable[[], "Scene"],
        get_project_path: Callable[[], str | None],
        on_resource_reloaded: Callable[[str, str], None],
        log_message: Callable[[str], None] | None = None,
    ):
        self._parent = parent
        self._resource_manager = resource_manager
        self._get_scene = get_scene
        self._get_project_path = get_project_path
        self._on_resource_reloaded = on_resource_reloaded
        self._log = log_message or (lambda msg: None)

    def scan_builtin_components(self) -> None:
        """Scan and register built-in component modules."""
        builtin_modules = [
            "termin.visualization.components",
        ]
        loaded = self._resource_manager.scan_components(builtin_modules)
        if loaded:
            log.warning(f"Loaded components: {loaded}")

    def init_resources_from_scene(self) -> None:
        """
        Register meshes and materials from scene entities in ResourceManager.
        Assigns names to unnamed resources.
        """
        from termin.visualization.render.components.mesh_renderer import MeshRenderer

        scene = self._get_scene()
        for ent in scene.entities:
            mr = ent.get_component(MeshRenderer)
            if mr is None:
                continue

            # Register meshes
            mesh = mr.mesh
            if mesh is not None:
                existing_mesh_name = self._resource_manager.find_mesh_name(mesh)
                if existing_mesh_name is None:
                    name = mesh.name
                    if not name:
                        base = f"{ent.name}_mesh" if ent.name else "Mesh"
                        name = base
                        i = 1
                        existing_names = set(self._resource_manager.list_mesh_names())
                        while name in existing_names:
                            i += 1
                            name = f"{base}_{i}"
                    mesh.name = name
                    self._resource_manager.register_mesh(name, mesh)

            # Register materials
            mat = mr.material
            if mat is None:
                continue

            existing_name = self._resource_manager.find_material_name(mat)
            if existing_name is not None:
                continue

            name = mat.name
            if not name:
                base = f"{ent.name}_mat" if ent.name else "Material"
                name = base
                i = 1
                while name in self._resource_manager.materials:
                    i += 1
                    name = f"{base}_{i}"
                mat.name = name

            self._resource_manager.register_material(name, mat)

    def load_material_from_file(self) -> None:
        """Open dialog to select .shader file, parse it and add to ResourceManager."""
        file_path, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Load Material",
            "",
            "Shader Files (*.shader);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not file_path:
            return

        try:
            from termin.visualization.render.shader_parser import parse_shader_text, ShaderMultyPhaseProgramm
            from termin.visualization.core.material import Material

            with open(file_path, "r", encoding="utf-8") as f:
                shader_text = f.read()

            tree = parse_shader_text(shader_text)
            program = ShaderMultyPhaseProgramm.from_tree(tree)
            material = Material.from_parsed(program, source_path=file_path)

            # Determine material name
            material_name = program.program
            if not material_name:
                material_name = os.path.splitext(os.path.basename(file_path))[0]

            # Ensure unique name
            base_name = material_name
            counter = 1
            while material_name in self._resource_manager.materials:
                counter += 1
                material_name = f"{base_name}_{counter}"

            material.name = material_name
            self._resource_manager.register_material(material_name, material)

            QMessageBox.information(
                self._parent,
                "Material Loaded",
                f"Material '{material_name}' loaded successfully.\n"
                f"Phases: {len(material.phases)}\n"
                f"Phase marks: {', '.join(p.phase_mark for p in material.phases)}",
            )

        except Exception as e:
            QMessageBox.critical(
                self._parent,
                "Error Loading Material",
                f"Failed to load material from:\n{file_path}\n\nError: {e}",
            )

    def load_components_from_file(self) -> None:
        """Load components from a Python file."""
        path, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Load Components",
            "",
            "Python Files (*.py);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return

        try:
            loaded = self._resource_manager.scan_components([path])

            if loaded:
                QMessageBox.information(
                    self._parent,
                    "Components Loaded",
                    f"Successfully loaded {len(loaded)} component(s):\n\n"
                    + "\n".join(f"• {name}" for name in loaded),
                )
            else:
                QMessageBox.warning(
                    self._parent,
                    "No Components Found",
                    f"No new Component subclasses found in:\n{path}",
                )

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self._parent,
                "Error Loading Components",
                f"Failed to load components from:\n{path}\n\nError: {e}\n\n{traceback.format_exc()}",
            )
