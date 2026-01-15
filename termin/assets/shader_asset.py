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
        material: Material to update
        program: ShaderMultyPhaseProgramm - new shader program
        shader_name: Shader name
        shader_uuid: Shader asset UUID
    """
    from termin.visualization.core.material import MaterialPhase

    if not program.phases:
        raise ValueError("Program has no phases")

    # Preserve existing uniforms/textures from first phase
    old_uniforms = {}
    old_textures = {}
    old_color = None
    if material.phases:
        old_uniforms = dict(material.phases[0].uniforms)
        old_textures = dict(material.phases[0].textures)
        old_color = material.phases[0].color

    # Rebuild phases (must use list assignment, not append - nanobind returns copy)
    material.shader_name = shader_name or program.program

    phases_list = []
    for shader_phase in program.phases:
        # Generate deterministic UUID for this phase
        phase_uuid = make_phase_uuid(shader_uuid, shader_phase.phase_mark) if shader_uuid else ""

        phase = MaterialPhase.from_shader_phase(
            shader_phase,
            color=old_color,
            textures=None,
            extra_uniforms=None,
            program_name=shader_name or program.program,
            phase_uuid=phase_uuid,
            features=program.features,
        )

        # Restore old textures and uniforms
        for key, val in old_textures.items():
            phase.textures[key] = val
        for key, val in old_uniforms.items():
            phase.uniforms[key] = val

        phases_list.append(phase)

    material.phases = phases_list


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
