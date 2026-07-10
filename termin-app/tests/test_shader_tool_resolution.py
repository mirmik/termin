import os
from pathlib import Path

import pytest

from termin.editor_core import shader_runtime


def test_editor_shader_runtime_uses_local_app_data_cache_root_on_windows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        pytest.skip("Windows LOCALAPPDATA shader cache path")

    local_app_data = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("TERMIN_SDK_SHADER_CACHE_ROOT", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    assert (
        shader_runtime._sdk_shader_cache_root()
        == local_app_data / "Termin" / "Cache" / "sdk-shaders"
    )
