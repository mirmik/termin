"""Widget tree construction for EditorWindowTcgui."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tcgui.widgets.button import Button
from tcgui.widgets.file_grid_widget import FileGridWidget
from tcgui.widgets.hstack import HStack
from tcgui.widgets.icon_button import IconButton
from tcgui.widgets.label import Label
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.tabs import TabView
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.tree import TreeWidget
from tcgui.widgets.units import pct, px
from tcgui.widgets.viewport3d import Viewport3D
from tcgui.widgets.vstack import VStack

from termin.editor_tcgui.modules_panel import ModulesPanel
from termin.editor_tcgui.profiler_panel import ProfilerPanel
from termin.editor_tcgui.viewport_list_widget import ViewportListWidgetTcgui


@dataclass
class EditorWindowWidgets:
    root: VStack
    menu_bar: MenuBar
    scene_tree: TreeWidget
    scene_collapse_all_button: IconButton
    viewport_list: ViewportListWidgetTcgui
    left_tabs: TabView
    left_splitter: Splitter
    center_tabs: TabView
    viewport_widget: Viewport3D
    right_scroll: ScrollArea
    right_splitter: Splitter
    inspector_container: VStack
    debug_panel: TabView
    debug_splitter: Splitter
    profiler_panel: ProfilerPanel
    modules_panel: ModulesPanel
    bottom_tabs: TabView
    bottom_splitter: Splitter
    project_dir_tree: TreeWidget
    project_file_list: FileGridWidget
    project_breadcrumb: HStack
    console_area: TextArea
    status_bar: StatusBar
    play_button: Button
    pause_button: Button
    prefab_toolbar: HStack
    prefab_toolbar_label: Label
    save_prefab_button: Button
    exit_prefab_button: Button


@dataclass(frozen=True)
class EditorWindowLayoutCallbacks:
    toggle_game_mode: Callable[[], None]
    toggle_pause: Callable[[], None]
    save_prefab: Callable[[], None]
    exit_prefab_editing: Callable[[], None]
    viewport_external_drag: Callable[[object], bool]
    viewport_external_drop: Callable[[object], bool]


def build_editor_window_layout(callbacks: EditorWindowLayoutCallbacks) -> EditorWindowWidgets:
    root = VStack()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.spacing = 0

    menu_bar = MenuBar()
    root.add_child(menu_bar)

    main_area = HStack()
    main_area.stretch = True
    main_area.spacing = 0

    left_tabs = TabView()
    left_tabs.preferred_width = px(280)

    scene_tab_content = VStack()
    scene_tab_content.spacing = 4

    scene_toolbar = HStack()
    scene_toolbar.preferred_height = px(30)
    scene_toolbar.spacing = 4
    scene_toolbar.alignment = "center"

    scene_title = Label()
    scene_title.text = "Hierarchy"
    scene_title.stretch = True
    scene_title.mouse_transparent = True
    scene_toolbar.add_child(scene_title)

    scene_collapse_all_button = IconButton()
    scene_collapse_all_button.icon = "<<"
    scene_collapse_all_button.tooltip = "Collapse all"
    scene_collapse_all_button.size = 24
    scene_collapse_all_button.font_size = 13
    scene_toolbar.add_child(scene_collapse_all_button)

    scene_tab_content.add_child(scene_toolbar)

    scene_tree = TreeWidget()
    scene_tree.stretch = True
    scene_tab_content.add_child(scene_tree)
    left_tabs.add_tab("Scene", scene_tab_content)

    viewport_list = ViewportListWidgetTcgui()
    viewport_list.stretch = True
    left_tabs.add_tab("Rendering", viewport_list)

    main_area.add_child(left_tabs)
    left_splitter = Splitter(target=left_tabs, side="right")
    main_area.add_child(left_splitter)

    center_area = VStack()
    center_area.stretch = True
    center_area.spacing = 0

    toolbar = HStack()
    toolbar.preferred_height = px(32)
    toolbar.spacing = 4
    toolbar.alignment = "center"

    spacer_left = Label()
    spacer_left.stretch = True
    spacer_left.mouse_transparent = True
    toolbar.add_child(spacer_left)

    play_button = Button()
    play_button.text = "Play"
    play_button.preferred_width = px(60)
    play_button.preferred_height = px(24)
    play_button.on_click = callbacks.toggle_game_mode
    toolbar.add_child(play_button)

    pause_button = Button()
    pause_button.text = "Pause"
    pause_button.preferred_width = px(60)
    pause_button.preferred_height = px(24)
    pause_button.visible = False
    pause_button.on_click = callbacks.toggle_pause
    toolbar.add_child(pause_button)

    prefab_toolbar = HStack()
    prefab_toolbar.spacing = 4
    prefab_toolbar.visible = False

    prefab_toolbar_label = Label()
    prefab_toolbar_label.text = "Editing Prefab"
    prefab_toolbar_label.mouse_transparent = True
    prefab_toolbar.add_child(prefab_toolbar_label)

    save_prefab_button = Button()
    save_prefab_button.text = "Save"
    save_prefab_button.preferred_width = px(60)
    save_prefab_button.preferred_height = px(24)
    save_prefab_button.on_click = callbacks.save_prefab
    prefab_toolbar.add_child(save_prefab_button)

    exit_prefab_button = Button()
    exit_prefab_button.text = "Exit"
    exit_prefab_button.preferred_width = px(60)
    exit_prefab_button.preferred_height = px(24)
    exit_prefab_button.on_click = callbacks.exit_prefab_editing
    prefab_toolbar.add_child(exit_prefab_button)

    toolbar.add_child(prefab_toolbar)

    spacer_right = Label()
    spacer_right.stretch = True
    spacer_right.mouse_transparent = True
    toolbar.add_child(spacer_right)

    center_area.add_child(toolbar)

    center_tabs = TabView()
    center_tabs.stretch = True

    viewport_widget = Viewport3D()
    viewport_widget.stretch = True
    viewport_widget.on_external_drag = callbacks.viewport_external_drag
    viewport_widget.on_external_drop = callbacks.viewport_external_drop
    center_tabs.add_tab("Editor", viewport_widget)

    center_area.add_child(center_tabs)
    main_area.add_child(center_area)

    right_scroll = ScrollArea()
    right_scroll.preferred_width = px(430)
    inspector_container = VStack()
    inspector_container.spacing = 4
    right_scroll.add_child(inspector_container)
    right_splitter = Splitter(target=right_scroll, side="left")
    main_area.add_child(right_splitter)
    main_area.add_child(right_scroll)

    debug_panel = TabView()
    debug_panel.preferred_width = px(350)
    debug_panel.visible = False

    profiler_panel = ProfilerPanel()
    debug_panel.add_tab("Profiler", profiler_panel)

    modules_panel = ModulesPanel()
    debug_panel.add_tab("Modules", modules_panel)

    debug_splitter = Splitter(target=debug_panel, side="left")
    debug_splitter.visible = False
    main_area.add_child(debug_splitter)
    main_area.add_child(debug_panel)

    root.add_child(main_area)

    bottom_tabs = TabView()
    bottom_tabs.preferred_height = px(380)
    bottom_splitter = Splitter(target=bottom_tabs, side="top")
    root.add_child(bottom_splitter)

    project_tab_content = HStack()
    project_tab_content.spacing = 0
    project_tab_content.stretch = True

    project_dir_tree = TreeWidget()
    project_dir_tree.preferred_width = px(200)
    project_dir_tree.stretch = True

    dir_tree_scroll = ScrollArea()
    dir_tree_scroll.preferred_width = px(200)
    dir_tree_scroll.add_child(project_dir_tree)

    project_file_list = FileGridWidget()
    project_file_list.stretch = True
    project_file_list.preferred_height = px(0)
    project_file_list.empty_text = "Select a directory"

    project_file_column = VStack()
    project_file_column.stretch = True
    project_file_column.spacing = 4

    project_breadcrumb = HStack()
    project_breadcrumb.preferred_height = px(24)
    project_breadcrumb.spacing = 2

    project_file_column.add_child(project_breadcrumb)
    project_file_column.add_child(project_file_list)

    project_tab_content.add_child(dir_tree_scroll)
    project_tab_content.add_child(Splitter(target=dir_tree_scroll, side="right"))
    project_tab_content.add_child(project_file_column)

    bottom_tabs.add_tab("Project", project_tab_content)

    console_area = TextArea()
    console_area.read_only = True
    bottom_tabs.add_tab("Console", console_area)
    root.add_child(bottom_tabs)

    status_bar = StatusBar()
    root.add_child(status_bar)

    return EditorWindowWidgets(
        root=root,
        menu_bar=menu_bar,
        scene_tree=scene_tree,
        scene_collapse_all_button=scene_collapse_all_button,
        viewport_list=viewport_list,
        left_tabs=left_tabs,
        left_splitter=left_splitter,
        center_tabs=center_tabs,
        viewport_widget=viewport_widget,
        right_scroll=right_scroll,
        right_splitter=right_splitter,
        inspector_container=inspector_container,
        debug_panel=debug_panel,
        debug_splitter=debug_splitter,
        profiler_panel=profiler_panel,
        modules_panel=modules_panel,
        bottom_tabs=bottom_tabs,
        bottom_splitter=bottom_splitter,
        project_dir_tree=project_dir_tree,
        project_file_list=project_file_list,
        project_breadcrumb=project_breadcrumb,
        console_area=console_area,
        status_bar=status_bar,
        play_button=play_button,
        pause_button=pause_button,
        prefab_toolbar=prefab_toolbar,
        prefab_toolbar_label=prefab_toolbar_label,
        save_prefab_button=save_prefab_button,
        exit_prefab_button=exit_prefab_button,
    )
