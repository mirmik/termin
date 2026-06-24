from __future__ import annotations

from pathlib import Path
from typing import Callable

from termin.editor_core.dialog_service import DialogService
from termin.editor_core.project_operations import ProjectOperations, _SHADER_TEMPLATE
from termin.materials import parse_shader_text


class FakeDialogService(DialogService):
    def __init__(self) -> None:
        self.input_result: str | None = None
        self.errors: list[tuple[str, str]] = []

    def show_error(
        self,
        title: str,
        message: str,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.errors.append((title, message))
        if on_close is not None:
            on_close()

    def show_input(
        self,
        title: str,
        message: str,
        default: str,
        on_result: Callable[[str | None], None],
    ) -> None:
        on_result(self.input_result)

    def show_choice(
        self,
        title: str,
        message: str,
        choices: list[str],
        on_result: Callable[[str | None], None],
        default: str | None = None,
        cancel: str | None = None,
    ) -> None:
        on_result(default)


def test_rename_file_moves_companion_meta(tmp_path: Path) -> None:
    asset = tmp_path / "Grenade.png"
    meta = tmp_path / "Grenade.png.meta"
    asset.write_text("image", encoding="utf-8")
    meta.write_text('{"uuid": "texture-uuid"}', encoding="utf-8")

    dialog = FakeDialogService()
    dialog.input_result = "GrenadeRenamed.png"
    refreshed = []

    ProjectOperations(dialog).rename_item(asset, lambda: refreshed.append(True))

    assert not asset.exists()
    assert not meta.exists()
    assert (tmp_path / "GrenadeRenamed.png").read_text(encoding="utf-8") == "image"
    assert (tmp_path / "GrenadeRenamed.png.meta").read_text(encoding="utf-8") == '{"uuid": "texture-uuid"}'
    assert refreshed == [True]
    assert dialog.errors == []


def test_rename_file_rejects_existing_target_meta(tmp_path: Path) -> None:
    asset = tmp_path / "Grenade.png"
    meta = tmp_path / "Grenade.png.meta"
    target_meta = tmp_path / "GrenadeRenamed.png.meta"
    asset.write_text("image", encoding="utf-8")
    meta.write_text("source-meta", encoding="utf-8")
    target_meta.write_text("target-meta", encoding="utf-8")

    dialog = FakeDialogService()
    dialog.input_result = "GrenadeRenamed.png"
    refreshed = []

    ProjectOperations(dialog).rename_item(asset, lambda: refreshed.append(True))

    assert asset.read_text(encoding="utf-8") == "image"
    assert meta.read_text(encoding="utf-8") == "source-meta"
    assert target_meta.read_text(encoding="utf-8") == "target-meta"
    assert refreshed == []
    assert dialog.errors == [("Error", "Meta file 'GrenadeRenamed.png.meta' already exists.")]


def test_new_shader_template_is_current_slang_shader() -> None:
    assert "@language slang" in _SHADER_TEMPLATE
    assert "#version" not in _SHADER_TEMPLATE

    parsed = parse_shader_text(_SHADER_TEMPLATE)

    assert parsed.language == "slang"
    assert parsed.program == "NewShader"
    assert parsed.phases[0].stages["vertex"].source
    assert parsed.phases[0].stages["fragment"].source
