"""Resource Manager Viewer — shows all registered assets and their status."""

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


def show_resource_manager_viewer(ui) -> None:
    """Show Resource Manager viewer dialog."""
    from termin.visualization.core.resources import ResourceManager

    rm = ResourceManager.instance()

    content = HStack()
    content.spacing = 8
    content.preferred_height = px(500)

    # Left: TabView with asset lists
    left = VStack()
    left.spacing = 4
    left.stretch = True

    tabs = TabView()
    tabs.stretch = True

    # Column definitions per tab
    _asset_cols = [TableColumn("Name"), TableColumn("Status", 80), TableColumn("Ver", 50), TableColumn("UUID", 200)]
    _pipeline_cols = [TableColumn("Name"), TableColumn("Passes", 70), TableColumn("Ver", 50), TableColumn("UUID", 200)]
    tab_columns = {
        "Materials": [TableColumn("Name"), TableColumn("Phases", 70), TableColumn("Source")],
        "Shaders": _asset_cols,
        "Meshes": _asset_cols,
        "Textures": _asset_cols,
        "VoxelGrids": _asset_cols,
        "NavMeshes": _asset_cols,
        "Skeletons": _asset_cols,
        "Pipelines": _pipeline_cols,
        "ScenePipelines": _pipeline_cols,
        "Components": [TableColumn("Name"), TableColumn("Module")],
        "ComponentRegistry": [TableColumn("Name"), TableColumn("Type", 80)],
    }
    tab_lists: dict[str, TableWidget] = {}
    tab_names = list(tab_columns.keys())
    for name, cols in tab_columns.items():
        tw = TableWidget()
        tw.set_columns(cols)
        tw.stretch = True
        tab_lists[name] = tw
        tabs.add_tab(name, tw)

    left.add_child(tabs)

    # Status label
    status_lbl = Label()
    status_lbl.text = ""
    left.add_child(status_lbl)

    content.add_child(left)

    # Right: details panel
    right = VStack()
    right.spacing = 4
    right.preferred_width = px(350)

    details = TextArea()
    details.read_only = True
    details.word_wrap = False
    details.stretch = True
    details.placeholder = "Select an item to view details"
    right.add_child(details)

    # Load button
    btn_row = HStack()
    btn_row.spacing = 4
    load_btn = Button()
    load_btn.text = "Load Asset"
    load_btn.padding = 6
    load_btn.on_click = lambda: _load_selected()
    btn_row.add_child(load_btn)

    refresh_btn = Button()
    refresh_btn.text = "Refresh"
    refresh_btn.padding = 6
    refresh_btn.on_click = lambda: _refresh_all()
    btn_row.add_child(refresh_btn)
    right.add_child(btn_row)

    content.add_child(right)

    # Data storage — maps tab name → list of dicts with "data" key
    all_data: dict[str, list[dict]] = {}
    selected_item: dict = {}

    def _refresh_all():
        _refresh_materials()
        _refresh_shaders()
        _refresh_meshes()
        _refresh_textures()
        _refresh_voxelgrids()
        _refresh_navmeshes()
        _refresh_skeletons()
        _refresh_pipelines()
        _refresh_scene_pipelines()
        _refresh_components()
        _refresh_component_registry()
        _update_status()

    def _make_status(name: str, is_loaded: bool) -> str:
        return "loaded" if is_loaded else "not loaded"

    def _uuid_short(uuid: str) -> str:
        return uuid[:16] if uuid else ""

    def _set_tab(tab_name: str, rows: list[list[str]], names: list[str]):
        data = [(tab_name, n) for n in names]
        all_data[tab_name] = data
        tab_lists[tab_name].set_rows(rows, data)

    def _refresh_asset_tab(tab_name: str, assets_dict: dict):
        rows = []
        names = []
        for name, asset in sorted(assets_dict.items()):
            rows.append([name, _make_status(name, asset.is_loaded), str(asset.version), _uuid_short(asset.uuid)])
            names.append(name)
        _set_tab(tab_name, rows, names)

    # --- Materials ---
    def _refresh_materials():
        rows = []
        names = []
        for name, mat in sorted(rm.materials.items()):
            phases = len(mat.phases) if mat.phases else 0
            rows.append([name, str(phases), mat.source_path or ""])
            names.append(name)
        _set_tab("Materials", rows, names)

    # --- Asset tabs ---
    def _refresh_shaders():
        _refresh_asset_tab("Shaders", rm._shader_assets)

    def _refresh_meshes():
        _refresh_asset_tab("Meshes", rm._mesh_assets)

    def _refresh_textures():
        _refresh_asset_tab("Textures", rm._texture_assets)

    def _refresh_voxelgrids():
        _refresh_asset_tab("VoxelGrids", rm._voxel_grid_assets)

    def _refresh_navmeshes():
        _refresh_asset_tab("NavMeshes", rm._navmesh_assets)

    def _refresh_skeletons():
        _refresh_asset_tab("Skeletons", rm._skeleton_assets)

    # --- Pipelines ---
    def _refresh_pipelines():
        rows = []
        names = []
        for name in sorted(rm.list_pipeline_names()):
            asset = rm.get_pipeline_asset(name)
            if asset is None:
                continue
            passes = str(len(asset.data.passes)) if asset.is_loaded and asset.data else _make_status(name, asset.is_loaded)
            rows.append([name, passes, str(asset.version), _uuid_short(asset.uuid)])
            names.append(name)
        _set_tab("Pipelines", rows, names)

    # --- Scene Pipelines ---
    def _refresh_scene_pipelines():
        rows = []
        names = []
        for name in sorted(rm.list_scene_pipeline_names()):
            asset = rm.get_scene_pipeline_asset(name)
            if asset is None:
                continue
            rows.append([name, _make_status(name, asset.is_loaded), str(asset.version), _uuid_short(asset.uuid)])
            names.append(name)
        _set_tab("ScenePipelines", rows, names)

    # --- Components ---
    def _refresh_components():
        rows = []
        names = []
        for name, cls in sorted(rm.components.items()):
            rows.append([name, cls.__module__])
            names.append(name)
        _set_tab("Components", rows, names)

    # --- Component Registry ---
    def _refresh_component_registry():
        rows = []
        names = []
        try:
            from termin.entity import ComponentRegistry
            reg = ComponentRegistry.instance()
            for name in sorted(reg.list_native()):
                rows.append([name, "C++"])
                names.append(name)
            for name in sorted(reg.list_python()):
                rows.append([name, "Python"])
                names.append(name)
        except Exception as e:
            log.error(f"Failed to get ComponentRegistry: {e}")
        _set_tab("ComponentRegistry", rows, names)

    # --- Status bar ---
    def _update_status():
        parts = []
        for tab_name in tab_names:
            count = len(all_data.get(tab_name, []))
            if count > 0:
                parts.append(f"{tab_name}: {count}")
        status_lbl.text = "  |  ".join(parts) if parts else "No resources"

    # --- Selection handlers ---
    def _on_select(idx, data):
        if data is None:
            return
        tab, name = data
        selected_item.clear()
        selected_item["tab"] = tab
        selected_item["name"] = name
        _show_details(tab, name)

    for tw in tab_lists.values():
        tw.on_select = _on_select

    # --- Detail display ---
    def _show_details(tab: str, name: str):
        if tab == "Materials":
            _show_material_details(name)
        elif tab == "Shaders":
            _show_shader_details(name)
        elif tab == "Meshes":
            _show_mesh_details(name)
        elif tab == "Textures":
            _show_texture_details(name)
        elif tab == "VoxelGrids":
            _show_voxelgrid_details(name)
        elif tab == "NavMeshes":
            _show_navmesh_details(name)
        elif tab == "Skeletons":
            _show_skeleton_details(name)
        elif tab == "Pipelines":
            _show_pipeline_details(name)
        elif tab == "ScenePipelines":
            _show_scene_pipeline_details(name)
        elif tab == "Components":
            _show_component_details(name)
        elif tab == "ComponentRegistry":
            _show_component_registry_details(name)

    def _show_material_details(name: str):
        mat = rm.materials.get(name)
        if mat is None:
            details.text = f"Material '{name}' not found"
            return
        lines = [f"=== Material: {name} ===", ""]
        lines.append(f"Source:  {mat.source_path or '(unknown)'}")
        lines.append(f"Shader:  {mat.shader_name or '(none)'}")
        lines.append(f"Phases:  {len(mat.phases) if mat.phases else 0}")
        if mat.phases:
            for i, phase in enumerate(mat.phases):
                lines.append(f"")
                lines.append(f"  Phase {i}: mark={phase.phase_mark}")
                if phase.uniforms:
                    for uname, uval in phase.uniforms.items():
                        lines.append(f"    uniform {uname} = {uval}")
                if phase.textures:
                    for tname, tval in phase.textures.items():
                        lines.append(f"    texture {tname} = {tval}")
        details.text = "\n".join(lines)

    def _show_asset_details(name: str, asset, extra_lines=None):
        lines = [f"=== {name} ===", ""]
        lines.append(f"UUID:    {asset.uuid}")
        lines.append(f"Source:  {asset.source_path or '(unknown)'}")
        lines.append(f"Loaded:  {asset.is_loaded}")
        lines.append(f"Version: {asset.version}")
        if extra_lines:
            lines.append("")
            lines.extend(extra_lines)
        details.text = "\n".join(lines)

    def _show_shader_details(name: str):
        asset = rm._shader_assets.get(name)
        if asset is None:
            details.text = f"Shader '{name}' not found"
            return
        extra = []
        if asset.is_loaded and asset.program:
            prog = asset.program
            if prog.phases:
                for i, phase in enumerate(prog.phases):
                    mark = phase.phase_mark if hasattr(phase, 'phase_mark') else ""
                    extra.append(f"Phase {i}: mark={mark}")
        _show_asset_details(name, asset, extra)

    def _show_mesh_details(name: str):
        asset = rm._mesh_assets.get(name)
        if asset is None:
            details.text = f"Mesh '{name}' not found"
            return
        extra = []
        if asset.is_loaded:
            mesh = asset.data
            if mesh is not None:
                extra.append(f"Vertices:  {mesh.vertex_count}")
                extra.append(f"Triangles: {mesh.triangle_count}")
                extra.append(f"Stride:    {mesh.stride}")
        _show_asset_details(name, asset, extra)

    def _show_texture_details(name: str):
        asset = rm._texture_assets.get(name)
        if asset is None:
            details.text = f"Texture '{name}' not found"
            return
        extra = []
        if asset.is_loaded:
            extra.append(f"Size: {asset.width}x{asset.height}")
        _show_asset_details(name, asset, extra)

    def _show_voxelgrid_details(name: str):
        asset = rm._voxel_grid_assets.get(name)
        if asset is None:
            details.text = f"VoxelGrid '{name}' not found"
            return
        extra = []
        if asset.is_loaded and asset.data:
            grid = asset.data
            extra.append(f"Cell size:    {grid.cell_size}")
            extra.append(f"Voxel count:  {grid.voxel_count()}")
            extra.append(f"Origin:       ({grid.origin.x:.2f}, {grid.origin.y:.2f}, {grid.origin.z:.2f})")
        _show_asset_details(name, asset, extra)

    def _show_navmesh_details(name: str):
        asset = rm._navmesh_assets.get(name)
        if asset is None:
            details.text = f"NavMesh '{name}' not found"
            return
        extra = []
        if asset.is_loaded and asset.data:
            nm = asset.data
            extra.append(f"Cell size:      {nm.cell_size}")
            extra.append(f"Polygon count:  {nm.polygon_count()}")
            extra.append(f"Triangle count: {nm.triangle_count()}")
            extra.append(f"Vertex count:   {nm.vertex_count()}")
        _show_asset_details(name, asset, extra)

    def _show_skeleton_details(name: str):
        asset = rm._skeleton_assets.get(name)
        if asset is None:
            details.text = f"Skeleton '{name}' not found"
            return
        extra = []
        if asset.is_loaded and asset.data:
            skel = asset.data
            bone_count = skel.get_bone_count() if hasattr(skel, 'get_bone_count') else len(skel.bones)
            extra.append(f"Bone count: {bone_count}")
            extra.append("")
            for bone in skel.bones:
                extra.append(f"  {bone.name}  parent={bone.parent_index}")
        _show_asset_details(name, asset, extra)

    def _show_pipeline_details(name: str):
        asset = rm.get_pipeline_asset(name)
        if asset is None:
            details.text = f"Pipeline '{name}' not found"
            return
        extra = []
        if asset.is_loaded and asset.data:
            pipeline = asset.data
            extra.append(f"Pass count: {len(pipeline.passes)}")
            for i, p in enumerate(pipeline.passes):
                pname = p.pass_name if hasattr(p, 'pass_name') else str(type(p).__name__)
                extra.append(f"  Pass {i}: {pname}")
        _show_asset_details(name, asset, extra)

    def _show_scene_pipeline_details(name: str):
        asset = rm.get_scene_pipeline_asset(name)
        if asset is None:
            details.text = f"ScenePipeline '{name}' not found"
            return
        extra = []
        if asset.is_loaded:
            graph = asset.graph_data if hasattr(asset, 'graph_data') else asset.data
            if graph and isinstance(graph, dict):
                nodes = graph.get("nodes", [])
                connections = graph.get("connections", [])
                extra.append(f"Nodes:       {len(nodes)}")
                extra.append(f"Connections: {len(connections)}")
                for nd in nodes:
                    nd_type = nd.get("type", "?")
                    nd_id = nd.get("id", "?")
                    params = nd.get("params", {})
                    pass_name = params.get("pass_name", "")
                    extra.append(f"  [{nd_id}] {nd_type} pass={pass_name}")
        _show_asset_details(name, asset, extra)

    def _show_component_details(name: str):
        cls = rm.components.get(name)
        if cls is None:
            details.text = f"Component '{name}' not found"
            return
        lines = [f"=== Component: {name} ===", ""]
        lines.append(f"Module:  {cls.__module__}")
        lines.append(f"Class:   {cls.__qualname__}")
        mro = [c.__name__ for c in cls.__mro__]
        lines.append(f"MRO:     {' → '.join(mro)}")
        details.text = "\n".join(lines)

    def _show_component_registry_details(name: str):
        lines = [f"=== Component: {name} ===", ""]
        try:
            from termin.entity import ComponentRegistry
            reg = ComponentRegistry.instance()
            native = reg.list_native()
            if name in native:
                lines.append("Backend: C++")
            else:
                lines.append("Backend: Python")
        except Exception:
            pass
        details.text = "\n".join(lines)

    # --- Load asset ---
    def _load_selected():
        tab = selected_item.get("tab")
        name = selected_item.get("name")
        if not tab or not name:
            return

        asset = None
        if tab == "Shaders":
            asset = rm._shader_assets.get(name)
        elif tab == "Meshes":
            asset = rm._mesh_assets.get(name)
        elif tab == "Textures":
            asset = rm._texture_assets.get(name)
        elif tab == "VoxelGrids":
            asset = rm._voxel_grid_assets.get(name)
        elif tab == "NavMeshes":
            asset = rm._navmesh_assets.get(name)
        elif tab == "Skeletons":
            asset = rm._skeleton_assets.get(name)
        elif tab == "Pipelines":
            asset = rm.get_pipeline_asset(name)
        elif tab == "ScenePipelines":
            asset = rm.get_scene_pipeline_asset(name)

        if asset is not None and not asset.is_loaded:
            try:
                asset.ensure_loaded()
                _show_details(tab, name)
            except Exception as e:
                log.error(f"Failed to load asset '{name}': {e}")
                details.text = f"Error loading '{name}': {e}"

    _refresh_all()

    dlg = Dialog()
    dlg.title = "Resource Manager"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 900

    dlg.show(ui, windowed=True)
