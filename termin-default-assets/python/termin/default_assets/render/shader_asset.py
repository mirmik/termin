"""Shader import boundary and canonical program ownership."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tcbase import log
from termin_assets import DataAsset
from tgfx import TcShaderProgram

if TYPE_CHECKING:
    from termin.materials import ShaderMultyPhaseProgramm


def make_phase_uuid(shader_uuid: str, phase_mark: str) -> str:
    """Return the canonical phase UUID derived by the native program registry."""
    return TcShaderProgram.make_phase_uuid(shader_uuid, phase_mark)


def _feature_flags(features: list[str]) -> int:
    result = 0
    for feature in features:
        if feature == "lighting_ubo":
            result |= 1
    return result


def _property_descriptor(prop) -> dict:
    return {
        "name": prop.name,
        "property_type": prop.property_type,
        "label": prop.label or "",
        "default": prop.default,
        "range_min": prop.range_min,
        "range_max": prop.range_max,
    }


def _phase_descriptor(phase) -> dict:
    from termin.default_assets.render.material_asset import _build_render_state

    state = _build_render_state(phase, phase.phase_mark)
    return {
        "phase_mark": phase.phase_mark,
        "priority": phase.priority,
        "state": {
            "polygon_mode": state.polygon_mode,
            "cull": bool(state.cull),
            "depth_test": bool(state.depth_test),
            "depth_write": bool(state.depth_write),
            "blend": bool(state.blend),
            "blend_src": state.blend_src,
            "blend_dst": state.blend_dst,
            "depth_func": state.depth_func,
        },
    }


def update_material_shader(material, program, shader_name: str, shader_uuid: str) -> None:
    """Rebuild a material from a canonical shader program."""
    from termin.default_assets.render.material_asset import (
        _apply_canonical_property_defaults,
        _apply_canonical_texture_defaults,
        _canonical_render_state,
    )
    from termin_assets import get_resource_manager

    if not program.phases:
        raise ValueError("Program has no phases")

    old_uniforms = dict(material.uniforms)
    old_textures = dict(material.textures)
    material.clear_phases()
    material.shader_name = shader_name or program.name
    material.set_shader_program_dependency(program.uuid, program.version)

    rm = get_resource_manager()
    if rm is None:
        log.error("[update_material_shader] Resource manager is not configured")
        raise RuntimeError("Resource manager is not configured")

    if not program.is_valid or (shader_uuid and program.uuid != shader_uuid):
        log.error(f"[update_material_shader] Invalid shader program: {shader_uuid}")
        raise RuntimeError(f"Invalid shader program: {shader_uuid}")

    available_marks = [item["phase_mark"] for item in program.phases]
    for canonical_phase in program.phases:
        phase = material.add_phase(
            canonical_phase["shader"],
            canonical_phase["phase_mark"],
            canonical_phase["priority"],
        )
        if phase is None:
            log.error("[update_material_shader] Failed to add phase")
            continue
        phase.state = _canonical_render_state(canonical_phase["state"])
        phase.set_available_marks(available_marks)
        _apply_canonical_property_defaults(phase, program.properties, old_uniforms)
        _apply_canonical_texture_defaults(phase, program.properties)
        for key, texture in old_textures.items():
            if key in phase.textures and texture is not None and texture.is_valid:
                phase.set_texture(key, texture)


class ShaderAsset(DataAsset["TcShaderProgram"]):
    """Catalog/import record strongly owning one canonical shader program."""

    _uses_binary = False

    def __init__(
        self,
        program: "ShaderMultyPhaseProgramm | None" = None,
        name: str = "shader",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=None, name=name, source_path=source_path, uuid=uuid)
        resource = TcShaderProgram.declare(self.uuid, self._name)
        if not resource.is_valid:
            raise RuntimeError(f"failed to declare canonical shader program '{self._name}'")
        self._data = resource
        self._loaded = False

        if program is not None:
            if not self.publish_import_ir(program):
                raise RuntimeError(f"failed to publish shader program '{self._name}'")
            self._loaded = True

    @property
    def program(self) -> "TcShaderProgram | None":
        """Canonical program handle; parsed source is never retained by the asset."""
        if not self._loaded and not self._load():
            return None
        return self._data

    @property
    def canonical_resource(self) -> "TcShaderProgram | None":
        return self.program

    def parse_import_ir(self, content: str) -> "ShaderMultyPhaseProgramm | None":
        """Parse a temporary source-domain object without retaining it."""
        from termin.materials import parse_shader_text

        try:
            candidate = parse_shader_text(content)
        except Exception:
            log.error(f"[ShaderAsset] Failed to parse shader '{self._name}'", exc_info=True)
            return None
        if not candidate.phases:
            log.error(f"[ShaderAsset] Shader '{self._name}' has no phases")
            return None
        for phase in candidate.phases:
            if "vertex" not in phase.stages or "fragment" not in phase.stages:
                log.error(
                    f"[ShaderAsset] Phase '{phase.phase_mark}' in '{self._name}' "
                    "has no complete vertex/fragment stage pair"
                )
                return None
        return candidate

    def publish_import_ir(self, candidate: "ShaderMultyPhaseProgramm") -> bool:
        """Publish a complete parsed candidate into the stable native identity."""
        from termin.materials import configure_shader_from_parsed

        properties = [_property_descriptor(prop) for prop in candidate.material_properties]
        phases = [_phase_descriptor(phase) for phase in candidate.phases]
        source_path = str(self._source_path) if self._source_path else candidate.source_path
        try:
            self._data.set_payload(
                name=candidate.program or self._name,
                source_path=source_path,
                language=candidate.language,
                features=_feature_flags(candidate.features),
                properties=properties,
                phases=phases,
            )
            for parsed_phase in candidate.phases:
                published_phase = self._data.find_phase(parsed_phase.phase_mark)
                if published_phase is None:
                    raise RuntimeError(
                        f"published phase is missing: {parsed_phase.phase_mark}"
                    )
                configure_shader_from_parsed(
                    published_phase["shader"],
                    candidate,
                    parsed_phase,
                    f"{candidate.program or self._name}/{parsed_phase.phase_mark}",
                    source_path,
                )
        except Exception:
            log.error(f"[ShaderAsset] Failed to publish shader '{self._name}'", exc_info=True)
            return False
        return True

    def _parse_content(self, content: bytes | str) -> "TcShaderProgram | None":
        if not isinstance(content, str):
            log.error(f"[ShaderAsset] Shader '{self._name}' has non-text content")
            return None
        candidate = self.parse_import_ir(content)
        if candidate is None or not self.publish_import_ir(candidate):
            return None
        return self._data

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "ShaderAsset":
        from termin_assets import read_spec_file

        path = Path(path)
        spec_data = read_spec_file(str(path))
        asset = cls(
            program=None,
            name=name or path.stem,
            source_path=path,
            uuid=spec_data.get("uuid") if spec_data else None,
        )
        asset.parse_spec(spec_data)
        if not asset.ensure_loaded():
            raise RuntimeError(f"failed to load shader asset from '{path}'")
        return asset

    @classmethod
    def from_program(
        cls,
        program: "ShaderMultyPhaseProgramm",
        name: str | None = None,
        source_path: str | Path | None = None,
        uuid: str | None = None,
    ) -> "ShaderAsset":
        return cls(
            program=program,
            name=name or program.program or "shader",
            source_path=source_path,
            uuid=uuid,
        )
