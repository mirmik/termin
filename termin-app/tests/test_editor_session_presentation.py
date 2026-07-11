from termin.editor_core.editor_log_model import EditorLogModel
from termin.editor_core.editor_session_presentation import EditorSessionPresentationModel


def test_editor_session_presentation_keeps_project_scene_mode_and_message():
    model = EditorSessionPresentationModel()
    snapshot = model.update(project_name="ChronoSquad", scene_label="scene4")
    assert snapshot.status_text == "ChronoSquad | scene4 | Edit | Ready"
    assert snapshot.window_title == "Termin Editor - ChronoSquad [scene4]"
    snapshot = model.update(playing=True, message="Build succeeded")
    assert snapshot.status_text == "ChronoSquad | scene4 | Play | Build succeeded"
    assert snapshot.window_title.endswith("- PLAYING")


def test_editor_log_is_bounded_and_clearable():
    model = EditorLogModel(max_lines=2)
    model.append("one\ntwo")
    model.append("three")
    assert model.text == "two\nthree"
    model.clear()
    assert model.text == ""
