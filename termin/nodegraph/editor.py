"""PipelineGraphEditor - Main window for visual pipeline editing."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QToolBar,
    QLabel,
    QStatusBar,
    QFileDialog,
)
from PyQt6.QtGui import QAction, QKeySequence

from termin.nodegraph.scene import NodeGraphScene
from termin.nodegraph.view import NodeGraphView
from termin.nodegraph.nodes import create_node
from termin.nodegraph.serialization import serialize_graph, deserialize_graph
from termin.nodegraph.compiler import compile_graph_to_dict, CompileError

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class PipelineGraphEditor(QMainWindow):
    """
    Visual editor for render pipelines using a node graph.

    Allows creating and connecting:
    - Resource nodes (FBOs, textures)
    - Pass nodes (ColorPass, ShadowPass, etc.)
    - Effect nodes (Bloom, Highlight, etc.)
    - Viewport output nodes
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle("Pipeline Graph Editor")
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)

        # Scene reference (set later)
        self._scene: Optional[Scene] = None

        self._setup_ui()
        self._setup_toolbar()
        self._create_demo_graph()

    def _setup_ui(self) -> None:
        """Setup the main UI."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create graph scene and view
        self._graph_scene = NodeGraphScene()
        self._graph_view = NodeGraphView(self._graph_scene)
        layout.addWidget(self._graph_view)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Right-click to add nodes. Middle-mouse to pan. Scroll to zoom.")

    def _setup_toolbar(self) -> None:
        """Setup the toolbar."""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Save
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_graph)
        toolbar.addAction(save_action)

        # Load
        load_action = QAction("Load", self)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        load_action.triggered.connect(self._load_graph)
        toolbar.addAction(load_action)

        toolbar.addSeparator()

        # Fit view
        fit_action = QAction("Fit View", self)
        fit_action.setShortcut(QKeySequence("F"))
        fit_action.triggered.connect(self._graph_view.fit_in_view)
        toolbar.addAction(fit_action)

        # Clear
        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(self._clear_graph)
        toolbar.addAction(clear_action)

        toolbar.addSeparator()

        # Compile
        compile_action = QAction("Compile Pipeline", self)
        compile_action.setShortcut(QKeySequence("Ctrl+Return"))
        compile_action.triggered.connect(self._compile_pipeline)
        toolbar.addAction(compile_action)

        toolbar.addSeparator()

        # Info label
        self._info_label = QLabel("Scene: (none)")
        toolbar.addWidget(self._info_label)

    def set_scene(self, scene: "Scene") -> None:
        """Set the scene to edit pipeline for."""
        self._scene = scene
        scene_name = scene.name if scene else "(none)"
        self._info_label.setText(f"Scene: {scene_name}")
        self.setWindowTitle(f"Pipeline Graph Editor - {scene_name}")

    def _clear_graph(self) -> None:
        """Clear the graph."""
        self._graph_scene.clear_graph()
        self._status_bar.showMessage("Graph cleared")

    def _create_demo_graph(self) -> None:
        """Create a demo graph to show capabilities."""
        from termin.nodegraph.viewport_frame import ViewportFrame
        from termin.nodegraph.connection import NodeConnection

        # Create viewport frame first (draws behind nodes)
        viewport_frame = ViewportFrame(
            title="Main Viewport",
            x=-250,
            y=-300,
            width=720,
            height=380,
        )
        self._graph_scene.add_viewport_frame(viewport_frame)

        # Shadow pass (outside viewport - shared resource)
        shadow = create_node("pass", "ShadowPass")
        shadow.setPos(-450, -100)
        self._graph_scene.add_node(shadow)

        # Nodes inside viewport frame (below header area):

        # Skybox pass
        skybox = create_node("pass", "SkyboxPass")
        skybox.setPos(-200, -180)
        self._graph_scene.add_node(skybox)

        # Color pass
        color = create_node("pass", "ColorPass")
        color.setPos(0, -80)
        self._graph_scene.add_node(color)

        # PostProcess
        postfx = create_node("pass", "PostProcess")
        postfx.setPos(200, -80)
        self._graph_scene.add_node(postfx)

        # Present (final output inside viewport)
        present = create_node("pass", "Present")
        present.setPos(400, -80)
        self._graph_scene.add_node(present)

        # Create connections

        # Shadow -> Color (from outside into viewport)
        conn1 = NodeConnection()
        conn1.set_start_socket(shadow.output_sockets[0])
        conn1.set_end_socket(color.input_sockets[1])
        self._graph_scene.add_connection(conn1)

        # Skybox -> Color
        conn2 = NodeConnection()
        conn2.set_start_socket(skybox.output_sockets[0])
        conn2.set_end_socket(color.input_sockets[0])
        self._graph_scene.add_connection(conn2)

        # Color -> PostProcess
        conn3 = NodeConnection()
        conn3.set_start_socket(color.output_sockets[0])
        conn3.set_end_socket(postfx.input_sockets[0])
        self._graph_scene.add_connection(conn3)

        # PostProcess -> Present
        conn4 = NodeConnection()
        conn4.set_start_socket(postfx.output_sockets[0])
        conn4.set_end_socket(present.input_sockets[0])
        self._graph_scene.add_connection(conn4)

        self._status_bar.showMessage("Demo graph created. Nodes inside blue frame use viewport resolution.")

    def _compile_pipeline(self) -> None:
        """Compile the graph into a RenderPipeline and print serialization."""
        nodes = self._graph_scene.get_nodes()
        connections = self._graph_scene.get_connections()

        pass_count = sum(1 for n in nodes if n.node_type in ("pass", "effect"))
        conn_count = len(connections)

        try:
            pipeline_dict = compile_graph_to_dict(self._graph_scene)

            self._status_bar.showMessage(
                f"Compiled: {pass_count} passes, {conn_count} connections → "
                f"{len(pipeline_dict.get('passes', []))} passes in pipeline"
            )

            # Pretty print the serialized pipeline
            print("\n" + "=" * 60)
            print("COMPILED PIPELINE")
            print("=" * 60)
            print(json.dumps(pipeline_dict, indent=2, default=str))
            print("=" * 60 + "\n")

        except CompileError as e:
            self._status_bar.showMessage(f"Compilation error: {e}")
            print(f"\nCompilation error: {e}\n")
        except Exception as e:
            self._status_bar.showMessage(f"Unexpected error: {e}")
            print(f"\nUnexpected error during compilation: {e}\n")
            import traceback
            traceback.print_exc()

    def _save_graph(self) -> None:
        """Save the graph to a JSON file."""
        dialog = QFileDialog(self, "Save Pipeline Graph")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter("Scene Pipeline (*.scene_pipeline);;All Files (*)")
        dialog.setDefaultSuffix("scene_pipeline")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return

        file_path = dialog.selectedFiles()[0]
        if not file_path:
            return

        try:
            data = serialize_graph(self._graph_scene)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._status_bar.showMessage(f"Saved: {file_path}")
        except Exception as e:
            self._status_bar.showMessage(f"Save failed: {e}")

    def _load_graph(self) -> None:
        """Load a graph from a JSON file."""
        dialog = QFileDialog(self, "Load Pipeline Graph")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setNameFilter("Scene Pipeline (*.scene_pipeline);;Pipeline (*.pipeline);;All Files (*)")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return

        file_path = dialog.selectedFiles()[0]
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            deserialize_graph(data, self._graph_scene)
            self._graph_view.fit_in_view()
            self._status_bar.showMessage(f"Loaded: {file_path}")
        except Exception as e:
            self._status_bar.showMessage(f"Load failed: {e}")
