"""Core Registry Viewer — shows internal core_c registry state."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.tabs import TabView
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.table_widget import TableWidget, TableColumn
from tcgui.widgets.button import Button
from tcgui.widgets.units import px

from tcbase import log


def show_core_registry_viewer(ui) -> None:
    """Show Core Registry viewer dialog."""
    try:
        from tmesh import tc_mesh_get_all_info, tc_mesh_count
        from tgfx import tc_texture_get_all_info, tc_texture_count
        from tgfx import TcShader, shader_get_all_info, shader_count
        from termin._native.render import (
            tc_material_get_all_info,
            tc_material_count,
            TcMaterial,
        )
        from termin.render_framework import (
            tc_pipeline_registry_count,
            tc_pipeline_registry_get_all_info,
            tc_pass_registry_get_all_instance_info,
            tc_pass_registry_get_all_types,
        )
        from termin.scene._scene_native import (
            component_registry_get_all_info,
            component_registry_type_count,
            soa_registry_get_all_info,
            soa_registry_type_count,
        )
        from termin.engine import scene as engine_scene
        tc_scene_registry_get_all_info = engine_scene.tc_scene_registry_get_all_info
        tc_scene_registry_count = engine_scene.tc_scene_registry_count
        tc_scene_get_entities = engine_scene.tc_scene_get_entities
        tc_scene_get_component_types = engine_scene.tc_scene_get_component_types
    except ImportError as e:
        log.error(f"Core registry APIs not available: {e}")
        return

    content = HStack()
    content.spacing = 8
    content.preferred_height = px(500)

    # Left: TabView
    left = VStack()
    left.spacing = 4
    left.stretch = True

    tabs = TabView()
    tabs.stretch = True

    tab_columns = {
        "Meshes": [TableColumn("Name"), TableColumn("Vertices", 80), TableColumn("Triangles", 80), TableColumn("Memory", 80)],
        "Textures": [TableColumn("Name"), TableColumn("Size", 80), TableColumn("Channels", 80), TableColumn("Memory", 80)],
        "Shaders": [TableColumn("Name"), TableColumn("Type", 80), TableColumn("Version", 70), TableColumn("Size", 80)],
        "Materials": [TableColumn("Name"), TableColumn("Phases", 70), TableColumn("Textures", 70), TableColumn("Version", 70)],
        "Components": [TableColumn("Name"), TableColumn("Language", 80), TableColumn("Drawable", 70), TableColumn("Parent"), TableColumn("Descendants", 80)],
        "SoA Types": [TableColumn("Name"), TableColumn("ID", 60), TableColumn("Size", 60), TableColumn("Align", 60), TableColumn("Init", 50), TableColumn("Destroy", 60)],
        "Pipelines": [TableColumn("Name"), TableColumn("Pass Count", 80)],
        "Passes": [TableColumn("Type Name"), TableColumn("Language", 80)],
        "Scenes": [TableColumn("Name"), TableColumn("Entities", 80)],
    }
    tab_lists: dict[str, TableWidget] = {}
    for name, cols in tab_columns.items():
        tw = TableWidget()
        tw.set_columns(cols)
        tw.stretch = True
        tab_lists[name] = tw
        tabs.add_tab(name, tw)

    left.add_child(tabs)

    status_lbl = Label()
    status_lbl.text = ""
    left.add_child(status_lbl)

    content.add_child(left)

    # Right: details
    right = VStack()
    right.spacing = 4
    right.preferred_width = px(400)

    details = TextArea()
    details.read_only = True
    details.word_wrap = False
    details.stretch = True
    details.placeholder = "Select an item to view details"
    right.add_child(details)

    entities_label = Label()
    entities_label.text = "Entities"
    entities_label.visible = False
    right.add_child(entities_label)

    entities_table = TableWidget()
    entities_table.set_columns([
        TableColumn("Name"),
        TableColumn("Components", 90),
        TableColumn("State", 90),
    ])
    entities_table.preferred_height = px(180)
    entities_table.visible = False
    right.add_child(entities_table)

    btn_row = HStack()
    btn_row.spacing = 4
    refresh_btn = Button()
    refresh_btn.text = "Refresh"
    refresh_btn.padding = 6
    refresh_btn.on_click = lambda: _refresh_all()
    btn_row.add_child(refresh_btn)
    right.add_child(btn_row)

    content.add_child(right)

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
        rows = []
        for info in infos:
            rows.append([
                info["name"],
                str(info.get("entity_count", 0)),
            ])
        tab_lists["Scenes"].set_rows(rows, _make_tab_data("Scenes", infos))

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
        if tab != "Scenes":
            _clear_entities()
        _show_details(tab, info)

    def _on_entity_select(idx, data):
        if data is None:
            return
        _show_entity_details(data)

    entities_table.on_select = _on_entity_select

    for tw in tab_lists.values():
        tw.on_select = _on_select

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

            # Entities
            try:
                entities = tc_scene_get_entities(handle)
                _load_entities(entities)
            except Exception as e:
                log.debug(f"[CoreRegistry] Failed to get entities for scene {info.get('name', '?')}: {e}")
                _clear_entities()

        details.text = "\n".join(lines)

    def _load_entities(entities: list[dict]) -> None:
        rows = []
        data = []
        for entity in sorted(entities, key=lambda x: x.get("name") or x.get("uuid") or ""):
            name = entity.get("name") or "(unnamed)"
            enabled = "on" if entity.get("enabled", True) else "off"
            visible = "vis" if entity.get("visible", True) else "hid"
            rows.append([
                name,
                str(entity.get("component_count", 0)),
                f"{enabled}/{visible}",
            ])
            data.append(entity)
        entities_table.set_rows(rows, data)
        entities_table.visible = True
        entities_label.visible = True
        entities_label.text = f"Entities ({len(rows)})"

    def _clear_entities() -> None:
        entities_table.set_rows([], [])
        entities_table.visible = False
        entities_label.visible = False

    def _show_entity_details(info: dict) -> None:
        lines = [
            "=== ENTITY ===",
            "",
            f"Name:           {info.get('name') or '(unnamed)'}",
            f"UUID:           {info.get('uuid', '')}",
            "",
            "--- State ---",
            f"Enabled:        {info.get('enabled', True)}",
            f"Visible:        {info.get('visible', True)}",
            "",
            "--- Components ---",
            f"Count:          {info.get('component_count', 0)}",
        ]
        details.text = "\n".join(lines)

    _refresh_all()

    dlg = Dialog()
    dlg.title = "Core Registry"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 900

    dlg.show(ui, windowed=True)
