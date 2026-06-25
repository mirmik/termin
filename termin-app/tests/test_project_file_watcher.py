from pathlib import Path
from typing import Set

from termin.default_assets.render.texture_plugin import TextureImportPlugin
from termin.assets.project_file_watcher import ProjectFileWatcher
from termin.editor_core.file_processors import ComponentFileProcessor, ModuleFileProcessor
from termin_assets.plugin_preloader import PluginPreLoader
from termin_assets.project_file_watcher import FilePreLoader
from termin.project.settings import ProjectSettings, ProjectSettingsManager
from termin_assets import PreLoadResult


class RecordingPreLoader(FilePreLoader):
    def __init__(self) -> None:
        super().__init__(resource_manager=None)
        self.changed: list[str] = []

    @property
    def extensions(self) -> Set[str]:
        return {".shader"}

    @property
    def resource_type(self) -> str:
        return "shader"

    def on_file_changed(self, path: str) -> None:
        self.changed.append(path)


class RecordingGlslPreLoader(RecordingPreLoader):
    @property
    def extensions(self) -> Set[str]:
        return {".glsl"}

    @property
    def resource_type(self) -> str:
        return "glsl"


class RecordingPythonPreLoader(RecordingPreLoader):
    @property
    def extensions(self) -> Set[str]:
        return {".py"}

    @property
    def resource_type(self) -> str:
        return "python"


class RecordingModulesRuntime:
    def __init__(self) -> None:
        self.auto_reload_enabled = True
        self.last_error = ""
        self.reloaded_descriptors: list[Path] = []
        self.reloaded_paths: list[Path] = []

    def reload_descriptor(self, path: Path) -> str | None:
        self.reloaded_descriptors.append(Path(path))
        return "gameplay"

    def reload_modules_for_path(self, path: str) -> list[str]:
        self.reloaded_paths.append(Path(path))
        return ["gameplay"]


class FailingComponentResourceManager:
    def scan_components(self, paths: list[str]) -> list[str]:
        raise AssertionError(f"package component files must not be scanned directly: {paths}")


class RecordingComponentResourceManager:
    def __init__(self) -> None:
        self.scanned_paths: list[list[str]] = []
        self.scan_options: list[tuple[str | None, str | None]] = []

    def scan_components(
        self,
        paths: list[str],
        *,
        project_root: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        self.scanned_paths.append(paths)
        self.scan_options.append((project_root, namespace))
        return [Path(paths[0]).stem]


def test_project_file_watcher_poll_processes_pending_changes(tmp_path: Path) -> None:
    shader_path = tmp_path / "HotReload.shader"
    shader_path.write_text("@program HotReload\n@language slang\n", encoding="utf-8")

    processor = RecordingPreLoader()
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)

    with watcher._lock:
        watcher._pending_changes[str(shader_path)] = "modified"

    watcher.poll()

    assert processor.changed == [str(shader_path)]


def test_module_file_processor_reloads_pymodule_when_auto_reload_enabled(tmp_path: Path) -> None:
    descriptor = tmp_path / "gameplay.pymodule"
    descriptor.write_text("name: gameplay\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    reloaded: list[tuple[str, str]] = []
    processor = ModuleFileProcessor(
        resource_manager=None,
        on_resource_reloaded=lambda resource_type, name: reloaded.append((resource_type, name)),
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_file_changed(str(descriptor))

    assert runtime.reloaded_descriptors == [descriptor]
    assert reloaded == [("module", "gameplay")]


def test_module_file_processor_ignores_changes_when_auto_reload_disabled(tmp_path: Path) -> None:
    descriptor = tmp_path / "gameplay.pymodule"
    descriptor.write_text("name: gameplay\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    runtime.auto_reload_enabled = False
    processor = ModuleFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_file_changed(str(descriptor))

    assert runtime.reloaded_descriptors == []


def test_component_processor_routes_package_python_files_to_module_reload(tmp_path: Path) -> None:
    package = tmp_path / "gameplay"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    component = package / "components.py"
    component.write_text("class Probe: pass\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ComponentFileProcessor(
        FailingComponentResourceManager(),
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_file_changed(str(component))

    assert runtime.reloaded_paths == [component]


def test_project_file_watcher_initial_scan_loads_loose_python_components(tmp_path: Path) -> None:
    script_path = tmp_path / "Scripts" / "PlayerComponent.py"
    script_path.parent.mkdir()
    script_path.write_text("class PlayerComponent: pass\n", encoding="utf-8")

    resource_manager = RecordingComponentResourceManager()
    reloaded: list[tuple[str, str]] = []
    processor = ComponentFileProcessor(
        resource_manager,
        on_resource_reloaded=lambda resource_type, name: reloaded.append((resource_type, name)),
    )
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._project_path = str(tmp_path)

    watcher._scan_directory(str(tmp_path))

    assert resource_manager.scanned_paths == [[str(script_path)]]
    assert watcher.watched_files == {str(script_path)}
    assert processor.get_tracked_files() == {str(script_path): {"PlayerComponent"}}
    assert reloaded == [("component", "PlayerComponent")]


def test_component_processor_registers_real_loose_python_component(tmp_path: Path) -> None:
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.scene import ComponentRegistry

    component_name = "BrowserLooseProbeComponent"
    script_path = tmp_path / "Scripts" / f"{component_name}.py"
    script_path.parent.mkdir()
    script_path.write_text(
        "\n".join(
            [
                "from termin.scene import PythonComponent",
                "",
                "",
                f"class {component_name}(PythonComponent):",
                "    pass",
                "",
            ]
        ),
        encoding="utf-8",
    )

    resource_manager = DefaultResourceManager()
    processor = ComponentFileProcessor(resource_manager)

    try:
        processor.on_file_added(str(script_path))

        assert resource_manager.get_component(component_name) is not None
        assert ComponentRegistry.instance().has(component_name)
        assert processor.get_tracked_files() == {str(script_path): {component_name}}
    finally:
        ComponentRegistry.instance().unregister_python(component_name)


def test_component_processor_loads_loose_python_in_project_namespace(tmp_path: Path) -> None:
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.scene import ComponentRegistry

    component_name = "BrowserLooseNamespacedComponent"
    scripts_dir = tmp_path / "Scripts"
    shared_dir = tmp_path / "Shared"
    scripts_dir.mkdir()
    shared_dir.mkdir()
    (scripts_dir / "helpers.py").write_text("SAME_DIR_VALUE = 2\n", encoding="utf-8")
    (shared_dir / "values.py").write_text("SHARED_VALUE = 5\n", encoding="utf-8")
    script_path = scripts_dir / f"{component_name}.py"
    script_path.write_text(
        "\n".join(
            [
                "from termin.scene import PythonComponent",
                "from .helpers import SAME_DIR_VALUE",
                "from termin_project.Shared.values import SHARED_VALUE",
                "",
                "",
                f"class {component_name}(PythonComponent):",
                "    value = SAME_DIR_VALUE + SHARED_VALUE",
                "",
            ]
        ),
        encoding="utf-8",
    )

    resource_manager = DefaultResourceManager()
    processor = ComponentFileProcessor(resource_manager)
    processor.set_project_root(str(tmp_path))

    try:
        processor.on_file_added(str(script_path))

        cls = resource_manager.get_component(component_name)
        assert cls is not None
        assert cls.__module__ == f"termin_project.Scripts.{component_name}"
        assert cls.value == 7
        assert ComponentRegistry.instance().has(component_name)
    finally:
        ComponentRegistry.instance().unregister_python(component_name)


def test_component_processor_reloads_real_loose_python_component_class(tmp_path: Path) -> None:
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.scene import ComponentRegistry

    component_name = "BrowserLooseReloadProbeComponent"
    script_path = tmp_path / "Scripts" / f"{component_name}.py"
    script_path.parent.mkdir()

    def write_component(version: int) -> None:
        script_path.write_text(
            "\n".join(
                [
                    "from termin.scene import PythonComponent",
                    "",
                    "",
                    f"class {component_name}(PythonComponent):",
                    f"    version = {version}",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    write_component(1)
    resource_manager = DefaultResourceManager()
    reloaded: list[tuple[str, str]] = []
    processor = ComponentFileProcessor(
        resource_manager,
        on_resource_reloaded=lambda resource_type, name: reloaded.append((resource_type, name)),
    )

    try:
        processor.on_file_added(str(script_path))
        old_cls = resource_manager.get_component(component_name)
        assert old_cls is not None
        instance = old_cls()

        write_component(2)
        processor.on_file_changed(str(script_path))

        new_cls = resource_manager.get_component(component_name)
        assert new_cls is not None
        assert new_cls is not old_cls
        assert new_cls.version == 2
        assert type(instance) is new_cls
        assert reloaded == [
            ("component", component_name),
            ("component", component_name),
        ]
    finally:
        ComponentRegistry.instance().unregister_python(component_name)


def test_project_file_watcher_created_event_loads_loose_python_components(tmp_path: Path) -> None:
    script_path = tmp_path / "Scripts" / "EnemyComponent.py"
    script_path.parent.mkdir()
    script_path.write_text("class EnemyComponent: pass\n", encoding="utf-8")

    resource_manager = RecordingComponentResourceManager()
    processor = ComponentFileProcessor(resource_manager)
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)

    _queue_change(watcher, script_path, "created")
    watcher.poll()

    assert resource_manager.scanned_paths == [[str(script_path)]]
    assert resource_manager.scan_options == [(None, None)]
    assert watcher.watched_files == {str(script_path)}
    assert processor.get_tracked_files() == {str(script_path): {"EnemyComponent"}}


def test_project_file_watcher_modified_event_reloads_loose_python_components(tmp_path: Path) -> None:
    script_path = tmp_path / "Scripts" / "InputComponent.py"
    script_path.parent.mkdir()
    script_path.write_text("class InputComponent: pass\n", encoding="utf-8")

    resource_manager = RecordingComponentResourceManager()
    reloaded: list[tuple[str, str]] = []
    processor = ComponentFileProcessor(
        resource_manager,
        on_resource_reloaded=lambda resource_type, name: reloaded.append((resource_type, name)),
    )
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)

    _queue_change(watcher, script_path, "modified")
    watcher.poll()

    assert resource_manager.scanned_paths == [[str(script_path)]]
    assert resource_manager.scan_options == [(None, None)]
    assert processor.get_tracked_files() == {str(script_path): {"InputComponent"}}
    assert reloaded == [("component", "InputComponent")]


def test_project_file_watcher_ignores_service_termin_directory_events(tmp_path: Path) -> None:
    artifact_path = (
        tmp_path
        / ".termin"
        / "shader-artifacts"
        / "shaders"
        / "opengl"
        / "compiled.frag.glsl"
    )
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("glsl", encoding="utf-8")
    artifact_path.with_name(artifact_path.name + ".artifact").write_text(
        "artifact_metadata_schema=1\n",
        encoding="utf-8",
    )

    processor = RecordingGlslPreLoader()
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._project_path = str(tmp_path)

    watcher._scan_directory(str(tmp_path))
    watcher._enqueue_change(str(artifact_path), "modified")
    watcher._enqueue_change(str(artifact_path.with_name(artifact_path.name + ".artifact")), "modified")

    assert watcher.watched_files == set()
    assert processor.changed == []
    with watcher._lock:
        assert watcher._pending_changes == {}


class RecordingAssetCatalog:
    def __init__(self) -> None:
        self.removed_paths: list[str] = []

    def remove_path(self, path: str) -> None:
        self.removed_paths.append(path)


class RecordingResourceManager:
    def __init__(self) -> None:
        self.external_assets = RecordingAssetCatalog()
        self.registered: list[PreLoadResult] = []
        self.reloaded: list[PreLoadResult] = []

    def register_file(self, result: PreLoadResult) -> None:
        self.registered.append(result)

    def reload_file(self, result: PreLoadResult) -> None:
        self.reloaded.append(result)


def _queue_change(watcher: ProjectFileWatcher, path: Path, kind: str) -> None:
    with watcher._lock:
        watcher._pending_changes[str(path)] = kind


def _set_project_settings(monkeypatch, settings: ProjectSettings) -> None:
    manager = ProjectSettingsManager()
    manager._settings = settings
    monkeypatch.setattr(ProjectSettingsManager, "_instance", manager)


def test_project_file_watcher_initial_scan_registers_plugin_assets(tmp_path: Path) -> None:
    texture_path = tmp_path / "Textures" / "Albedo.png"
    texture_path.parent.mkdir()
    texture_path.write_bytes(b"png")
    texture_path.with_name(texture_path.name + ".meta").write_text(
        '{"uuid": "texture-scan-uuid"}',
        encoding="utf-8",
    )

    rm = RecordingResourceManager()
    preloader = PluginPreLoader(TextureImportPlugin(), rm)
    watcher = ProjectFileWatcher()
    watcher.register_processor(preloader)

    watcher._project_path = str(tmp_path)
    watcher._scan_directory(str(tmp_path))

    assert [result.resource_type for result in rm.registered] == ["texture"]
    assert rm.registered[0].path == str(texture_path)
    assert rm.registered[0].uuid == "texture-scan-uuid"
    assert preloader.get_tracked_files() == {str(texture_path): {"Albedo"}}


def test_project_file_watcher_initial_scan_ignores_project_setting_paths(tmp_path: Path, monkeypatch) -> None:
    _set_project_settings(
        monkeypatch,
        ProjectSettings(ignored_resource_paths=["Ignored", "LooseIgnored.png"]),
    )

    keep_path = tmp_path / "Textures" / "Keep.png"
    keep_path.parent.mkdir()
    keep_path.write_bytes(b"png")
    keep_path.with_name(keep_path.name + ".meta").write_text(
        '{"uuid": "keep-texture-uuid"}',
        encoding="utf-8",
    )

    ignored_dir_path = tmp_path / "Ignored" / "Skip.png"
    ignored_dir_path.parent.mkdir()
    ignored_dir_path.write_bytes(b"png")
    ignored_dir_path.with_name(ignored_dir_path.name + ".meta").write_text(
        '{"uuid": "ignored-dir-texture-uuid"}',
        encoding="utf-8",
    )

    ignored_file_path = tmp_path / "LooseIgnored.png"
    ignored_file_path.write_bytes(b"png")
    ignored_file_path.with_name(ignored_file_path.name + ".meta").write_text(
        '{"uuid": "ignored-file-texture-uuid"}',
        encoding="utf-8",
    )

    rm = RecordingResourceManager()
    preloader = PluginPreLoader(TextureImportPlugin(), rm)
    watcher = ProjectFileWatcher()
    watcher.register_processor(preloader)

    watcher._project_path = str(tmp_path)
    watcher._scan_directory(str(tmp_path))

    assert [result.path for result in rm.registered] == [str(keep_path)]
    assert preloader.get_tracked_files() == {str(keep_path): {"Keep"}}


def test_project_file_watcher_initial_scan_ignores_python_files_in_project_setting_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _set_project_settings(monkeypatch, ProjectSettings(ignored_resource_paths=["tests"]))

    script_path = tmp_path / "Scripts" / "PlayerComponent.py"
    script_path.parent.mkdir()
    script_path.write_text("class PlayerComponent: pass\n", encoding="utf-8")

    test_script_path = tmp_path / "tests" / "test_player_component.py"
    test_script_path.parent.mkdir()
    test_script_path.write_text("class TestOnlyComponent: pass\n", encoding="utf-8")

    processor = RecordingPythonPreLoader()
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)

    watcher._project_path = str(tmp_path)
    watcher._scan_directory(str(tmp_path))

    assert watcher.watched_files == {str(script_path)}


def test_project_file_watcher_rescan_removes_newly_ignored_plugin_asset(tmp_path: Path, monkeypatch) -> None:
    _set_project_settings(monkeypatch, ProjectSettings())

    texture_path = tmp_path / "Generated" / "Albedo.png"
    texture_path.parent.mkdir()
    texture_path.write_bytes(b"png")
    texture_path.with_name(texture_path.name + ".meta").write_text(
        '{"uuid": "texture-generated-uuid"}',
        encoding="utf-8",
    )

    rm = RecordingResourceManager()
    preloader = PluginPreLoader(TextureImportPlugin(), rm)
    watcher = ProjectFileWatcher()
    watcher.register_processor(preloader)
    watcher._project_path = str(tmp_path)
    watcher._scan_directory(str(tmp_path))

    assert str(texture_path) in watcher.watched_files
    assert preloader.get_tracked_files() == {str(texture_path): {"Albedo"}}

    _set_project_settings(monkeypatch, ProjectSettings(ignored_resource_paths=["Generated"]))
    watcher.rescan()

    assert str(texture_path) not in watcher.watched_files
    assert preloader.get_tracked_files() == {}
    assert rm.external_assets.removed_paths == [str(texture_path)]


def test_project_file_watcher_created_file_registers_plugin_asset(tmp_path: Path) -> None:
    texture_path = tmp_path / "Albedo.png"
    texture_path.write_bytes(b"png")
    texture_path.with_name(texture_path.name + ".meta").write_text(
        '{"uuid": "texture-created-uuid"}',
        encoding="utf-8",
    )

    rm = RecordingResourceManager()
    watcher = ProjectFileWatcher()
    watcher.register_processor(PluginPreLoader(TextureImportPlugin(), rm))
    _queue_change(watcher, texture_path, "created")

    watcher.poll()

    assert [result.uuid for result in rm.registered] == ["texture-created-uuid"]
    assert rm.registered[0].path == str(texture_path)
    assert rm.reloaded == []


def test_project_file_watcher_modified_file_reloads_plugin_asset(tmp_path: Path) -> None:
    texture_path = tmp_path / "Albedo.png"
    texture_path.write_bytes(b"png")
    texture_path.with_name(texture_path.name + ".meta").write_text(
        '{"uuid": "texture-modified-uuid"}',
        encoding="utf-8",
    )

    rm = RecordingResourceManager()
    watcher = ProjectFileWatcher()
    watcher.register_processor(PluginPreLoader(TextureImportPlugin(), rm))
    _queue_change(watcher, texture_path, "modified")

    watcher.poll()

    assert rm.registered == []
    assert [result.uuid for result in rm.reloaded] == ["texture-modified-uuid"]
    assert rm.reloaded[0].path == str(texture_path)


def test_project_file_watcher_meta_change_reloads_resource_file(tmp_path: Path) -> None:
    texture_path = tmp_path / "Albedo.png"
    meta_path = tmp_path / "Albedo.png.meta"
    texture_path.write_bytes(b"png")
    meta_path.write_text('{"uuid": "texture-meta-uuid"}', encoding="utf-8")

    rm = RecordingResourceManager()
    watcher = ProjectFileWatcher()
    watcher.register_processor(PluginPreLoader(TextureImportPlugin(), rm))
    _queue_change(watcher, meta_path, "modified")

    watcher.poll()

    assert rm.registered == []
    assert [result.uuid for result in rm.reloaded] == ["texture-meta-uuid"]
    assert rm.reloaded[0].path == str(texture_path)


def test_project_file_watcher_deleted_file_clears_plugin_tracking(tmp_path: Path) -> None:
    texture_path = tmp_path / "Albedo.png"
    texture_path.write_bytes(b"png")

    rm = RecordingResourceManager()
    preloader = PluginPreLoader(TextureImportPlugin(), rm)
    watcher = ProjectFileWatcher()
    watcher.register_processor(preloader)
    preloader.on_file_added(str(texture_path))

    assert preloader.get_tracked_files() == {str(texture_path): {"Albedo"}}

    texture_path.unlink()
    _queue_change(watcher, texture_path, "deleted")

    watcher.poll()

    assert preloader.get_tracked_files() == {}
