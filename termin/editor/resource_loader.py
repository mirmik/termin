"""
Resource loading utilities for the editor.

Handles loading materials, components, and scanning project resources.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from tcbase import log

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
        resource_manager: "ResourceManager",
        get_scene: Callable[[], "Scene"],
        get_project_path: Callable[[], str | None],
        on_resource_reloaded: Callable[[str, str], None],
        log_message: Callable[[str], None] | None = None,
        show_open_file_dialog: Callable[[str, str], str | None] | None = None,
    ):
        self._resource_manager = resource_manager
        self._get_scene = get_scene
        self._get_project_path = get_project_path
        self._on_resource_reloaded = on_resource_reloaded
        self._log = log_message or (lambda msg: None)
        self._show_open_file_dialog = show_open_file_dialog

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
        if self._show_open_file_dialog is None:
            log.error("[ResourceLoader] load_material_from_file: no file dialog callback")
            return

        file_path = self._show_open_file_dialog(
            "Load Material",
            "Shader Files (*.shader);;All Files (*)",
        )
        if not file_path:
            return

        self.load_material_from_path(file_path)

    def load_material_from_path(self, file_path: str) -> None:
        """Load material from a shader file path."""
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

            log.info(f"[ResourceLoader] Material '{material_name}' loaded: "
                     f"{len(material.phases)} phases, "
                     f"marks: {', '.join(p.phase_mark for p in material.phases)}")

        except Exception as e:
            log.error(f"[ResourceLoader] Failed to load material from {file_path}: {e}")

    def load_components_from_file(self) -> None:
        """Load components from a Python file."""
        if self._show_open_file_dialog is None:
            log.error("[ResourceLoader] load_components_from_file: no file dialog callback")
            return

        path = self._show_open_file_dialog(
            "Load Components",
            "Python Files (*.py);;All Files (*)",
        )
        if not path:
            return

        self.load_components_from_path(path)

    def load_components_from_path(self, path: str) -> None:
        """Load components from a Python file path."""
        try:
            loaded = self._resource_manager.scan_components([path])

            if loaded:
                log.info(f"[ResourceLoader] Loaded {len(loaded)} component(s): "
                         + ", ".join(loaded))
            else:
                log.warn(f"[ResourceLoader] No new Component subclasses found in: {path}")

        except Exception as e:
            log.error(f"[ResourceLoader] Failed to load components from {path}: {e}")
