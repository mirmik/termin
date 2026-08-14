from termin.artifacts import clear_artifact_store, current_artifact_store
from termin.editor_core.project_context import current_project_path, set_current_project_path


def test_project_context_owns_artifact_store_instance(tmp_path):
    clear_artifact_store()
    set_current_project_path(tmp_path)

    store = current_artifact_store()
    assert store is not None
    assert store.project_root == tmp_path.resolve()
    assert store.root == tmp_path.resolve() / ".termin" / "artifacts"
    assert current_project_path() == tmp_path.resolve()

    set_current_project_path(None)
    assert current_artifact_store() is None
    assert current_project_path() is None
