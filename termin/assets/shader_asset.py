"""ShaderAsset - Asset for shader programs."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.data_asset import DataAsset
from termin._native import log
from termin._native.render import TcShader

if TYPE_CHECKING:
    from termin.visualization.render.shader_parser import ShaderMultyPhaseProgramm


def make_phase_uuid(shader_uuid: str, phase_mark: str) -> str:
    """Generate deterministic UUID for shader phase.

    Uses UUID5 (SHA-1 based) to create stable UUID from shader UUID + phase mark.
    """
    if not phase_mark:
        return shader_uuid
    try:
        base = uuid.UUID(shader_uuid)
        return str(uuid.uuid5(base, phase_mark))
    except ValueError:
        # Invalid UUID format, fallback
        log.warning(f"[ShaderAsset] Invalid shader UUID format: {shader_uuid}")
        return shader_uuid


def update_material_shader(material, program, shader_name: str, shader_uuid: str) -> None:
    """Update material's shader with proper phase UUIDs for hot-reload.

    Args:
        material: TcMaterial to update
        program: ShaderMultyPhaseProgramm - new shader program
        shader_name: Shader name
        shader_uuid: Shader asset UUID
    """
    from termin._native.render import TcRenderState
    from termin.assets.material_asset import _build_render_state, _apply_uniform_defaults, _apply_texture_defaults
    from termin.assets.resources import ResourceManager

    if not program.phases:
        raise ValueError("Program has no phases")

    # Preserve existing uniforms/textures from first phase
    old_uniforms = {}
    old_textures = {}
    if material.phase_count > 0:
        phase = material.get_phase(0)
        if phase is not None:
            old_uniforms = dict(phase.uniforms)
            old_textures = dict(phase.textures)

    # Clear existing phases and rebuild
    material.clear_phases()
    material.shader_name = shader_name or program.program

    rm = ResourceManager.instance()

    for shader_phase in program.phases:
        # Get shader sources
        vertex_source = ""
        fragment_source = ""
        geometry_source = ""

        if "vertex" in shader_phase.stages:
            vertex_source = shader_phase.stages["vertex"].source
        if "fragment" in shader_phase.stages:
            fragment_source = shader_phase.stages["fragment"].source
        if "geometry" in shader_phase.stages:
            geometry_source = shader_phase.stages["geometry"].source

        if not vertex_source or not fragment_source:
            log.warning(f"[update_material_shader] Phase missing vertex or fragment shader")
            continue

        # Build render state
        state = _build_render_state(shader_phase, shader_phase.phase_mark)

        # Add phase
        phase = material.add_phase_from_sources(
            vertex_source=vertex_source,
            fragment_source=fragment_source,
            geometry_source=geometry_source,
            shader_name=shader_name or program.program,
            phase_mark=shader_phase.phase_mark,
            priority=shader_phase.priority,
            state=state,
        )

        if phase is None:
            log.error(f"[update_material_shader] Failed to add phase")
            continue

        # Apply shader features
        shader = phase.shader
        for feature in program.features:
            if feature == "lighting_ubo":
                shader.set_feature(1)

        # Set available marks
        if shader_phase.available_marks:
            phase.set_available_marks(shader_phase.available_marks)

        # Apply uniform defaults from shader, then restore old values
        _apply_uniform_defaults(phase, shader_phase, old_uniforms)

        # Apply texture defaults, then restore old textures
        _apply_texture_defaults(phase, shader_phase, rm)
        for key, tex in old_textures.items():
            if tex is not None and tex.is_valid:
                phase.set_texture(key, tex)


class ShaderAsset(DataAsset["ShaderMultyPhaseProgramm"]):
    """
    Asset for shader program definition.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores ShaderMultyPhaseProgramm (parsed shader with phases, uniforms).
    GPU compilation is handled by TcShader inside MaterialPhase.
    """

    _uses_binary = False  # Shader text format

    def __init__(
        self,
        program: "ShaderMultyPhaseProgramm | None" = None,
        name: str = "shader",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=program, name=name, source_path=source_path, uuid=uuid)

    # --- Convenience property ---

    @property
    def program(self) -> "ShaderMultyPhaseProgramm | None":
        """Shader program definition (lazy-loaded)."""
        return self.data

    @program.setter
    def program(self, value: "ShaderMultyPhaseProgramm | None") -> None:
        """Set program and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "ShaderMultyPhaseProgramm | None":
        """Parse shader source text into ShaderMultyPhaseProgramm."""
        from termin.visualization.render.shader_parser import (
            parse_shader_text,
            ShaderMultyPhaseProgramm,
        )

        tree = parse_shader_text(content)
        return ShaderMultyPhaseProgramm.from_tree(tree)

    def _update_tc_shaders(self) -> None:
        """Update tc_shader registry for hot-reload."""
        if self._data is None or not self._uuid:
            return

        # Update tc_shader for each phase so existing TcShaders see new sources
        for phase in self._data.phases:
            phase_mark = phase.phase_mark
            phase_uuid = make_phase_uuid(self._uuid, phase_mark)

            # Find existing tc_shader (don't create - it's created by MaterialPhase)
            tc = TcShader.from_uuid(phase_uuid)
            if not tc.is_valid:
                log.info(f"[ShaderAsset] _update_tc_shaders: tc_shader not found for {phase_uuid}, skipping")
                continue

            # Get sources from phase
            vs = phase.stages.get("vertex")
            fs = phase.stages.get("fragment")
            gs = phase.stages.get("geometry")

            vertex_src = vs.source if vs else ""
            fragment_src = fs.source if fs else ""
            geometry_src = gs.source if gs else ""

            # Update sources in tc_shader (bumps version if changed)
            changed = tc.set_sources(vertex_src, fragment_src, geometry_src, self._name, str(self._source_path) if self._source_path else "")
            log.info(f"[ShaderAsset] _update_tc_shaders uuid={phase_uuid} changed={changed} ver={tc.version}")

    def _on_loaded(self) -> None:
        """After loading/reloading, update tc_shader registry for hot-reload."""
        self._update_tc_shaders()

    # --- Factory methods ---

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "ShaderAsset":
        """Create ShaderAsset from .shader file."""
        from termin.visualization.render.shader_parser import (
            parse_shader_text,
            ShaderMultyPhaseProgramm,
        )

        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            shader_text = f.read()

        tree = parse_shader_text(shader_text)
        program = ShaderMultyPhaseProgramm.from_tree(tree)

        return cls(
            program=program,
            name=name or path.stem,
            source_path=path,
        )

    @classmethod
    def from_program(
        cls,
        program: "ShaderMultyPhaseProgramm",
        name: str | None = None,
        source_path: str | Path | None = None,
        uuid: str | None = None,
    ) -> "ShaderAsset":
        """Create ShaderAsset from existing ShaderMultyPhaseProgramm."""
        return cls(
            program=program,
            name=name or program.program or "shader",
            source_path=source_path,
            uuid=uuid,
        )
