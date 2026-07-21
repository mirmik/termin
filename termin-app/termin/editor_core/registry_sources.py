"""Production registry catalog sources shared by editor frontends."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from termin.editor_core.registry_viewer_model import (
    RegistryColumn,
    RegistryPage,
    RegistryRow,
)


def _memory_size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


def _mapping_details(title: str, info: Mapping[str, Any]) -> str:
    lines = [title, ""]
    for key in sorted(info):
        value = info[key]
        if isinstance(value, (list, tuple)):
            lines.append(f"{key}: {len(value)}")
            lines.extend(f"  - {item}" for item in value)
        elif isinstance(value, dict):
            lines.append(f"{key}: {len(value)}")
            lines.extend(f"  {nested_key}: {value[nested_key]}" for nested_key in sorted(value))
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


class MappingRegistrySource:
    def __init__(
        self,
        loader: Callable[[], Iterable[Mapping[str, Any]]],
        row_builder: Callable[[Mapping[str, Any]], RegistryRow],
    ) -> None:
        self._loader = loader
        self._row_builder = row_builder

    def load_rows(self) -> Iterable[RegistryRow]:
        return (self._row_builder(info) for info in self._loader())


def _mapping_row(
    info: Mapping[str, Any],
    stable_key: str,
    cells: tuple[str, ...],
    title: str,
) -> RegistryRow:
    stable_id = str(info.get(stable_key, ""))
    return RegistryRow(stable_id, cells, _mapping_details(f"{title}: {stable_id}", info))


class SceneRegistrySource:
    """Hierarchical adapter over the public engine scene registry diagnostics."""

    def load_rows(self) -> Iterable[RegistryRow]:
        from termin.engine import scene as engine_scene

        rows: list[RegistryRow] = []
        for scene_info in engine_scene.tc_scene_registry_get_all_info():
            handle = scene_info.get("handle")
            if handle is None:
                continue
            scene_id = f"scene:{handle[0]}:{handle[1]}"
            scene_name = str(scene_info.get("name") or "<unnamed scene>")
            entities = engine_scene.tc_scene_get_entities(handle)
            component_types = engine_scene.tc_scene_get_component_types(handle)
            scene_details = [
                f"Scene: {scene_name}",
                "",
                f"Handle: {handle[0]}:{handle[1]}",
                f"Entities: {scene_info.get('entity_count', 0)}",
                f"Loaded entities: {len(entities)}",
                f"Pending: {scene_info.get('pending_count', 0)}",
                f"Update components: {scene_info.get('update_count', 0)}",
                f"Fixed-update components: {scene_info.get('fixed_update_count', 0)}",
                "",
                "Component Types",
            ]
            scene_details.extend(
                f"  {component.get('type_name', '?')}: {component.get('count', 0)}" for component in component_types
            )
            rows.append(
                RegistryRow(
                    scene_id,
                    (scene_name, f"{len(entities)} entities"),
                    "\n".join(scene_details),
                )
            )
            entity_ids = {
                (entity.get("id_index"), entity.get("id_generation")): (
                    f"{scene_id}/entity:{entity.get('id_index')}:{entity.get('id_generation')}"
                )
                for entity in entities
            }
            for entity in sorted(
                entities,
                key=lambda item: (
                    int(item.get("pick_id", 0)),
                    str(item.get("name") or item.get("uuid") or ""),
                    int(item.get("id_index", 0)),
                ),
            ):
                entity_id = entity_ids[(entity.get("id_index"), entity.get("id_generation"))]
                parent_key = (entity.get("parent_index"), entity.get("parent_generation"))
                parent_id = entity_ids.get(parent_key, scene_id)
                components = entity.get("components", [])
                entity_name = str(entity.get("name") or "(unnamed)")
                details = [
                    f"Entity: {entity_name}",
                    "",
                    f"UUID: {entity.get('uuid', '')}",
                    f"Entity ID: {entity.get('id_index', '?')}:{entity.get('id_generation', '?')}",
                    f"Runtime ID: {entity.get('runtime_id', 0)}",
                    f"Pick ID: {entity.get('pick_id', 0)}",
                    f"Enabled: {entity.get('enabled', True)}",
                    f"Visible: {entity.get('visible', True)}",
                    f"Pickable: {entity.get('pickable', True)}",
                    f"Selectable: {entity.get('selectable', True)}",
                    f"Priority: {entity.get('priority', 0)}",
                    f"Layer: {entity.get('layer', 0)}",
                    f"Children: {entity.get('children_count', 0)}",
                    "",
                    f"Components: {len(components)}",
                ]
                for component in components:
                    details.extend(
                        (
                            f"  {component.get('type_name', '<unknown>')}",
                            f"    enabled: {component.get('enabled', False)}",
                            f"    active_in_editor: {component.get('active_in_editor', False)}",
                            f"    started: {component.get('started', False)}",
                        )
                    )
                rows.append(
                    RegistryRow(
                        entity_id,
                        (entity_name, f"{len(components)} components"),
                        "\n".join(details),
                        parent_id=parent_id,
                    )
                )
        return rows


class NavMeshRegistrySource:
    """Hierarchical public adapter for per-scene runtime NavMesh registries."""

    def load_rows(self) -> Iterable[RegistryRow]:
        from termin.navmesh.registry import NavMeshRegistry

        rows: list[RegistryRow] = []
        for scene_uuid, registry in NavMeshRegistry.instances():
            agent_types = sorted(registry.list_agent_types())
            if not agent_types:
                continue
            scene_id = f"navmesh-scene/{scene_uuid}"
            rows.append(
                RegistryRow(
                    scene_id,
                    (f"Scene: {scene_uuid}", f"{len(agent_types)} agent types"),
                    f"Scene UUID: {scene_uuid}\nAgent types: {len(agent_types)}",
                )
            )
            for agent_type in agent_types:
                entries = registry.get_all(agent_type)
                agent_id = f"{scene_id}/agent/{agent_type}"
                polygons = sum(navmesh.polygon_count() for navmesh, _entity in entries)
                triangles = sum(navmesh.triangle_count() for navmesh, _entity in entries)
                vertices = sum(navmesh.vertex_count() for navmesh, _entity in entries)
                rows.append(
                    RegistryRow(
                        agent_id,
                        (agent_type, f"{len(entries)} sources, {polygons} polygons"),
                        "\n".join(
                            (
                                f"Agent Type: {agent_type}",
                                "",
                                f"Sources: {len(entries)}",
                                f"Polygons: {polygons}",
                                f"Triangles: {triangles}",
                                f"Vertices: {vertices}",
                            )
                        ),
                        parent_id=scene_id,
                    )
                )
                for navmesh, entity in entries:
                    entity_name = entity.name if entity is not None else "(no entity)"
                    entity_uuid = entity.uuid if entity is not None else "none"
                    navmesh_id = f"{agent_id}/source/{entity_uuid}"
                    details = [
                        f"NavMesh: {navmesh.name}",
                        "",
                        f"Source entity: {entity_name}",
                        f"Source UUID: {entity_uuid}",
                        f"Polygons: {navmesh.polygon_count()}",
                        f"Triangles: {navmesh.triangle_count()}",
                        f"Vertices: {navmesh.vertex_count()}",
                        f"Cell size: {navmesh.cell_size}",
                        f"Origin: {navmesh.origin}",
                    ]
                    rows.append(
                        RegistryRow(
                            navmesh_id,
                            (entity_name, f"{navmesh.polygon_count()} polygons"),
                            "\n".join(details),
                            parent_id=agent_id,
                        )
                    )
        return rows


def build_core_registry_pages() -> tuple[RegistryPage, ...]:
    """Build adapters over the public C++ core registry inspection APIs."""
    from tcbase import intern_string_get_all_info
    from termin.materials import tc_material_get_all_info
    from termin.gui_native import tc_ui_document_registry_get_all_info
    from termin.render_framework import (
        tc_pass_registry_get_all_types,
        tc_pipeline_registry_get_all_info,
    )
    from termin.scene._scene_native import component_registry_get_all_info, soa_registry_get_all_info
    from tgfx import shader_get_all_info, tc_texture_get_all_info
    from tmesh import tc_mesh_get_all_info

    pages = (
        RegistryPage(
            "meshes",
            "Meshes",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("vertices", "Vertices", 84.0),
                RegistryColumn("triangles", "Triangles", 84.0),
                RegistryColumn("memory", "Memory", 88.0),
            ),
            MappingRegistrySource(
                tc_mesh_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "name",
                    (
                        str(info.get("name", "")),
                        str(info.get("vertex_count", 0)),
                        str(info.get("index_count", 0)),
                        _memory_size(int(info.get("memory_bytes", 0))),
                    ),
                    "Mesh",
                ),
            ),
        ),
        RegistryPage(
            "textures",
            "Textures",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("size", "Size", 90.0),
                RegistryColumn("channels", "Channels", 80.0),
                RegistryColumn("memory", "Memory", 88.0),
            ),
            MappingRegistrySource(
                tc_texture_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "name",
                    (
                        str(info.get("name", "")),
                        f"{info.get('width', 0)}x{info.get('height', 0)}",
                        str(info.get("channels", 0)),
                        _memory_size(int(info.get("memory_bytes", 0))),
                    ),
                    "Texture",
                ),
            ),
        ),
        RegistryPage(
            "shaders",
            "Shaders",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("type", "Type", 96.0),
                RegistryColumn("version", "Version", 72.0),
                RegistryColumn("size", "Size", 80.0),
            ),
            MappingRegistrySource(
                shader_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "name",
                    (
                        str(info.get("name", "")),
                        "variant" if info.get("is_variant") else "standard",
                        str(info.get("version", 0)),
                        str(info.get("source_size", 0)),
                    ),
                    "Shader",
                ),
            ),
        ),
        RegistryPage(
            "materials",
            "Materials",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("phases", "Phases", 72.0),
                RegistryColumn("textures", "Textures", 76.0),
                RegistryColumn("version", "Version", 72.0),
            ),
            MappingRegistrySource(
                tc_material_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "name",
                    (
                        str(info.get("name", "")),
                        str(info.get("phase_count", 0)),
                        str(info.get("texture_count", 0)),
                        str(info.get("version", 0)),
                    ),
                    "Material",
                ),
            ),
        ),
        RegistryPage(
            "components",
            "Components",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("language", "Language", 84.0),
                RegistryColumn("drawable", "Drawable", 80.0),
                RegistryColumn("parent", "Parent", stretch=1.0),
                RegistryColumn("descendants", "Children", 76.0),
            ),
            MappingRegistrySource(
                component_registry_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "name",
                    (
                        str(info.get("name", "")),
                        str(info.get("language", "?")),
                        "yes" if info.get("is_drawable") else "",
                        str(info.get("parent", "")),
                        str(len(info.get("descendants", []))),
                    ),
                    "Component",
                ),
            ),
        ),
        RegistryPage(
            "soa-types",
            "SoA Types",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("id", "ID", 60.0),
                RegistryColumn("size", "Size", 64.0),
                RegistryColumn("align", "Align", 64.0),
                RegistryColumn("init", "Init", 56.0),
                RegistryColumn("destroy", "Destroy", 70.0),
            ),
            MappingRegistrySource(
                soa_registry_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "name",
                    (
                        str(info.get("name", "")),
                        str(info.get("id", "?")),
                        str(info.get("element_size", 0)),
                        str(info.get("alignment", 0)),
                        "yes" if info.get("has_init") else "",
                        "yes" if info.get("has_destroy") else "",
                    ),
                    "SoA Type",
                ),
            ),
        ),
        RegistryPage(
            "pipelines",
            "Pipelines",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("passes", "Passes", 80.0),
            ),
            MappingRegistrySource(
                tc_pipeline_registry_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "name",
                    (str(info.get("name", "")), str(info.get("pass_count", 0))),
                    "Pipeline",
                ),
            ),
        ),
        RegistryPage(
            "ui-documents",
            "UI Documents",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("handle", "Handle", 96.0),
                RegistryColumn("widgets", "Widgets", 72.0),
                RegistryColumn("roots", "Roots", 64.0),
                RegistryColumn("overlays", "Overlays", 72.0),
            ),
            MappingRegistrySource(
                tc_ui_document_registry_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "handle",
                    (
                        str(info.get("name", "")),
                        ":".join(str(part) for part in info.get("handle", ())),
                        str(info.get("live_widget_count", 0)),
                        str(info.get("root_count", 0)),
                        str(info.get("overlay_count", 0)),
                    ),
                    "UI Document",
                ),
            ),
        ),
        RegistryPage(
            "passes",
            "Passes",
            (
                RegistryColumn("type", "Type Name", stretch=2.0),
                RegistryColumn("language", "Language", 90.0),
            ),
            MappingRegistrySource(
                tc_pass_registry_get_all_types,
                lambda info: _mapping_row(
                    info,
                    "type_name",
                    (str(info.get("type_name", "")), str(info.get("language", "?"))),
                    "Pass Type",
                ),
            ),
        ),
        RegistryPage(
            "intern-strings",
            "Intern Strings",
            (
                RegistryColumn("string", "String", stretch=2.0),
                RegistryColumn("bucket", "Bucket", 80.0),
                RegistryColumn("depth", "Chain Pos", 88.0),
            ),
            MappingRegistrySource(
                intern_string_get_all_info,
                lambda info: _mapping_row(
                    info,
                    "string",
                    (
                        str(info.get("string", "")),
                        str(info.get("bucket", 0)),
                        str(info.get("depth", 0)),
                    ),
                    "Intern String",
                ),
            ),
        ),
    )
    return pages + (
        RegistryPage(
            "scenes",
            "Scenes",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("summary", "Summary", stretch=1.0),
            ),
            SceneRegistrySource(),
            hierarchical=True,
        ),
        RegistryPage(
            "navmesh",
            "NavMesh",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("summary", "Summary", stretch=1.0),
            ),
            NavMeshRegistrySource(),
            hierarchical=True,
        ),
    )


class ResourceAssetSource:
    def __init__(self, resource_manager, type_id: str) -> None:
        self._resource_manager = resource_manager
        self._type_id = type_id

    def load_rows(self) -> Iterable[RegistryRow]:
        assets = sorted(
            self._resource_manager.iter_runtime_assets(self._type_id),
            key=lambda asset: (asset.name.casefold(), asset.uuid),
        )
        name_counts: dict[str, int] = {}
        for asset in assets:
            name_counts[asset.name] = name_counts.get(asset.name, 0) + 1
        for asset in assets:
            name = asset.name
            source = asset.source_path or ""
            label = name
            if name_counts[name] > 1:
                label = f"{name} — {source or str(asset.uuid)[:8]}"
            details = "\n".join(
                (
                    f"{self._type_id}: {name}",
                    "",
                    f"UUID: {asset.uuid}",
                    f"Source: {source or '(unknown)'}",
                    f"Loaded: {asset.is_loaded}",
                    f"Version: {asset.version}",
                )
            )
            yield RegistryRow(
                str(asset.uuid),
                (
                    label,
                    "loaded" if asset.is_loaded else "not loaded",
                    str(asset.version),
                    str(asset.uuid)[:16],
                ),
                details,
            )

    def activate(self, row: RegistryRow) -> None:
        asset = self._resource_manager.get_runtime_asset_by_uuid(self._type_id, row.stable_id)
        if asset is None:
            raise LookupError(f"{self._type_id} asset '{row.stable_id}' no longer exists")
        if not asset.is_loaded:
            asset.ensure_loaded()


class ResourceComponentSource:
    def __init__(self, resource_manager) -> None:
        self._resource_manager = resource_manager

    def load_rows(self) -> Iterable[RegistryRow]:
        for name in sorted(self._resource_manager.list_component_names()):
            component_class = self._resource_manager.get_component(name)
            if component_class is None:
                continue
            module = component_class.__module__
            details = "\n".join(
                (
                    f"Component: {name}",
                    "",
                    f"Module: {module}",
                    f"Class: {component_class.__qualname__}",
                    f"MRO: {' -> '.join(cls.__name__ for cls in component_class.__mro__)}",
                )
            )
            yield RegistryRow(name, (name, module), details)


class WatchedFileSource:
    def __init__(self, watcher) -> None:
        self._watcher = watcher

    def load_rows(self) -> Iterable[RegistryRow]:
        watcher = self._watcher
        project = watcher.project_path or "(none)"
        watched_dirs = sorted(watcher.watched_dirs)
        processors = sorted(watcher.get_all_processors(), key=lambda item: item.resource_type)
        rows = [
            RegistryRow(
                "watcher",
                ("Project Watcher", "enabled" if watcher.is_enabled else "disabled"),
                "\n".join(
                    (
                        "Project File Watcher",
                        "",
                        f"State: {'enabled' if watcher.is_enabled else 'disabled'}",
                        f"Project: {project}",
                        f"Watched directories: {len(watched_dirs)}",
                        f"Watched resource files: {watcher.get_file_count()}",
                        f"Known project files: {watcher.get_all_files_count()}",
                        f"Processors: {len(processors)}",
                    )
                ),
            ),
            RegistryRow(
                "watcher/extensions",
                ("By Extension", f"{watcher.get_all_files_count()} files"),
                "Project file counts grouped by extension.",
                parent_id="watcher",
            ),
            RegistryRow(
                "watcher/directories",
                ("Directories", f"{len(watched_dirs)} watched"),
                "Directories covered by the recursive project watcher.",
                parent_id="watcher",
            ),
            RegistryRow(
                "watcher/processors",
                ("Processors", f"{len(processors)} registered"),
                "Registered file processors and their tracked resources.",
                parent_id="watcher",
            ),
        ]
        for extension, count in watcher.get_all_files_by_extension().items():
            rows.append(
                RegistryRow(
                    f"watcher/extensions/{extension}",
                    (extension, f"{count} files"),
                    f"Extension: {extension}\nFiles: {count}",
                    parent_id="watcher/extensions",
                )
            )
        for path in watched_dirs:
            rows.append(
                RegistryRow(
                    f"watcher/directories/{path}",
                    (path, "directory"),
                    f"Watched directory: {path}",
                    parent_id="watcher/directories",
                )
            )
        for processor in processors:
            processor_id = f"watcher/processors/{processor.resource_type}"
            tracked = processor.get_tracked_files()
            rows.append(
                RegistryRow(
                    processor_id,
                    (processor.resource_type, f"{len(tracked)} files"),
                    "\n".join(
                        (
                            f"Processor: {processor.resource_type}",
                            f"Extensions: {', '.join(sorted(processor.extensions))}",
                            f"Tracked files: {len(tracked)}",
                        )
                    ),
                    parent_id="watcher/processors",
                )
            )
            for path, resource_names in sorted(tracked.items()):
                resources = ", ".join(sorted(resource_names)) if resource_names else "(pending)"
                rows.append(
                    RegistryRow(
                        f"{processor_id}/{path}",
                        (path, resources),
                        "\n".join(
                            (
                                f"File: {path}",
                                f"Processor: {processor.resource_type}",
                                f"Resources: {resources}",
                            )
                        ),
                        parent_id=processor_id,
                    )
                )
        return rows


def build_resource_manager_pages(resource_manager, project_file_watcher=None) -> tuple[RegistryPage, ...]:
    asset_columns = (
        RegistryColumn("name", "Name", stretch=2.0),
        RegistryColumn("status", "Status", 92.0),
        RegistryColumn("version", "Ver", 56.0),
        RegistryColumn("uuid", "UUID", 150.0),
    )
    pages = []
    for type_id, label in (
        ("material", "Materials"),
        ("shader", "Shaders"),
        ("mesh", "Meshes"),
        ("texture", "Textures"),
        ("voxel_grid", "Voxel Grids"),
        ("navmesh", "NavMeshes"),
        ("skeleton", "Skeletons"),
        ("pipeline", "Pipelines"),
    ):
        source = ResourceAssetSource(resource_manager, type_id)
        pages.append(
            RegistryPage(
                type_id,
                label,
                asset_columns,
                source,
                activate=source.activate,
            )
        )
    pages.append(
        RegistryPage(
            "components",
            "Components",
            (
                RegistryColumn("name", "Name", stretch=2.0),
                RegistryColumn("module", "Module", stretch=2.0),
            ),
            ResourceComponentSource(resource_manager),
        )
    )
    if project_file_watcher is not None:
        pages.append(
            RegistryPage(
                "watched-files",
                "Watched Files",
                (
                    RegistryColumn("name", "Name", stretch=2.0),
                    RegistryColumn("summary", "Summary", stretch=1.0),
                ),
                WatchedFileSource(project_file_watcher),
                hierarchical=True,
            )
        )
    return tuple(pages)


__all__ = [
    "MappingRegistrySource",
    "NavMeshRegistrySource",
    "ResourceAssetSource",
    "ResourceComponentSource",
    "SceneRegistrySource",
    "WatchedFileSource",
    "build_core_registry_pages",
    "build_resource_manager_pages",
]
