import importlib
import os
import pathlib
import sys
import pytest

import termin.visualization.core.world as world_module

from termin.visualization.platform.backends import (
    set_default_graphics_backend,
    set_default_window_backend,
)

from termin.visualization.platform.backends.nop_graphics import NOPGraphicsBackend
from termin.visualization.platform.backends.nop_window import NOPWindowBackend
from termin.visualization.render.framegraph.passes.present import PresentToScreenPass


def collect_example_modules():
    """
    Собирает список модулей из examples/visual/*.py,
    которые содержат функцию main().
    """
    examples_dir = pathlib.Path("examples/visual")
    modules = []

    for file in sorted(examples_dir.glob("*.py")):
        if file.stem == "__init__":
            continue
        if file.stem == "qt_embed":
            # Qt-пример требует полноценной оконной среды, пропускаем в автоматических тестах.
            continue
        modname = "examples.visual." + file.stem
        modules.append(modname)

    return modules


@pytest.mark.parametrize("module_name", collect_example_modules())
def test_example_runs_one_frame(module_name, monkeypatch):
    """
    Тест запускает каждый example/*.py один раз с NOP-бекэндами
    и завершает его после первого кадра.
    """

    # --- 1. Завершать визуализацию после первого рендера ---
    monkeypatch.setattr(world_module, "CLOSE_AFTER_FIRST_FRAME", True)

    # --- 2. Врубить NOP-бекэнды ---
    set_default_graphics_backend(NOPGraphicsBackend())
    set_default_window_backend(NOPWindowBackend())

    # --- 2.1. Сбросить статические шейдеры (могли быть скомпилированы с другим бэкендом) ---
    PresentToScreenPass._shader = None

    # --- 3. Перехват Texture.from_file, чтобы не грузить реальные картинки ---
    # import termin.visualization.render.texture as texture_mod
    # monkeypatch.setattr(
    #     texture_mod.Texture,
    #     "from_file",
    #     lambda path: texture_mod.Texture(image_data=None, size=(1, 1)),
    # )

    # --- 4. Перехват FontTextureAtlas, чтобы не загружать реальные TTF ---
    # from termin.visualization.ui.font import FontTextureAtlas

    # def fake_font_init(self, *a, **kw):
    #     self.tex = None

    # monkeypatch.setattr(FontTextureAtlas, "__init__", fake_font_init)
    # monkeypatch.setattr(FontTextureAtlas, "__getattr__", lambda *a, **k: None)

    # --- 5. Импортируем модуль и запускаем его main() ---
    module = importlib.import_module(module_name)
    module.main()
