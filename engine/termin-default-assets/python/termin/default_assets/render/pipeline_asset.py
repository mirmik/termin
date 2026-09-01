"""Pipeline import boundary and canonical template ownership.

Both supported authored formats are normalized through the pass-list path.
The asset retains only the stable :class:`TcPipelineTemplate` resource and small
dependency metadata; mutable execution instances are created by consumers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from termin.base import log
from termin_assets import DataAsset

if TYPE_CHECKING:
    from termin.render_framework import RenderPipeline, TcPipelineTemplate


@dataclass(frozen=True)
class _PipelineCandidate:
    """Complete candidate compiled without mutating the live template."""

    pipeline: "RenderPipeline"
    pass_parameters: tuple[str, ...]
    targets: tuple[dict, ...]
    material_names: frozenset[str]
    external_params: tuple[str, ...]
    source_format: str
    execution_model: str


def _pass_parameters(pipeline: "RenderPipeline") -> tuple[str, ...]:
    """Serialize parameters in execution-plan order for the template payload."""
    serialized = pipeline.serialize()
    result: list[str] = []
    for pass_data in serialized.get("passes", []):
        data = pass_data.get("data", {}) if isinstance(pass_data, dict) else {}
        result.append(json.dumps(data, separators=(",", ":"), sort_keys=True))
    return tuple(result)


def _deserialize_pass_list_pipeline(data: dict, resource_manager):
    from termin.render_framework import RenderPipeline

    passes = data.get("passes")
    if not isinstance(passes, list):
        raise ValueError("pipeline has a non-list 'passes' field")
    targets = data.get("targets", [])
    if not isinstance(targets, list) or not all(isinstance(item, dict) for item in targets):
        raise ValueError("pipeline has invalid target metadata")
    resource_views = data.get("resource_views", {})
    fbo_compositions = data.get("fbo_compositions", {})
    execution_model = data.get("execution_model", "single_view")
    if execution_model not in ("single_view", "xr_multiview"):
        raise ValueError(f"pipeline has invalid execution model '{execution_model}'")
    if (
        not isinstance(resource_views, dict)
        or not all(
            isinstance(name, str) and isinstance(item, dict)
            for name, item in resource_views.items()
        )
        or not isinstance(fbo_compositions, dict)
        or not all(
            isinstance(name, str) and isinstance(item, dict)
            for name, item in fbo_compositions.items()
        )
    ):
        raise ValueError("pipeline has an invalid resource recipe")
    pipeline = RenderPipeline.deserialize(data, resource_manager)
    if pipeline is None:
        raise ValueError("pipeline deserializer returned no pipeline")
    return pipeline


def validate_pipeline_document(data: dict, resource_manager=None) -> None:
    """Validate authored pipeline data through the runtime import boundary."""
    if not isinstance(data, dict):
        raise ValueError("pipeline document must be a JSON object")
    has_pass_list = "passes" in data
    has_graph = any(key in data for key in ("nodes", "connections", "viewport_frames"))
    if has_pass_list and has_graph:
        raise ValueError("pipeline document mixes graph and pass-list fields")
    if has_graph:
        from termin.render_framework import compile_graph_from_json

        pipeline = compile_graph_from_json(json.dumps(data))
    elif has_pass_list:
        if resource_manager is None:
            from termin_assets import get_resource_manager

            resource_manager = get_resource_manager()
        if resource_manager is None:
            raise ValueError("pipeline resource manager is not configured")
        pipeline = _deserialize_pass_list_pipeline(data, resource_manager)
    else:
        raise ValueError("pipeline document has no supported authored format")
    pipeline.destroy()


class PipelineAsset(DataAsset["TcPipelineTemplate"]):
    """Strong owner of one stable, versioned canonical pipeline template."""

    _uses_binary = False

    def __init__(
        self,
        data: "RenderPipeline | None" = None,
        name: str = "pipeline",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        from termin.render_framework import TcPipelineTemplate

        super().__init__(data=None, name=name, source_path=source_path, uuid=uuid)
        pipeline_template = TcPipelineTemplate.declare(self.uuid, self._name)
        if not pipeline_template.is_valid:
            raise RuntimeError(f"failed to declare canonical pipeline template '{self._name}'")
        self._data = pipeline_template
        self._loaded = False
        self._source_format: str | None = None
        self._material_names: frozenset[str] = frozenset()
        self._external_params: tuple[str, ...] = ()
        self._resource_manager = None

        if data is not None:
            candidate = self._candidate_from_pipeline(data, source_format="runtime")
            if not self._publish_candidate(candidate):
                raise RuntimeError(f"failed to publish runtime pipeline '{self._name}'")
            self._loaded = True

    @property
    def pipeline(self) -> "RenderPipeline | None":
        """Create a fresh mutable execution instance from the canonical template."""
        from termin.render_framework import RenderPipeline

        pipeline_template = self.canonical_resource
        if pipeline_template is None:
            return None
        return RenderPipeline(pipeline_template)

    @property
    def canonical_resource(self) -> "TcPipelineTemplate | None":
        if not self._loaded and not self._load():
            return None
        return self._data

    @property
    def source_format(self) -> str | None:
        if not self._loaded:
            self._load()
        return self._source_format

    @property
    def is_graph_format(self) -> bool:
        return self.source_format == "graph"

    @property
    def external_params(self) -> list[str]:
        if not self._loaded:
            self._load()
        return list(self._external_params)

    def uses_material_names(self, material_names: set[str]) -> bool:
        if not self._loaded:
            return False
        return bool(self._material_names & material_names)

    def bind_resource_manager(self, resource_manager) -> None:
        """Bind the manager needed to deserialize Python-authored pass data."""
        self._resource_manager = resource_manager

    def _parse_content(self, content: bytes | str) -> "TcPipelineTemplate | None":
        if not isinstance(content, str):
            log.error(f"[PipelineAsset] Pipeline '{self._name}' has non-text content")
            return None
        candidate = self._prepare_candidate(content)
        if candidate is None:
            return None
        try:
            return self._data if self._publish_candidate(candidate) else None
        finally:
            candidate.pipeline.destroy()

    def _prepare_candidate(self, content: str) -> _PipelineCandidate | None:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            log.error(f"[PipelineAsset] Invalid JSON in pipeline '{self._name}'", exc_info=True)
            return None
        if not isinstance(data, dict):
            log.error(f"[PipelineAsset] Pipeline '{self._name}' must contain a JSON object")
            return None

        embedded_uuid = data.get("uuid")
        if embedded_uuid is not None:
            if not isinstance(embedded_uuid, str) or not embedded_uuid:
                log.error(f"[PipelineAsset] Pipeline '{self._name}' has an invalid embedded UUID")
                return None
            if embedded_uuid != self.uuid:
                log.error(
                    f"[PipelineAsset] Refusing to change UUID of registered pipeline "
                    f"'{self._name}' from {self.uuid} to {embedded_uuid}"
                )
                return None

        has_pass_list = "passes" in data
        has_graph = any(key in data for key in ("nodes", "connections", "viewport_frames"))
        if has_pass_list and has_graph:
            log.error(f"[PipelineAsset] Pipeline '{self._name}' mixes graph and pass-list fields")
            return None
        if has_pass_list:
            return self._prepare_pass_list_candidate(data, source_format="pass-list")
        if "nodes" in data:
            return self._prepare_graph_candidate(data)
        log.error(f"[PipelineAsset] Pipeline '{self._name}' has no supported authored format")
        return None

    def _prepare_graph_candidate(self, data: dict) -> _PipelineCandidate | None:
        """Lower graph authoring to a pass list, then use the canonical path."""
        from termin.render_framework import compile_graph_from_json

        graph_pipeline = None
        try:
            graph_pipeline = compile_graph_from_json(json.dumps(data))
            pass_list = graph_pipeline.serialize()
            serialized_targets = {
                str(item.get("viewport_name", "")): item
                for item in pass_list.get("targets", [])
                if isinstance(item, dict)
            }
            pass_list["name"] = str(data.get("name", self._name))
            pass_list["uuid"] = self.uuid
            pass_list["execution_model"] = str(data.get("execution_model", "single_view"))
            pass_list["targets"] = [
                {
                    "viewport_name": str(frame.get("viewport_name", "main")),
                    "export_name": str(
                        frame.get("export_name")
                        or serialized_targets.get(str(frame.get("viewport_name", "main")), {}).get(
                            "export_name", ""
                        )
                    ),
                    "color_content": str(
                        serialized_targets.get(str(frame.get("viewport_name", "main")), {}).get(
                            "color_content", "display_linear"
                        )
                    ),
                    "width": int(frame.get("target_width", 0)),
                    "height": int(frame.get("target_height", 0)),
                }
                for frame in data.get("viewport_frames", [])
                if isinstance(frame, dict)
            ]
            candidate = self._prepare_pass_list_candidate(pass_list, source_format="graph")
            if candidate is None:
                return None
            external_params = tuple(
                str(node.get("params", {}).get("slot") or node.get("name") or "unnamed")
                for node in data.get("nodes", [])
                if isinstance(node, dict)
                and node.get("node_type") == "external_rt"
                and isinstance(node.get("params", {}), dict)
            )
            return _PipelineCandidate(
                pipeline=candidate.pipeline,
                pass_parameters=candidate.pass_parameters,
                targets=candidate.targets,
                material_names=candidate.material_names,
                external_params=external_params,
                source_format=candidate.source_format,
                execution_model=candidate.execution_model,
            )
        except Exception:
            log.error(f"[PipelineAsset] Failed to lower graph pipeline '{self._name}'", exc_info=True)
            return None
        finally:
            if graph_pipeline is not None:
                graph_pipeline.destroy()

    def _prepare_pass_list_candidate(
        self,
        data: dict,
        *,
        source_format: str,
    ) -> _PipelineCandidate | None:
        from termin_assets import get_resource_manager
        from termin.default_assets.render.pipeline_dependencies import material_pass_materials
        targets = data.get("targets", [])
        execution_model = data.get("execution_model", "single_view")
        rm = self._resource_manager or get_resource_manager()
        if rm is None:
            log.error(f"[PipelineAsset] Resource manager is not configured for '{self._name}'")
            return None
        try:
            pipeline = _deserialize_pass_list_pipeline(data, rm)
        except Exception:
            log.error(
                f"[PipelineAsset] Failed to deserialize pass-list pipeline '{self._name}'",
                exc_info=True,
            )
            return None
        pipeline.name = self._name
        external_params = tuple(
            str(item.get("resource"))
            for item in data.get("pipeline_specs", [])
            if isinstance(item, dict)
            and str(item.get("resource_type", "")).startswith("external")
            and item.get("resource")
        )
        return _PipelineCandidate(
            pipeline=pipeline,
            pass_parameters=_pass_parameters(pipeline),
            targets=tuple(dict(item) for item in targets),
            material_names=frozenset(material_pass_materials(data)),
            external_params=external_params,
            source_format=source_format,
            execution_model=execution_model,
        )

    def _candidate_from_pipeline(
        self,
        pipeline: "RenderPipeline",
        *,
        source_format: str,
    ) -> _PipelineCandidate:
        serialized = pipeline.serialize()
        from termin.default_assets.render.pipeline_dependencies import material_pass_materials

        return _PipelineCandidate(
            pipeline=pipeline,
            pass_parameters=_pass_parameters(pipeline),
            targets=tuple(dict(item) for item in serialized.get("targets", [])),
            material_names=frozenset(material_pass_materials(serialized)),
            external_params=(),
            source_format=source_format,
            execution_model="single_view",
        )

    def _publish_candidate(self, candidate: _PipelineCandidate) -> bool:
        from termin.render_framework import publish_pipeline_template

        try:
            publish_pipeline_template(
                candidate.pipeline,
                self._data,
                list(candidate.pass_parameters),
                list(candidate.targets),
                candidate.execution_model,
            )
        except Exception:
            log.error(f"[PipelineAsset] Failed to publish pipeline '{self._name}'", exc_info=True)
            return False
        self._source_format = candidate.source_format
        self._material_names = candidate.material_names
        self._external_params = candidate.external_params
        return True

    def _load_content(self, content: bytes | str) -> bool:
        if not isinstance(content, str):
            log.error(f"[PipelineAsset] Pipeline '{self._name}' has non-text content")
            return False
        candidate = self._prepare_candidate(content)
        if candidate is None:
            return False
        try:
            previous_loaded = self._loaded
            self._loaded = True
            try:
                self._on_loaded()
            except Exception:
                self._loaded = previous_loaded
                raise
            if not self._publish_candidate(candidate):
                self._loaded = previous_loaded
                return False
        except Exception:
            log.error(f"[PipelineAsset] Post-load hook failed for '{self._name}'", exc_info=True)
            return False
        finally:
            candidate.pipeline.destroy()
        if not self._has_uuid_in_spec and self._source_path:
            self.save_spec_file()
        return True

    def reload(self) -> bool:
        if self._source_path is None:
            return False
        result = self._load_from_file()
        if result:
            self._bump_version()
        return result

    def unload(self) -> None:
        """Keep the declared strong resource handle while discarding load state."""
        self._loaded = False
        self._source_format = None
        self._material_names = frozenset()
        self._external_params = ()

    @classmethod
    def from_pipeline(
        cls,
        pipeline: "RenderPipeline",
        name: str | None = None,
        uuid: str | None = None,
    ) -> "PipelineAsset":
        return cls(data=pipeline, name=name or pipeline.name, uuid=uuid)
