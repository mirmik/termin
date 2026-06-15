from termin.editor_tcgui.project_file_action_controller import ProjectFileActionController


class _Recorder:
    def __init__(self) -> None:
        self.scene_path = None
        self.prefab_path = None
        self.inspector = _InspectorRecorder()

    def load_scene(self, path: str) -> None:
        self.scene_path = path

    def open_prefab(self, path: str) -> None:
        self.prefab_path = path

    def get_inspector(self):
        return self.inspector


class _InspectorRecorder:
    def __init__(self) -> None:
        self.material_path = None
        self.pipeline_path = None
        self.texture_path = None
        self.mesh_path = None
        self.glb_path = None

    def show_material_inspector_for_file(self, path: str) -> None:
        self.material_path = path

    def show_pipeline_inspector_for_file(self, path: str) -> None:
        self.pipeline_path = path

    def show_texture_inspector_for_file(self, path: str) -> None:
        self.texture_path = path

    def show_mesh_inspector_for_file(self, path: str) -> None:
        self.mesh_path = path

    def show_glb_inspector_for_file(self, path: str) -> None:
        self.glb_path = path


def _make_controller(
    recorder: _Recorder,
    open_in_text_editor=None,
) -> ProjectFileActionController:
    return ProjectFileActionController(
        load_scene_from_file=recorder.load_scene,
        open_prefab=recorder.open_prefab,
        get_inspector_controller=recorder.get_inspector,
        open_in_text_editor=open_in_text_editor,
    )


def test_project_file_actions_activate_scene_and_prefab() -> None:
    recorder = _Recorder()
    controller = _make_controller(recorder)

    controller.activate_file("/project/Main.tc_scene")
    controller.activate_file("/project/Tree.tc_prefab")

    assert recorder.scene_path == "/project/Main.tc_scene"
    assert recorder.prefab_path == "/project/Tree.tc_prefab"


def test_project_file_actions_activate_other_file_in_text_editor() -> None:
    opened_paths = []

    def _open_in_text_editor(path: str) -> None:
        opened_paths.append(path)

    controller = _make_controller(_Recorder(), open_in_text_editor=_open_in_text_editor)
    controller.activate_file("/project/script.py")

    assert opened_paths == ["/project/script.py"]


def test_project_file_actions_select_files_for_inspector() -> None:
    recorder = _Recorder()
    controller = _make_controller(recorder)

    controller.select_file("/project/material.tc_mat")
    controller.select_file("/project/render.scene_pipeline")
    controller.select_file("/project/albedo.png")
    controller.select_file("/project/mesh.obj")
    assert recorder.inspector.mesh_path == "/project/mesh.obj"

    controller.select_file("/project/mesh.stl")
    controller.select_file("/project/model.glb")

    assert recorder.inspector.material_path == "/project/material.tc_mat"
    assert recorder.inspector.pipeline_path == "/project/render.scene_pipeline"
    assert recorder.inspector.texture_path == "/project/albedo.png"
    assert recorder.inspector.mesh_path == "/project/mesh.stl"
    assert recorder.inspector.glb_path == "/project/model.glb"
