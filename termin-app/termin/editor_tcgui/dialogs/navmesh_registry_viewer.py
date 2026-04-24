"""NavMesh Registry Viewer — shows registered NavMesh for each agent type and scene."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.tree import TreeWidget, TreeNode
from tcgui.widgets.button import Button
from tcgui.widgets.units import px


def show_navmesh_registry_viewer(ui) -> None:
    """Show NavMesh Registry viewer dialog."""
    content = VStack()
    content.spacing = 4

    # Main area: tree + details
    main_row = HStack()
    main_row.spacing = 8
    main_row.preferred_height = px(350)

    # Left: tree with column headers
    left_col = VStack()
    left_col.spacing = 0
    left_col.preferred_width = px(400)
    left_col.stretch = True

    # Column header row
    _COL_POLYS_W = 70
    _COL_TRIS_W = 70
    _COL_VERTS_W = 70
    _HDR_COLOR = (0.50, 0.50, 0.50, 1.0)

    col_header = HStack()
    col_header.spacing = 0
    col_header.preferred_height = px(20)

    def _hdr_label(text: str, width: int = 0, stretch: bool = False) -> Label:
        lbl = Label()
        lbl.text = text
        lbl.font_size = 11
        lbl.text_color = _HDR_COLOR
        if width:
            lbl.preferred_width = px(width)
        if stretch:
            lbl.stretch = True
        return lbl

    col_header.add_child(_hdr_label("Agent Type / Source", stretch=True))
    col_header.add_child(_hdr_label("Polygons", _COL_POLYS_W))
    col_header.add_child(_hdr_label("Triangles", _COL_TRIS_W))
    col_header.add_child(_hdr_label("Vertices", _COL_VERTS_W))
    left_col.add_child(col_header)

    tree = TreeWidget()
    tree.stretch = True
    left_col.add_child(tree)

    # Right: details
    details = TextArea()
    details.read_only = True
    details.word_wrap = False
    details.stretch = True
    details.placeholder = "Select an item to view details"

    main_row.add_child(left_col)
    main_row.add_child(details)
    content.add_child(main_row)

    # Status
    status_lbl = Label()
    status_lbl.text = ""
    content.add_child(status_lbl)

    def _refresh():
        # Clear tree
        for node in list(tree.root_nodes):
            tree.remove_root(node)
        details.text = ""

        from termin.navmesh.registry import NavMeshRegistry

        total_scenes = 0
        total_meshes = 0
        total_polygons = 0
        total_agent_types = 0

        def _make_row(name_text: str, polys: str, tris: str, verts: str) -> HStack:
            row = HStack()
            row.spacing = 0
            _TEXT_COLOR = (0.75, 0.75, 0.75, 1.0)

            name_lbl = Label()
            name_lbl.text = name_text
            name_lbl.font_size = 12
            name_lbl.text_color = _TEXT_COLOR
            name_lbl.stretch = True
            row.add_child(name_lbl)

            for val, w in [(polys, _COL_POLYS_W), (tris, _COL_TRIS_W), (verts, _COL_VERTS_W)]:
                lbl = Label()
                lbl.text = val
                lbl.font_size = 12
                lbl.text_color = _TEXT_COLOR
                lbl.preferred_width = px(w)
                row.add_child(lbl)

            return row

        for scene_uuid, registry in NavMeshRegistry._instances.items():
            agent_types = registry.list_agent_types()
            if not agent_types:
                continue

            total_scenes += 1

            scene_row = _make_row(f"Scene: {scene_uuid[:8]}...", "", "", "")
            scene_node = TreeNode(content=scene_row)
            scene_node.data = ("scene", scene_uuid)
            scene_node.expanded = True

            for agent_type in sorted(agent_types):
                entries = registry.get_all(agent_type)
                if not entries:
                    continue

                total_agent_types += 1
                agent_polygons = sum(nm.polygon_count() for nm, _ in entries)
                agent_tris = sum(nm.triangle_count() for nm, _ in entries)
                agent_verts = sum(nm.vertex_count() for nm, _ in entries)

                agent_row = _make_row(
                    agent_type,
                    str(agent_polygons), str(agent_tris), str(agent_verts),
                )
                agent_node = TreeNode(content=agent_row)
                agent_node.data = ("agent_type", agent_type, entries)
                agent_node.expanded = True

                for navmesh, entity in entries:
                    source_name = entity.name if entity else "(no entity)"
                    source_uuid = entity.uuid if entity else "?"

                    source_row = _make_row(
                        source_name,
                        str(navmesh.polygon_count()),
                        str(navmesh.triangle_count()),
                        str(navmesh.vertex_count()),
                    )
                    source_node = TreeNode(content=source_row)
                    source_node.data = ("navmesh", navmesh, entity, source_uuid)
                    agent_node.add_node(source_node)

                    total_meshes += 1
                    total_polygons += navmesh.polygon_count()

                scene_node.add_node(agent_node)

            tree.add_root(scene_node)

        if total_scenes == 0:
            status_lbl.text = "No NavMesh registered"
        else:
            status_lbl.text = (
                f"Scenes: {total_scenes} | "
                f"Agent types: {total_agent_types} | "
                f"NavMesh: {total_meshes} | "
                f"Polygons: {total_polygons}"
            )

    def _on_select(node: TreeNode):
        if node is None or node.data is None:
            return
        data = node.data
        if data[0] == "agent_type":
            _show_agent_type_details(data[1], data[2])
        elif data[0] == "navmesh":
            _show_navmesh_details(data[1], data[2], data[3])

    def _show_agent_type_details(agent_type: str, entries: list):
        total_polygons = sum(nm.polygon_count() for nm, _ in entries)
        total_tris = sum(nm.triangle_count() for nm, _ in entries)
        total_verts = sum(nm.vertex_count() for nm, _ in entries)

        lines = [
            f"=== AGENT TYPE: {agent_type} ===",
            "",
            f"Sources:        {len(entries)}",
            f"Total polygons: {total_polygons}",
            f"Total tris:     {total_tris}",
            f"Total vertices: {total_verts}",
            "",
            "--- Sources ---",
        ]
        for navmesh, entity in entries:
            name = entity.name if entity else "(no entity)"
            uuid = entity.uuid if entity else "?"
            lines.append(f"  {name} ({navmesh.polygon_count()} polys) - {uuid}")

        details.text = "\n".join(lines)

    def _show_navmesh_details(navmesh, entity, source_uuid: str):
        entity_name = entity.name if entity else "(no entity)"

        lines = [
            "=== NAVMESH ===",
            "",
            f"Name:           {navmesh.name}",
            f"Source entity:  {entity_name}",
            f"Source UUID:    {source_uuid}",
            "",
            "--- Geometry ---",
            f"Polygons:       {navmesh.polygon_count()}",
            f"Triangles:      {navmesh.triangle_count()}",
            f"Vertices:       {navmesh.vertex_count()}",
            f"Cell size:      {navmesh.cell_size}",
            f"Origin:         ({navmesh.origin[0]:.2f}, {navmesh.origin[1]:.2f}, {navmesh.origin[2]:.2f})",
            "",
            "--- Polygons ---",
        ]

        for i, poly in enumerate(navmesh.polygons[:20]):
            verts = len(poly.vertices) if poly.vertices is not None else 0
            tris = len(poly.triangles) if poly.triangles is not None else 0
            neighbors = len(poly.neighbors)
            lines.append(f"  [{i}] {verts} verts, {tris} tris, {neighbors} neighbors")

        if navmesh.polygon_count() > 20:
            lines.append(f"  ... and {navmesh.polygon_count() - 20} more")

        details.text = "\n".join(lines)

    tree.on_select = _on_select

    # Buttons
    btn_row = HStack()
    btn_row.spacing = 4
    refresh_btn = Button()
    refresh_btn.text = "Refresh"
    refresh_btn.padding = 6
    refresh_btn.on_click = _refresh
    btn_row.add_child(refresh_btn)
    content.add_child(btn_row)

    _refresh()

    dlg = Dialog()
    dlg.title = "NavMesh Registry Viewer"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 750

    dlg.show(ui, windowed=True)
