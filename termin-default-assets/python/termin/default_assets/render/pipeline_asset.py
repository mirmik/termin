"""Pipeline import boundary and canonical resource ownership.

Both supported authored formats are normalized through the pass-list path.
The asset retains only the stable :class:`TcRenderPipeline` resource and small
dependency metadata; mutable execution instances are created by consumers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tcbase import log
from termin_assets import DataAsset

if TYPE_CHECKING:
    from termin.render_framework import RenderPipeline, TcRenderPipeline


@dataclass(frozen=True)
class _PipelineCandidate:
    """Complete candidate compiled without mutating the live resource."""

    pipeline: "RenderPipeline"
    pass_parameters: tuple[str, ...]
    targets: tuple[dict, ...]
    material_names: frozenset[str]
    external_params: tuple[str, ...]
    resource_views: dict
    fbo_compositions: dict
    source_format: str


def _pass_parameters(pipeline: "RenderPipeline") -> tuple[str, ...]:
    """Serialize parameters in execution-plan order for the resource payload."""
    serialized = pipeline.serialize()
    result: list[str] = []
    for pass_data in serialized.get("passes", []):
        data = pass_data.get("data", {}) if isinstance(pass_data, dict) else {}
        result.append(json.dumps(data, separators=(",", ":"), sort_keys=True))
    return tuple(result)


class PipelineAsset(DataAsset["TcRenderPipeline"]):
    """Strong owner of one stable, versioned canonical render-pipeline resource."""

    _uses_binary = False

    def __init__(
        self,
        data: "RenderPipeline | None" = None,
        name: str = "pipeline",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        from termin.render_framework import TcRenderPipeline

        super().__init__(data=None, name=name, source_path=source_path, uuid=uuid)
        resource = TcRenderPipeline.declare(self.uuid, self._name)
        if not resource.is_valid:
            raise RuntimeError(f"failed to declare canonical pipeline resource '{self._name}'")
        self._data = resource
        self._loaded = False
        self._source_format: str | None = None
        self._material_names: frozenset[str] = frozenset()
        self._external_params: tuple[str, ...] = ()
        self._resource_views: dict = {}
        self._fbo_compositions: dict = {}
        self._resource_manager = None

        if data is not None:
            candidate = self._candidate_from_pipeline(data, source_format="runtime")
            if not self._publish_candidate(candidate):
                raise RuntimeError(f"failed to publish runtime pipeline '{self._name}'")
            self._loaded = True

    @property
    def pipeline(self) -> "RenderPipeline | None":
        """Create a fresh mutable execution instance from the canonical resource."""
        from termin.render_framework import RenderPipeline, apply_pipeline_resource_recipe

        resource = self.canonical_resource
        if resource is None:
            return None
        pipeline = RenderPipeline(resource)
        apply_pipeline_resource_recipe(
            pipeline,
            self._resource_views,
            self._fbo_compositions,
        )
        return pipeline

    @property
    def canonical_resource(self) -> "TcRenderPipeline | None":
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

    def _parse_content(self, content: bytes | str) -> "TcRenderPipeline | None":
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
            pass_list["name"] = str(data.get("name", self._name))
            pass_list["uuid"] = self.uuid
            pass_list["targets"] = [
                {
                    "viewport_name": str(frame.get("viewport_name", "main")),
                    "export_name": str(frame.get("export_name", "")),
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
                resource_views=candidate.resource_views,
                fbo_compositions=candidate.fbo_compositions,
                source_format=candidate.source_format,
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
        from termin.render_framework import RenderPipeline

        passes = data.get("passes")
        if not isinstance(passes, list):
            log.error(f"[PipelineAsset] Pipeline '{self._name}' has a non-list 'passes' field")
            return None
        targets = data.get("targets", [])
        if not isinstance(targets, list) or not all(isinstance(item, dict) for item in targets):
            log.error(f"[PipelineAsset] Pipeline '{self._name}' has invalid target metadata")
            return None
        resource_views = data.get("resource_views", {})
        fbo_compositions = data.get("fbo_compositions", {})
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
            log.error(f"[PipelineAsset] Pipeline '{self._name}' has invalid resource recipe")
            return None
        rm = self._resource_manager or get_resource_manager()
        if rm is None:
            log.error(f"[PipelineAsset] Resource manager is not configured for '{self._name}'")
            return None
        try:
            pipeline = RenderPipeline.deserialize(data, rm)
        except Exception:
            log.error(
                f"[PipelineAsset] Failed to deserialize pass-list pipeline '{self._name}'",
                exc_info=True,
            )
            return None
        if pipeline is None:
            log.error(f"[PipelineAsset] Deserializer returned no pipeline for '{self._name}'")
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
            resource_views=dict(resource_views),
            fbo_compositions=dict(fbo_compositions),
            source_format=source_format,
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
            targets=(),
            material_names=frozenset(material_pass_materials(serialized)),
            external_params=(),
            resource_views=dict(serialized.get("resource_views", {})),
            fbo_compositions=dict(serialized.get("fbo_compositions", {})),
            source_format=source_format,
        )

    def _publish_candidate(self, candidate: _PipelineCandidate) -> bool:
        from termin.render_framework import publish_pipeline_definition

        try:
            publish_pipeline_definition(
                candidate.pipeline,
                self._data,
                list(candidate.pass_parameters),
                list(candidate.targets),
            )
        except Exception:
            log.error(f"[PipelineAsset] Failed to publish pipeline '{self._name}'", exc_info=True)
            return False
        self._source_format = candidate.source_format
        self._material_names = candidate.material_names
        self._external_params = candidate.external_params
        self._resource_views = candidate.resource_views
        self._fbo_compositions = candidate.fbo_compositions
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
        self._resource_views = {}
        self._fbo_compositions = {}

    @classmethod
    def from_pipeline(
        cls,
        pipeline: "RenderPipeline",
        name: str | None = None,
        uuid: str | None = None,
    ) -> "PipelineAsset":
        return cls(data=pipeline, name=name or pipeline.name, uuid=uuid)
