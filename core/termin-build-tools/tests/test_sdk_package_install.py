from termin_build import sdk
from termin_build.package_manifest import PackageEntry


def test_extension_only_package_uses_regular_install_in_editable_mode(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    sdk_prefix = repo_root / "sdk"
    (sdk_prefix / "lib").mkdir(parents=True)
    (repo_root / "native-only").mkdir()
    packages = [
        PackageEntry(
            "native-only",
            "native-only",
            (),
            (),
            editable=False,
        )
    ]
    commands = []

    monkeypatch.setattr(sdk, "_sdk_packages", lambda _repo_root: packages)
    monkeypatch.setattr(sdk, "_python_bin", lambda: "python")
    monkeypatch.setattr(
        sdk,
        "_run",
        lambda command, **_kwargs: commands.append(command) or 0,
    )

    result = sdk.install_pip_packages(
        repo_root=repo_root,
        sdk_prefix=sdk_prefix,
        build_dir=repo_root / "build" / "Release",
        target_dir=None,
        editable=True,
        force=False,
    )

    assert result == 0
    assert len(commands) == 1
    assert "--no-deps" in commands[0]
    assert "-e" not in commands[0]
