import os
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt

from termin.visualization.entity import Entity
from termin.kinematic.transform import Transform3
from editor_tree import SceneTreeModel
from termin.visualization.picking import id_to_rgb


class EditorWindow(QMainWindow):
    def __init__(self, world, scene, camera):
        super().__init__()
        self.selected_entity_id = None

        ui_path = os.path.join(os.path.dirname(__file__), "editor.ui")
        uic.loadUi(ui_path, self)

        self.world = world
        self.scene = scene
        self.camera = camera

        # --- UI elements ---
        self.sceneTree = self.findChild(type(self.sceneTree), "sceneTree")
        self.viewportContainer = self.findChild(type(self.viewportContainer), "viewportContainer")
        self.inspectorLabel = self.findChild(type(self.inspectorLabel), "inspectorLabel")

        self.topSplitter = self.findChild(type(self.topSplitter), "topSplitter")
        self.verticalSplitter = self.findChild(type(self.verticalSplitter), "verticalSplitter")

        # --- Fix splitter behaviour ---
        self._fix_splitters()

        # --- Scene tree ---
        self.sceneTree.setModel(SceneTreeModel(scene))
        self.sceneTree.expandAll()
        self.sceneTree.clicked.connect(self.on_tree_click)

        # --- Render viewport ---
        self._init_viewport()

    # ----------------------------------------------------
    def _fix_splitters(self):
        # сглаживание resize
        self.topSplitter.setOpaqueResize(False)
        self.verticalSplitter.setOpaqueResize(False)

        # запрет схлопывания
        self.topSplitter.setCollapsible(0, False)
        self.topSplitter.setCollapsible(1, False)
        self.topSplitter.setCollapsible(2, False)

        self.verticalSplitter.setCollapsible(0, False)
        self.verticalSplitter.setCollapsible(1, False)

        # стартовые размеры
        self.topSplitter.setSizes([300, 1000, 300])
        self.verticalSplitter.setSizes([600, 200])

    def mouse_button_clicked(self, x, y, viewport):
        print(f"Mouse button clicked at ({x}, {y}) in viewport {viewport}")  # --- DEBUG ---
        self._pending_pick = (x, y, viewport)

    def _after_render(self, window):
        """
        Вызывается из Window._render_core, уже внутри валидного GL-контекста.
        Здесь можно безопасно делать pick_entity_at.
        """
        if self._pending_pick is None:
            return

        x, y, viewport = self._pending_pick
        self._pending_pick = None

        picked_ent = window.pick_entity_at(x, y, viewport)
        if picked_ent is not None:
            self.selected_entity_id = self.viewport_window._get_pick_id_for_entity(picked_ent)
        else:
            self.selected_entity_id = 0

    # ----------------------------------------------------
    def _init_viewport(self):
        self._pending_pick = None  # (x, y, viewport) или None
        layout = self.viewportContainer.layout()

        self.viewport_window = self.world.create_window(
            width=900,
            height=800,
            title="viewport",
            parent=self.viewportContainer
        )
        self.viewport = self.viewport_window.add_viewport(self.scene, self.camera)
        self.viewport_window.set_world_mode("editor")
        #self.viewport_window.set_selection_handler(self.on_entity_picked)
        
        self.viewport_window.on_mouse_button_event = self.mouse_button_clicked
        self.viewport_window.after_render_handler = self._after_render

        gl_widget = self.viewport_window.handle.widget
        gl_widget.setFocusPolicy(Qt.StrongFocus)
        gl_widget.setMinimumSize(50, 50)

        layout.addWidget(gl_widget)

        self.viewport.set_render_pipeline(self.make_pipeline())

    # ----------------------------------------------------
    def on_tree_click(self, index):
        node = index.internalPointer()
        obj = node.obj

        if isinstance(obj, Entity):
            self.inspectorLabel.setText(f"Entity: {obj.name}")
        elif isinstance(obj, Transform3):
            pose = obj.global_pose()
            self.inspectorLabel.setText(
                f"Transform\npos={pose.lin}\nrot={pose.ang}"
            )
        else:
            self.inspectorLabel.setText(str(obj))


    def make_pipeline(
        self,
    ) -> list["FramePass"]:
        """
        Собирает конвейер рендера.
        """
        from termin.visualization.framegraph import ColorPass, IdPass, CanvasPass, PresentToScreenPass
        from termin.visualization.postprocess import PostProcessPass
        from termin.visualization.posteffects.highlight import HighlightEffect


        postprocess = PostProcessPass(
                effects=[],  # можно заранее что-то положить сюда
                input_res="color",
                output_res="color_pp",
                pass_name="PostFX",
            )

        passes: List["FramePass"] = [
            ColorPass(input_res="empty", output_res="color", pass_name="Color"),
            IdPass(input_res="empty_id", output_res="id", pass_name="Id"),
            postprocess,
            CanvasPass(
                src="color_pp",
                dst="color+ui",
                pass_name="Canvas",
            ),
            PresentToScreenPass(
                input_res="color+ui",
                pass_name="Present",
            )
        ]

        postprocess.add_effect(HighlightEffect(lambda: self.selected_entity_id))

        return passes