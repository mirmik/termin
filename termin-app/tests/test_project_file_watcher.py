from pathlib import Path
from types import SimpleNamespace
from typing import Set

from termin.default_assets.render.texture_plugin import TextureImportPlugin
from termin.editor_core.project_file_watcher import ProjectFileWatcher
from termin.editor_core.file_processors import ComponentFileProcessor, ModuleFileProcessor, ModuleInputFileProcessor
from termin.project_modules.runtime import ProjectModulesRuntime
from termin_assets.plugin_preloader import PluginPreLoader
from termin_assets.project_file_watcher import FilePreLoader
from termin.project.settings import ProjectSettings, ProjectSettingsManager
from termin_assets import PreLoadResult
from termin_modules import ModuleKind, ModuleState


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
        self.last_error = ""
        self.reloaded_descriptors: list[Path] = []
        self.reloaded_paths: list[Path] = []
        self.dirty_paths: list[Path] = []

    def reload_descriptor(self, path: Path) -> str | None:
        self.reloaded_descriptors.append(Path(path))
        return "gameplay"

    def reload_modules_for_path(self, path: str) -> list[str]:
        self.reloaded_paths.append(Path(path))
        return ["gameplay"]

    def mark_modules_dirty_for_path(self, path: str) -> list[str]:
        self.dirty_paths.append(Path(path))
        return ["native_core"]


class RuntimeUnderTest(ProjectModulesRuntime):
    def __init__(self, records: list[object]) -> None:
        self._records = records
        self._dirty_module_reasons: dict[str, set[str]] = {}

    def records(self) -> list[object]:
        return list(self._records)


class ReloadRuntimeUnderTest(RuntimeUnderTest):
    def __init__(self, records: list[object], stale_modules: list[str] | None = None) -> None:
        super().__init__(records)
        self._closed = False
        self._stale_modules = stale_modules or []
        self.reloaded_modules: list[str] = []
        self.fail_modules: set[str] = set()

    def find(self, module_id: str):
        for record in self._records:
            if record.id == module_id:
                return record
        return None

    def stale_modules(self) -> list[str]:
        return list(self._stale_modules)

    def reload_module(self, module_id: str) -> bool:
        self.reloaded_modules.append(module_id)
        return module_id not in self.fail_modules


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


def test_module_file_processor_marks_pymodule_dirty(tmp_path: Path) -> None:
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

    assert runtime.dirty_paths == [descriptor]
    assert runtime.reloaded_descriptors == []
    assert reloaded == []


def test_module_file_processor_leaves_cpp_descriptors_to_policy_neutral_input_tracking() -> None:
    processor = ModuleFileProcessor(resource_manager=None)

    assert ".pymodule" in processor.extensions
    assert ".module" not in processor.extensions


def test_module_file_processor_marks_changes_without_auto_reload_mode(tmp_path: Path) -> None:
    descriptor = tmp_path / "gameplay.pymodule"
    descriptor.write_text("name: gameplay\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ModuleFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_file_changed(str(descriptor))

    assert runtime.dirty_paths == [descriptor]
    assert runtime.reloaded_descriptors == []


def test_module_file_processor_initial_scan_does_not_mark_pymodule_dirty(tmp_path: Path) -> None:
    descriptor = tmp_path / "gameplay.pymodule"
    descriptor.write_text("name: gameplay\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ModuleFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_initial_file_added(str(descriptor))

    assert runtime.dirty_paths == []
    assert processor.get_tracked_files() == {str(descriptor): set()}


def test_module_input_processor_marks_cpp_descriptor_dirty_without_reload(tmp_path: Path) -> None:
    descriptor = tmp_path / "native_core.module"
    descriptor.write_text("name: native_core\ntype: cpp\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ModuleInputFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_file_changed(str(descriptor))

    assert runtime.dirty_paths == [descriptor]
    assert runtime.reloaded_descriptors == []


def test_module_input_processor_marks_cpp_source_dirty_without_reload(tmp_path: Path) -> None:
    source = tmp_path / "native_core.cpp"
    source.write_text("extern \"C\" void module_init() {}\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ModuleInputFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_file_changed(str(source))

    assert runtime.dirty_paths == [source]
    assert runtime.reloaded_descriptors == []


def test_module_input_processor_initial_scan_does_not_mark_existing_sources_dirty(tmp_path: Path) -> None:
    source = tmp_path / "native_core.cpp"
    source.write_text("extern \"C\" void module_init() {}\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ModuleInputFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_initial_file_added(str(source))

    assert runtime.dirty_paths == []
    assert processor.get_tracked_files() == {str(source): set()}


def test_module_input_processor_live_created_source_marks_module_dirty(tmp_path: Path) -> None:
    source = tmp_path / "native_core.cpp"
    source.write_text("extern \"C\" void module_init() {}\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ModuleInputFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )

    processor.on_file_added(str(source))

    assert runtime.dirty_paths == [source]


def test_project_file_watcher_initial_scan_uses_initial_add_hook_for_module_inputs(tmp_path: Path) -> None:
    source = tmp_path / "native_core.cpp"
    source.write_text("extern \"C\" void module_init() {}\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ModuleInputFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)
    watcher._project_path = str(tmp_path)

    watcher._scan_directory(str(tmp_path))

    assert runtime.dirty_paths == []
    assert watcher.watched_files == {str(source)}


def test_project_file_watcher_live_created_module_input_marks_module_dirty(tmp_path: Path) -> None:
    source = tmp_path / "native_core.cpp"
    source.write_text("extern \"C\" void module_init() {}\n", encoding="utf-8")
    runtime = RecordingModulesRuntime()
    processor = ModuleInputFileProcessor(
        resource_manager=None,
        modules_runtime_provider=lambda: runtime,
    )
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)

    with watcher._lock:
        watcher._pending_changes[str(source)] = "created"

    watcher.poll()

    assert runtime.dirty_paths == [source]
    assert watcher.watched_files == {str(source)}


def test_project_modules_runtime_marks_cpp_module_dirty_for_native_input(tmp_path: Path) -> None:
    descriptor = tmp_path / "native_core.module"
    source = tmp_path / "src" / "native_core.cpp"
    source.parent.mkdir()
    descriptor.write_text("name: native_core\ntype: cpp\n", encoding="utf-8")
    source.write_text("extern \"C\" void module_init() {}\n", encoding="utf-8")
    runtime = RuntimeUnderTest(
        [
            SimpleNamespace(
                id="native_core",
                kind=ModuleKind.Cpp,
                descriptor_path=str(descriptor),
            )
        ]
    )

    assert runtime.mark_modules_dirty_for_path(source) == ["native_core"]

    dirty = runtime.dirty_modules()
    assert list(dirty) == ["native_core"]
    assert str(source) in dirty["native_core"][0]


def test_project_modules_runtime_ignores_cpp_build_directory_inputs(tmp_path: Path) -> None:
    descriptor = tmp_path / "native_core.module"
    generated = tmp_path / "build" / "generated.cpp"
    generated.parent.mkdir()
    descriptor.write_text("name: native_core\ntype: cpp\n", encoding="utf-8")
    generated.write_text("// generated\n", encoding="utf-8")
    runtime = RuntimeUnderTest(
        [
            SimpleNamespace(
                id="native_core",
                kind=ModuleKind.Cpp,
                descriptor_path=str(descriptor),
            )
        ]
    )

    assert runtime.mark_modules_dirty_for_path(generated) == []
    assert runtime.dirty_modules() == {}


def test_project_modules_runtime_marks_python_package_dirty(tmp_path: Path) -> None:
    descriptor = tmp_path / "gameplay.pymodule"
    package_file = tmp_path / "gameplay" / "components.py"
    package_file.parent.mkdir()
    descriptor.write_text("name: gameplay\ntype: python\n", encoding="utf-8")
    package_file.write_text("class Probe: pass\n", encoding="utf-8")
    runtime = RuntimeUnderTest(
        [
            SimpleNamespace(
                id="gameplay",
                kind=ModuleKind.Python,
                descriptor_path=str(descriptor),
                python_root=str(tmp_path),
                python_packages=["gameplay"],
            )
        ]
    )

    assert runtime.module_ids_for_path(package_file) == ["gameplay"]
    assert runtime.mark_modules_dirty_for_path(package_file) == ["gameplay"]
    dirty = runtime.dirty_modules()
    assert list(dirty) == ["gameplay"]
    assert str(package_file) in dirty["gameplay"][0]


def test_project_modules_runtime_reload_dirty_modules_coalesces_loaded_dependents(tmp_path: Path) -> None:
    core_dir = tmp_path / "core"
    leaf_dir = tmp_path / "leaf"
    core_dir.mkdir()
    leaf_dir.mkdir()
    core_descriptor = core_dir / "core.module"
    leaf_descriptor = leaf_dir / "leaf.module"
    core_descriptor.write_text("name: core\ntype: cpp\n", encoding="utf-8")
    leaf_descriptor.write_text("name: leaf\ntype: cpp\ndependencies: [core]\n", encoding="utf-8")
    core_source = core_dir / "core.cpp"
    leaf_source = leaf_dir / "leaf.cpp"
    core_source.write_text("// core\n", encoding="utf-8")
    leaf_source.write_text("// leaf\n", encoding="utf-8")

    runtime = ReloadRuntimeUnderTest(
        [
            SimpleNamespace(
                id="core",
                kind=ModuleKind.Cpp,
                descriptor_path=str(core_descriptor),
                dependencies=[],
                state=ModuleState.Loaded,
            ),
            SimpleNamespace(
                id="leaf",
                kind=ModuleKind.Cpp,
                descriptor_path=str(leaf_descriptor),
                dependencies=["core"],
                state=ModuleState.Loaded,
            ),
        ]
    )

    assert runtime.mark_modules_dirty_for_path(core_source) == ["core"]
    assert runtime.mark_modules_dirty_for_path(leaf_source) == ["leaf"]

    assert runtime.reload_dirty_modules()

    assert runtime.reloaded_modules == ["core"]
    assert runtime.dirty_modules() == {}


def test_component_processor_marks_package_python_files_dirty(tmp_path: Path) -> None:
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

    assert runtime.dirty_paths == [component]
    assert runtime.reloaded_paths == []


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
        assert processor.dirty_component_paths() == (str(script_path),)
        assert resource_manager.get_component(component_name) is None

        assert processor.reload_dirty_components()

        assert resource_manager.get_component(component_name) is not None
        assert ComponentRegistry.instance().has(component_name)
        assert processor.get_tracked_files() == {str(script_path): {component_name}}
        assert processor.dirty_component_paths() == ()
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
        processor.on_initial_file_added(str(script_path))

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
        processor.on_initial_file_added(str(script_path))
        old_cls = resource_manager.get_component(component_name)
        assert old_cls is not None
        instance = old_cls()

        write_component(2)
        processor.on_file_changed(str(script_path))
        assert processor.dirty_component_paths() == (str(script_path),)
        assert resource_manager.get_component(component_name) is old_cls

        assert processor.reload_dirty_components()

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


def test_component_processor_reloads_dependents_after_loose_helper_change(tmp_path: Path) -> None:
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.scene import ComponentRegistry

    component_name = "BrowserLooseHelperCascadeComponent"
    scripts_dir = tmp_path / "Scripts"
    scripts_dir.mkdir()
    helper_path = scripts_dir / "helper_values.py"
    script_path = scripts_dir / f"{component_name}.py"

    def write_helper(value: int) -> None:
        helper_path.write_text(f"HELPER_VALUE = {value}\n", encoding="utf-8")

    write_helper(1)
    script_path.write_text(
        "\n".join(
            [
                "from termin.scene import PythonComponent",
                "from .helper_values import HELPER_VALUE",
                "",
                "",
                f"class {component_name}(PythonComponent):",
                "    value = HELPER_VALUE",
                "",
            ]
        ),
        encoding="utf-8",
    )

    resource_manager = DefaultResourceManager()
    reloaded: list[tuple[str, str]] = []
    processor = ComponentFileProcessor(
        resource_manager,
        on_resource_reloaded=lambda resource_type, name: reloaded.append((resource_type, name)),
    )
    processor.set_project_root(str(tmp_path))

    try:
        processor.on_initial_file_added(str(helper_path))
        processor.on_initial_file_added(str(script_path))
        old_cls = resource_manager.get_component(component_name)
        assert old_cls is not None
        assert old_cls.value == 1

        write_helper(5)
        processor.on_file_changed(str(helper_path))
        assert processor.dirty_component_paths() == (str(helper_path),)
        assert resource_manager.get_component(component_name) is old_cls

        assert processor.reload_dirty_components()

        new_cls = resource_manager.get_component(component_name)
        assert new_cls is not None
        assert new_cls is not old_cls
        assert new_cls.value == 5
        assert reloaded == [
            ("component", component_name),
            ("component", component_name),
        ]
    finally:
        ComponentRegistry.instance().unregister_python(component_name)


def test_component_processor_reloads_cross_dir_termin_project_dependents(tmp_path: Path) -> None:
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin.scene import ComponentRegistry

    component_name = "BrowserLooseCrossDirHelperCascadeComponent"
    scripts_dir = tmp_path / "Scripts"
    shared_dir = tmp_path / "Shared"
    scripts_dir.mkdir()
    shared_dir.mkdir()
    helper_path = shared_dir / "values.py"
    script_path = scripts_dir / f"{component_name}.py"

    def write_helper(value: int) -> None:
        helper_path.write_text(f"SHARED_VALUE = {value}\n", encoding="utf-8")

    write_helper(3)
    script_path.write_text(
        "\n".join(
            [
                "from termin.scene import PythonComponent",
                "from termin_project.Shared.values import SHARED_VALUE",
                "",
                "",
                f"class {component_name}(PythonComponent):",
                "    value = SHARED_VALUE",
                "",
            ]
        ),
        encoding="utf-8",
    )

    resource_manager = DefaultResourceManager()
    processor = ComponentFileProcessor(resource_manager)
    processor.set_project_root(str(tmp_path))

    try:
        processor.on_initial_file_added(str(helper_path))
        processor.on_initial_file_added(str(script_path))
        old_cls = resource_manager.get_component(component_name)
        assert old_cls is not None
        assert old_cls.value == 3

        write_helper(8)
        processor.on_file_changed(str(helper_path))
        assert processor.dirty_component_paths() == (str(helper_path),)
        assert resource_manager.get_component(component_name) is old_cls

        assert processor.reload_dirty_components()

        new_cls = resource_manager.get_component(component_name)
        assert new_cls is not None
        assert new_cls is not old_cls
        assert new_cls.value == 8
    finally:
        ComponentRegistry.instance().unregister_python(component_name)


def test_project_file_watcher_created_event_marks_loose_python_components_dirty(tmp_path: Path) -> None:
    script_path = tmp_path / "Scripts" / "EnemyComponent.py"
    script_path.parent.mkdir()
    script_path.write_text("class EnemyComponent: pass\n", encoding="utf-8")

    resource_manager = RecordingComponentResourceManager()
    processor = ComponentFileProcessor(resource_manager)
    watcher = ProjectFileWatcher()
    watcher.register_processor(processor)

    _queue_change(watcher, script_path, "created")
    watcher.poll()

    assert resource_manager.scanned_paths == []
    assert watcher.watched_files == {str(script_path)}
    assert processor.get_tracked_files() == {}
    assert processor.dirty_component_paths() == (str(script_path),)


def test_project_file_watcher_modified_event_marks_loose_python_components_dirty(tmp_path: Path) -> None:
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

    assert resource_manager.scanned_paths == []
    assert resource_manager.scan_options == []
    assert processor.get_tracked_files() == {}
    assert processor.dirty_component_paths() == (str(script_path),)
    assert reloaded == []


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
        self.unregistered: list[PreLoadResult] = []

    def register_file(self, result: PreLoadResult) -> None:
        self.registered.append(result)

    def reload_file(self, result: PreLoadResult) -> None:
        self.reloaded.append(result)

    def unregister_file(self, result: PreLoadResult) -> None:
        self.unregistered.append(result)


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
    assert [result.path for result in rm.unregistered] == [str(texture_path)]
    assert rm.external_assets.removed_paths == [str(texture_path)]


def test_project_file_watcher_rescan_preserves_existing_plugin_asset(tmp_path: Path, monkeypatch) -> None:
    _set_project_settings(monkeypatch, ProjectSettings())

    texture_path = tmp_path / "Textures" / "Stable.png"
    texture_path.parent.mkdir()
    texture_path.write_bytes(b"png")
    texture_path.with_name(texture_path.name + ".meta").write_text(
        '{"uuid": "texture-stable-uuid"}',
        encoding="utf-8",
    )

    rm = RecordingResourceManager()
    preloader = PluginPreLoader(TextureImportPlugin(), rm)
    watcher = ProjectFileWatcher()
    watcher.register_processor(preloader)
    watcher._project_path = str(tmp_path)
    watcher._scan_directory(str(tmp_path))

    registered_before = list(rm.registered)
    reloaded_before = list(rm.reloaded)

    watcher.rescan()

    assert watcher.watched_files == {
        str(texture_path),
        str(texture_path.with_name(texture_path.name + ".meta")),
    }
    assert preloader.get_tracked_files() == {str(texture_path): {"Stable"}}
    assert rm.registered == registered_before
    assert rm.reloaded == reloaded_before
    assert rm.unregistered == []
    assert rm.external_assets.removed_paths == []


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
    assert [result.path for result in rm.unregistered] == [str(texture_path)]
