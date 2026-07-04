"""Core Registry Viewer - shows internal core registry state."""

from __future__ import annotations

from tcgui.widgets.label import Label
from tcgui.widgets.table_widget import TableColumn
from tcgui.widgets.tree import TreeNode, TreeWidget

from termin.editor_tcgui.dialogs.registry_viewer_dialog import RegistryViewerDialog
from tcbase import log


def show_core_registry_viewer(ui) -> None:
    """Show Core Registry viewer dialog."""
    try:
        from tmesh import tc_mesh_get_all_info, tc_mesh_count
        from tgfx import tc_texture_get_all_info, tc_texture_count
        from tgfx import TcShader, shader_get_all_info, shader_count
        from termin.materials import (
            tc_material_get_all_info,
            tc_material_count,
            TcMaterial,
        )
        from termin.render_framework import (
            tc_pipeline_registry_get_all_info,
            tc_pass_registry_get_all_instance_info,
            tc_pass_registry_get_all_types,
        )
        from termin.scene._scene_native import (
            component_registry_get_all_info,
            component_registry_type_count,
            soa_registry_get_all_info,
        )
        from termin.engine import scene as engine_scene
        tc_scene_registry_get_all_info = engine_scene.tc_scene_registry_get_all_info
        tc_scene_get_entities = engine_scene.tc_scene_get_entities
        tc_scene_get_component_types = engine_scene.tc_scene_get_component_types
    except ImportError as e:
        log.error(f"Core registry APIs not available: {e}")
        return

    tab_columns = {
        "Meshes": [
            TableColumn("Name"),
            TableColumn("Vertices", 80),
            TableColumn("Triangles", 80),
            TableColumn("Memory", 80),
        ],
        "Textures": [
            TableColumn("Name"),
            TableColumn("Size", 80),
            TableColumn("Channels", 80),
            TableColumn("Memory", 80),
        ],
        "Shaders": [
            TableColumn("Name"),
            TableColumn("Type", 80),
            TableColumn("Version", 70),
            TableColumn("Size", 80),
        ],
        "Materials": [
            TableColumn("Name"),
            TableColumn("Phases", 70),
            TableColumn("Textures", 70),
            TableColumn("Version", 70),
        ],
        "Components": [
            TableColumn("Name"),
            TableColumn("Language", 80),
            TableColumn("Drawable", 70),
            TableColumn("Parent"),
            TableColumn("Descendants", 80),
        ],
        "SoA Types": [
            TableColumn("Name"),
            TableColumn("ID", 60),
            TableColumn("Size", 60),
            TableColumn("Align", 60),
            TableColumn("Init", 50),
            TableColumn("Destroy", 60),
        ],
        "Pipelines": [TableColumn("Name"), TableColumn("Pass Count", 80)],
        "Passes": [TableColumn("Type Name"), TableColumn("Language", 80)],
    }

    viewer = RegistryViewerDialog("Core Registry", tab_columns)
    tab_lists = viewer.tab_lists
    details = viewer.details
    status_lbl = viewer.status_label

    scene_tree = TreeWidget()
    scene_tree.row_height = 22
    scene_tree.stretch = True
    viewer.add_tab("Scenes", scene_tree)

    # Storage
    all_infos: dict[str, list] = {}
    selected: dict = {}

    def _fmt_mem(b: int) -> str:
        if b < 1024:
            return f"{b} B"
        if b < 1024 * 1024:
            return f"{b / 1024:.1f} KB"
        return f"{b / (1024 * 1024):.1f} MB"

    # --- Refresh functions ---
    def _make_tab_data(tab_name: str, infos: list):
        return [(tab_name, info) for info in infos]

    def _refresh_meshes():
        infos = tc_mesh_get_all_info()
        all_infos["Meshes"] = infos
        rows = []
        for info in infos:
            rows.append([
                info["name"],
                str(info.get("vertex_count", 0)),
                str(info.get("index_count", 0)),
                _fmt_mem(info.get("memory_bytes", 0)),
            ])
        tab_lists["Meshes"].set_rows(rows, _make_tab_data("Meshes", infos))

    def _refresh_textures():
        infos = tc_texture_get_all_info()
        all_infos["Textures"] = infos
        rows = []
        for info in infos:
            rows.append([
                info["name"],
                f"{info.get('width', 0)}x{info.get('height', 0)}",
                str(info.get("channels", 0)),
                _fmt_mem(info.get("memory_bytes", 0)),
            ])
        tab_lists["Textures"].set_rows(rows, _make_tab_data("Textures", infos))

    def _refresh_shaders():
        infos = shader_get_all_info()
        all_infos["Shaders"] = infos
        rows = []
        for info in infos:
            stype = "variant" if info.get("is_variant") else "standard"
            if info.get("has_geometry"):
                stype += "+geom"
            rows.append([
                info["name"],
                stype,
                str(info.get("version", 0)),
                str(info.get("source_size", 0)),
            ])
        tab_lists["Shaders"].set_rows(rows, _make_tab_data("Shaders", infos))

    def _refresh_materials():
        infos = tc_material_get_all_info()
        all_infos["Materials"] = infos
        rows = []
        for info in infos:
            rows.append([
                info["name"],
                str(info.get("phase_count", 0)),
                str(info.get("texture_count", 0)),
                str(info.get("version", 0)),
            ])
        tab_lists["Materials"].set_rows(rows, _make_tab_data("Materials", infos))

    def _refresh_components():
        infos = component_registry_get_all_info()
        all_infos["Components"] = infos
        rows = []
        for info in infos:
            descendants = info.get("descendants", [])
            rows.append([
                info["name"],
                info.get("language", "?"),
                "yes" if info.get("is_drawable") else "",
                info.get("parent", ""),
                str(len(descendants)),
            ])
        tab_lists["Components"].set_rows(rows, _make_tab_data("Components", infos))

    def _refresh_soa_types():
        infos = soa_registry_get_all_info()
        all_infos["SoA Types"] = infos
        rows = []
        for info in infos:
            rows.append([
                info["name"],
                str(info.get("id", "?")),
                str(info.get("element_size", 0)),
                str(info.get("alignment", 0)),
                "yes" if info.get("has_init") else "",
                "yes" if info.get("has_destroy") else "",
            ])
        tab_lists["SoA Types"].set_rows(rows, _make_tab_data("SoA Types", infos))

    def _refresh_pipelines():
        infos = tc_pipeline_registry_get_all_info()
        all_infos["Pipelines"] = infos
        rows = []
        for info in infos:
            rows.append([
                info["name"],
                str(info.get("pass_count", 0)),
            ])
        tab_lists["Pipelines"].set_rows(rows, _make_tab_data("Pipelines", infos))

    def _refresh_passes():
        infos = tc_pass_registry_get_all_types()
        all_infos["Passes"] = infos
        rows = []
        for info in infos:
            rows.append([
                info["type_name"],
                info.get("language", "?"),
            ])
        tab_lists["Passes"].set_rows(rows, _make_tab_data("Passes", infos))

    def _refresh_scenes():
        infos = tc_scene_registry_get_all_info()
        all_infos["Scenes"] = infos
        scene_tree.clear()
        for info in infos:
            handle = info.get("handle")
            entities = []
            if handle:
                try:
                    entities = tc_scene_get_entities(handle)
                except Exception as e:
                    log.debug(f"[CoreRegistry] Failed to get entities for scene {info.get('name', '?')}: {e}")
            info["entities"] = entities

            scene_node = TreeNode(content=_make_scene_tree_row(info))
            scene_node.data = ("Scenes", info)
            scene_node.expanded = True
            scene_tree.add_root(scene_node)

            for entity in sorted(entities, key=_entity_sort_key):
                entity_node = TreeNode(content=_make_entity_tree_row(entity))
                entity_node.data = ("Entity", entity)
                scene_node.add_node(entity_node)

    def _refresh_all():
        _refresh_meshes()
        _refresh_textures()
        _refresh_shaders()
        _refresh_materials()
        _refresh_components()
        _refresh_soa_types()
        _refresh_pipelines()
        _refresh_passes()
        _refresh_scenes()
        _update_status()

    def _update_status():
        total_mem = 0
        for info in all_infos.get("Meshes", []):
            total_mem += info.get("memory_bytes", 0)
        for info in all_infos.get("Textures", []):
            total_mem += info.get("memory_bytes", 0)

        parts = []
        parts.append(f"Meshes: {tc_mesh_count()}")
        parts.append(f"Tex: {tc_texture_count()}")
        parts.append(f"Shaders: {shader_count()}")
        parts.append(f"Mat: {tc_material_count()}")
        parts.append(f"Comp: {component_registry_type_count()}")
        parts.append(f"Mem: {_fmt_mem(total_mem)}")
        status_lbl.text = "  |  ".join(parts)

    # --- Selection ---
    def _on_select(idx, data):
        if data is None:
            return
        tab, info = data
        selected.clear()
        selected["tab"] = tab
        selected["info"] = info
        _show_details(tab, info)

    def _on_scene_tree_select(node):
        if node is None or node.data is None:
            return
        kind, info = node.data
        selected.clear()
        selected["tab"] = kind
        selected["info"] = info
        if kind == "Scenes":
            _show_scene_details(info)
        elif kind == "Entity":
            _show_entity_details(info)

    viewer.set_table_select_handler(_on_select)
    scene_tree.on_select = _on_scene_tree_select

    # --- Detail display ---
    def _show_details(tab: str, info: dict):
        if tab == "Meshes":
            _show_mesh_details(info)
        elif tab == "Textures":
            _show_texture_details(info)
        elif tab == "Shaders":
            _show_shader_details(info)
        elif tab == "Materials":
            _show_material_details(info)
        elif tab == "Components":
            _show_component_details(info)
        elif tab == "SoA Types":
            _show_soa_details(info)
        elif tab == "Pipelines":
            _show_pipeline_details(info)
        elif tab == "Passes":
            _show_pass_details(info)
        elif tab == "Scenes":
            _show_scene_details(info)

    def _show_mesh_details(info: dict):
        lines = [f"=== Mesh: {info['name']} ===", ""]
        lines.append(f"UUID:      {info.get('uuid', '')}")
        lines.append(f"Vertices:  {info.get('vertex_count', 0)}")
        lines.append(f"Triangles: {info.get('index_count', 0)}")
        lines.append(f"Stride:    {info.get('stride', 0)}")
        lines.append(f"Memory:    {_fmt_mem(info.get('memory_bytes', 0))}")
        lines.append(f"Ref count: {info.get('ref_count', 0)}")
        lines.append(f"Version:   {info.get('version', 0)}")

        details.text = "\n".join(lines)

    def _show_texture_details(info: dict):
        lines = [f"=== Texture: {info['name']} ===", ""]
        lines.append(f"UUID:      {info.get('uuid', '')}")
        lines.append(f"Size:      {info.get('width', 0)}x{info.get('height', 0)}")
        lines.append(f"Channels:  {info.get('channels', 0)}")
        lines.append(f"Format:    {info.get('format', 'unknown')}")
        lines.append(f"Source:    {info.get('source_path', '')}")
        lines.append(f"Memory:    {_fmt_mem(info.get('memory_bytes', 0))}")
        lines.append(f"Ref count: {info.get('ref_count', 0)}")
        lines.append(f"Version:   {info.get('version', 0)}")
        details.text = "\n".join(lines)

    def _show_shader_details(info: dict):
        lines = [f"=== Shader: {info['name']} ===", ""]
        lines.append(f"UUID:      {info.get('uuid', '')}")
        lines.append(f"Source:    {info.get('source_path', '')}")
        lines.append(f"Variant:   {info.get('is_variant', False)}")
        if info.get("is_variant"):
            lines.append(f"Variant op: {info.get('variant_op', '')}")
        lines.append(f"Geometry:  {info.get('has_geometry', False)}")
        lines.append(f"Features:  {info.get('features', 0)}")
        lines.append(f"Src size:  {info.get('source_size', 0)}")
        lines.append(f"Ref count: {info.get('ref_count', 0)}")
        lines.append(f"Version:   {info.get('version', 0)}")

        # Try to get shader source
        uuid = info.get("uuid")
        if uuid:
            try:
                shader = TcShader.from_uuid(uuid)
                if shader.is_valid:
                    lines.append("")
                    lines.append("--- Vertex Source ---")
                    lines.append(shader.vertex_source[:500] if shader.vertex_source else "(empty)")
                    lines.append("")
                    lines.append("--- Fragment Source ---")
                    lines.append(shader.fragment_source[:500] if shader.fragment_source else "(empty)")
                    if shader.has_geometry:
                        lines.append("")
                        lines.append("--- Geometry Source ---")
                        lines.append(shader.geometry_source[:500] if shader.geometry_source else "(empty)")
            except Exception as e:
                log.debug(f"[CoreRegistry] Failed to get shader source for {uuid}: {e}")

        details.text = "\n".join(lines)

    def _show_material_details(info: dict):
        lines = [f"=== Material: {info['name']} ===", ""]
        lines.append(f"UUID:      {info.get('uuid', '')}")
        lines.append(f"Phases:    {info.get('phase_count', 0)}")
        lines.append(f"Textures:  {info.get('texture_count', 0)}")
        lines.append(f"Ref count: {info.get('ref_count', 0)}")
        lines.append(f"Version:   {info.get('version', 0)}")

        uuid = info.get("uuid")
        if uuid:
            try:
                mat = TcMaterial.from_uuid(uuid)
                if mat.is_valid:
                    lines.append("")
                    lines.append(f"Shader:       {mat.shader_name or '(none)'}")
                    lines.append(f"Active phase: {mat.active_phase_mark or '(none)'}")
                    c = mat.color
                    lines.append(f"Color:        ({c.x:.2f}, {c.y:.2f}, {c.z:.2f}, {c.w:.2f})")
            except Exception as e:
                log.debug(f"[CoreRegistry] Failed to get material details for {uuid}: {e}")

        details.text = "\n".join(lines)

    def _show_component_details(info: dict):
        lines = [f"=== Component: {info['name']} ===", ""]
        lines.append(f"Language:    {info.get('language', '?')}")
        lines.append(f"Drawable:    {info.get('is_drawable', False)}")
        lines.append(f"Parent:      {info.get('parent', '(none)')}")
        descendants = info.get("descendants", [])
        if descendants:
            lines.append(f"Descendants: {len(descendants)}")
            for d in descendants:
                lines.append(f"  - {d}")
        details.text = "\n".join(lines)

    def _show_soa_details(info: dict):
        lines = [f"=== SoA Type: {info['name']} ===", ""]
        lines.append(f"ID:        {info.get('id', '?')}")
        lines.append(f"Size:      {info.get('element_size', 0)} bytes")
        lines.append(f"Alignment: {info.get('alignment', 0)}")
        lines.append(f"Has init:  {info.get('has_init', False)}")
        lines.append(f"Has destroy: {info.get('has_destroy', False)}")
        details.text = "\n".join(lines)

    def _show_pipeline_details(info: dict):
        lines = [f"=== Pipeline: {info['name']} ===", ""]
        lines.append(f"Pass count: {info.get('pass_count', 0)}")

        # Get pass instances for this pipeline
        pipeline_ptr = info.get("ptr")
        if pipeline_ptr:
            try:
                all_passes = tc_pass_registry_get_all_instance_info()
                pipeline_passes = [p for p in all_passes if p.get("pipeline_ptr") == pipeline_ptr]
                if pipeline_passes:
                    lines.append("")
                    lines.append("--- Passes ---")
                    for p in pipeline_passes:
                        enabled = "enabled" if p.get("enabled", True) else "disabled"
                        lines.append(f"  {p.get('pass_name', '?')}  type={p.get('type_name', '?')}  [{enabled}]")
            except Exception as e:
                log.debug(f"[CoreRegistry] Failed to get pipeline passes for {info.get('name', '?')}: {e}")

        details.text = "\n".join(lines)

    def _show_pass_details(info: dict):
        lines = [f"=== Pass Type: {info['type_name']} ===", ""]
        lines.append(f"Language: {info.get('language', '?')}")
        details.text = "\n".join(lines)

    def _show_scene_details(info: dict):
        lines = [f"=== Scene: {info['name']} ===", ""]
        lines.append(f"Entity count:    {info.get('entity_count', 0)}")
        lines.append(f"Entities loaded: {len(info.get('entities', []))}")
        lines.append(f"Pending count:   {info.get('pending_count', 0)}")
        lines.append(f"Update count:    {info.get('update_count', 0)}")
        lines.append(f"Fixed update:    {info.get('fixed_update_count', 0)}")

        handle = info.get("handle")
        if handle:
            # Component types in scene
            try:
                comp_types = tc_scene_get_component_types(handle)
                if comp_types:
                    lines.append("")
                    lines.append("--- Component Types ---")
                    for ct in comp_types:
                        lines.append(f"  {ct.get('type_name', '?')}  count={ct.get('count', 0)}")
            except Exception as e:
                log.debug(f"[CoreRegistry] Failed to get component types for scene {info.get('name', '?')}: {e}")

        details.text = "\n".join(lines)

    def _entity_sort_key(entity: dict) -> tuple[int, str, int]:
        pick_id = int(entity.get("pick_id", 0))
        name = entity.get("name") or entity.get("uuid") or ""
        return (pick_id, name, int(entity.get("id_index", 0)))

    def _entity_flags(entity: dict) -> str:
        flags = []
        flags.append("E" if entity.get("enabled", True) else "-")
        flags.append("V" if entity.get("visible", True) else "-")
        flags.append("P" if entity.get("pickable", True) else "-")
        flags.append("S" if entity.get("selectable", True) else "-")
        return " ".join(flags)

    def _make_tree_label(text: str) -> Label:
        lbl = Label()
        lbl.text = text
        lbl.font_size = 12
        lbl.stretch = True
        return lbl

    def _make_scene_tree_row(info: dict) -> Label:
        name = info.get("name", "<unnamed scene>")
        entity_count = info.get("entity_count", 0)
        loaded_count = len(info.get("entities", []))
        return _make_tree_label(f"{name}  entities={entity_count} loaded={loaded_count}")

    def _make_entity_tree_row(entity: dict) -> Label:
        name = entity.get("name") or "(unnamed)"
        entity_id = f"{entity.get('id_index', '?')}:{entity.get('id_generation', '?')}"
        return _make_tree_label(
            f"{name}  pick_id={entity.get('pick_id', 0)}  "
            f"runtime={entity.get('runtime_id', 0)}  id={entity_id}  "
            f"components={entity.get('component_count', 0)}  flags={_entity_flags(entity)}"
        )

    def _show_entity_details(info: dict) -> None:
        parent_index = info.get("parent_index")
        parent_generation = info.get("parent_generation")
        parent_text = (
            f"{parent_index}:{parent_generation}"
            if parent_index is not None and parent_generation is not None
            else "(root)"
        )
        components = info.get("components", [])
        lines = [
            "=== ENTITY ===",
            "",
            f"Name:           {info.get('name') or '(unnamed)'}",
            f"UUID:           {info.get('uuid', '')}",
            f"Entity ID:      {info.get('id_index', '?')}:{info.get('id_generation', '?')}",
            f"Runtime ID:     {info.get('runtime_id', 0)}",
            f"Pick ID:        {info.get('pick_id', 0)}",
            "",
            "--- State ---",
            f"Enabled:        {info.get('enabled', True)}",
            f"Visible:        {info.get('visible', True)}",
            f"Pickable:       {info.get('pickable', True)}",
            f"Selectable:     {info.get('selectable', True)}",
            f"Priority:       {info.get('priority', 0)}",
            f"Layer:          {info.get('layer', 0)}",
            f"Flags:          {info.get('flags', 0)}",
            "",
            "--- Hierarchy ---",
            f"Parent:         {parent_text}",
            f"Children:       {info.get('children_count', 0)}",
            "",
            "--- Components ---",
            f"Count:          {info.get('component_count', 0)}",
        ]
        for index, component in enumerate(components):
            lines.append("")
            lines.append(f"[{index}] {component.get('type_name', '<unknown>')}")
            lines.append(f"  ptr:              0x{int(component.get('ptr', 0)):x}")
            lines.append(f"  enabled:          {component.get('enabled', False)}")
            lines.append(f"  active_in_editor: {component.get('active_in_editor', False)}")
            lines.append(f"  started:          {component.get('started', False)}")
            lines.append(f"  update:           {component.get('has_update', False)}")
            lines.append(f"  fixed_update:     {component.get('has_fixed_update', False)}")
            lines.append(f"  before_render:    {component.get('has_before_render', False)}")
        details.text = "\n".join(lines)

    viewer.add_button("Refresh", _refresh_all)

    _refresh_all()
    viewer.show(ui)
