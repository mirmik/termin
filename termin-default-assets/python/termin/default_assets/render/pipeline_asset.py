"""Pipeline asset loading and transactional hot reload.

Pipeline documents use their UUID as stable external identity.  The import
plugin establishes that identity before this asset is registered; loading must
therefore never rewrite it from the document contents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tcbase import log
from termin_assets import DataAsset

if TYPE_CHECKING:
    from termin.render_framework import RenderPipeline


@dataclass(frozen=True)
class _PipelineCandidate:
    """Fully parsed pipeline state, ready to atomically replace the live one."""

    pipeline: "RenderPipeline"
    graph_data: dict | None


class PipelineAsset(DataAsset["RenderPipeline"]):
    """
    Asset for render pipelines (.pipeline files).

    IMPORTANT: Create through ResourceManager, not directly.

    Example:
        rm = ResourceManager.instance()
        pipeline = rm.get_pipeline("my_pipeline")
        asset = rm.get_pipeline_asset("my_pipeline")
    """

    _uses_binary = False  # JSON text files

    def __init__(
        self,
        data: "RenderPipeline | None" = None,
        name: str = "pipeline",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize PipelineAsset.

        Args:
            data: RenderPipeline instance (can be None for lazy loading)
            name: Pipeline name
            source_path: Path to .pipeline file
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(data=data, name=name, source_path=source_path, uuid=uuid)

        self._graph_data: dict | None = None

    @property
    def pipeline(self) -> "RenderPipeline | None":
        """Get the render pipeline (lazy-loaded)."""
        return self.data

    @property
    def graph_data(self) -> dict | None:
        """Raw graph data (nodes, connections) for graph-format pipelines."""
        if not self._loaded:
            self._load()
        return self._graph_data

    @property
    def is_graph_format(self) -> bool:
        """True if this pipeline uses the graph format (nodes, connections)."""
        if not self._loaded:
            self._load()
        return self._graph_data is not None

    @property
    def external_params(self) -> list[str]:
        """List of external RT slot names defined in the pipeline graph."""
        if not self._loaded:
            self._load()
        if self._graph_data is None:
            return []
        result: list[str] = []
        for node in self._graph_data.get("nodes", []):
            if node.get("node_type") == "external_rt":
                slot = node.get("params", {}).get("slot", "")
                name = node.get("name", "")
                result.append(slot or name or "unnamed")
        return result

    def uses_material_names(self, material_names: set[str]) -> bool:
        """True if this pipeline graph references any of material_names."""
        if not self._loaded:
            return False
        from termin.default_assets.render.pipeline_dependencies import uses_material_names

        return uses_material_names(self._graph_data, material_names)

    def _parse_content(self, content: bytes | str) -> "RenderPipeline | None":
        """Parse without modifying live state (required by :class:`DataAsset`)."""
        if not isinstance(content, str):
            log.error(f"[PipelineAsset] Pipeline '{self._name}' has non-text content")
            return None
        candidate = self._prepare_candidate(content)
        return candidate.pipeline if candidate is not None else None

    def _prepare_candidate(self, content: str) -> _PipelineCandidate | None:
        """Compile a candidate pipeline while preserving the registered identity."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            log.error(
                f"[PipelineAsset] Invalid JSON in pipeline '{self._name}'",
                exc_info=True,
            )
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

        if "nodes" in data and "passes" not in data:
            return self._prepare_graph_candidate(data)
        return self._prepare_pass_list_candidate(data)

    def _prepare_graph_candidate(self, data: dict) -> _PipelineCandidate | None:
        """Compile graph JSON without registering or mutating a global template."""
        from termin.render_framework import compile_graph_from_json

        try:
            pipeline = compile_graph_from_json(json.dumps(data))
        except Exception:
            log.error(
                f"[PipelineAsset] Failed to compile graph pipeline '{self._name}'",
                exc_info=True,
            )
            return None

        if pipeline is None:
            log.error(f"[PipelineAsset] Graph compiler returned no pipeline for '{self._name}'")
            return None
        pipeline.name = self._name
        return _PipelineCandidate(pipeline=pipeline, graph_data=data)

    def _prepare_pass_list_candidate(self, data: dict) -> _PipelineCandidate | None:
        """Deserialize a legacy pass-list document without modifying live state."""
        from termin_assets import get_resource_manager
        from termin.render_framework import RenderPipeline

        rm = get_resource_manager()
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
        return _PipelineCandidate(pipeline=pipeline, graph_data=None)

    def _load_content(self, content: bytes | str) -> bool:
        """Atomically replace cached pipeline state after a successful parse."""
        if not isinstance(content, str):
            log.error(f"[PipelineAsset] Pipeline '{self._name}' has non-text content")
            return False

        candidate = self._prepare_candidate(content)
        if candidate is None:
            return False

        previous_data = self._data
        previous_graph_data = self._graph_data
        previous_loaded = self._loaded
        self._data = candidate.pipeline
        self._graph_data = candidate.graph_data
        self._loaded = True
        try:
            self._on_loaded()
        except Exception:
            self._data = previous_data
            self._graph_data = previous_graph_data
            self._loaded = previous_loaded
            log.error(f"[PipelineAsset] Post-load hook failed for '{self._name}'", exc_info=True)
            return False

        if not self._has_uuid_in_spec and self._source_path:
            self.save_spec_file()
        return True

    def reload(self) -> bool:
        """Reload the asset and rebind live render targets using this pipeline."""
        if self._source_path is None:
            return False
        result = self._load_from_file()
        if result:
            self._bump_version()
            self._notify_rendering_manager_reloaded()
        return result

    def _notify_rendering_manager_reloaded(self) -> None:
        try:
            from termin.engine import RenderingManager
        except Exception as e:
            log.debug(
                f"[PipelineAsset] RenderingManager is not available; "
                f"skipping live pipeline rebind for '{self._name}': {e}"
            )
            return

        try:
            rebound = RenderingManager.instance().recreate_render_target_pipelines_for_asset(
                self._name,
                self.uuid,
            )
            if rebound:
                log.info(
                    f"[PipelineAsset] Rebound {rebound} render target(s) "
                    f"after reloading pipeline '{self._name}'"
                )
        except Exception:
            log.error(
                f"[PipelineAsset] Failed to rebind render targets for pipeline '{self._name}'",
                exc_info=True,
            )

    def save_graph_to_file(self, path: Path | str | None = None) -> bool:
        """Save graph data to .pipeline file.

        Args:
            path: Target path. If None, uses source_path.

        Returns:
            True on success, False on failure.
        """
        target = Path(path) if path else self._source_path
        if target is None:
            log.error("[PipelineAsset] No path specified for save")
            return False

        if self._graph_data is None:
            log.error("[PipelineAsset] No graph data to save")
            return False

        try:
            save_data = dict(self._graph_data)
            save_data["uuid"] = self.uuid

            with open(target, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)

            self._source_path = target
            self.mark_just_saved()

            return True

        except Exception as e:
            log.error(f"[PipelineAsset] Failed to save: {e}")
            return False

    @classmethod
    def from_pipeline(
        cls,
        pipeline: "RenderPipeline",
        name: str | None = None,
        uuid: str | None = None,
    ) -> "PipelineAsset":
        """
        Create PipelineAsset from existing RenderPipeline.

        Args:
            pipeline: RenderPipeline instance
            name: Asset name (defaults to pipeline.name)
            uuid: Optional fixed UUID

        Returns:
            PipelineAsset wrapping the pipeline
        """
        return cls(
            data=pipeline,
            name=name or pipeline.name,
            uuid=uuid,
        )
