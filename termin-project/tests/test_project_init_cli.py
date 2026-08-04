from termin.project import init_cli


def test_init_cli_initializes_current_directory(tmp_path, monkeypatch, capsys):
    project_dir = tmp_path / "Demo"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)

    assert init_cli.main([]) == 0

    assert (project_dir / "Demo.terminproj").is_file()
    assert "Initialized Termin project" in capsys.readouterr().out


def test_init_cli_reports_conflict_without_traceback(tmp_path, monkeypatch, capsys):
    project_dir = tmp_path / "Demo"
    project_dir.mkdir()
    (project_dir / "scene.scene").write_text("preserve", encoding="utf-8")
    monkeypatch.chdir(project_dir)

    assert init_cli.main([]) == 2

    captured = capsys.readouterr()
    assert "Project path already exists" in captured.err
    assert "Traceback" not in captured.err
    assert (project_dir / "scene.scene").read_text(encoding="utf-8") == "preserve"
