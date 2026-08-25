from __future__ import annotations

from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TERMIN = REPOSITORY_ROOT / "sdk" / "bin" / "termin"


def test_installed_termin_help_lists_show_command():
    result = subprocess.run(
        [str(TERMIN), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "show <model.glb>" in result.stdout


def test_installed_termin_show_routes_to_model_viewer_help():
    result = subprocess.run(
        [str(TERMIN), "show", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usage: termin show" in result.stdout
    assert "orbit camera" in result.stdout
