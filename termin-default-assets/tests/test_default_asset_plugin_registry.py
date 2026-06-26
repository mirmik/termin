import ast
from pathlib import Path


DEFAULT_ASSET_PLUGIN_SETUP_FILES = (
    "termin-default-assets/setup.py",
    "termin-glb/setup.py",
    "termin-prefab/setup.py",
)

EXPECTED_PLUGIN_TYPES = {
    "audio_clip",
    "glb",
    "glsl",
    "material",
    "mesh",
    "navmesh",
    "pipeline",
    "prefab",
    "scene_pipeline",
    "shader",
    "texture",
    "ui",
    "voxel_grid",
}

EXPECTED_IMPORT_EXTENSIONS = {
    ".glb": "glb",
    ".gltf": "glb",
    ".glsl": "glsl",
    ".jpeg": "texture",
    ".jpg": "texture",
    ".material": "material",
    ".navmesh": "navmesh",
    ".obj": "mesh",
    ".ogg": "audio_clip",
    ".flac": "audio_clip",
    ".mp3": "audio_clip",
    ".pipeline": "pipeline",
    ".png": "texture",
    ".prefab": "prefab",
    ".scene_pipeline": "scene_pipeline",
    ".shader": "shader",
    ".stl": "mesh",
    ".bmp": "texture",
    ".tga": "texture",
    ".uiscript": "ui",
    ".voxels": "voxel_grid",
    ".wav": "audio_clip",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _setup_entry_points(setup_path: Path) -> dict[str, dict[str, str]]:
    tree = ast.parse(setup_path.read_text(encoding="utf-8"), filename=str(setup_path))
    setup_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "setup"
    )
    entry_points = next(
        keyword.value
        for keyword in setup_call.keywords
        if keyword.arg == "entry_points"
    )
    assert isinstance(entry_points, ast.Dict)

    groups: dict[str, dict[str, str]] = {}
    for key, value in zip(entry_points.keys, entry_points.values):
        assert isinstance(key, ast.Constant)
        assert isinstance(key.value, str)
        assert isinstance(value, ast.List)
        group_entries: dict[str, str] = {}
        for item in value.elts:
            assert isinstance(item, ast.Constant)
            assert isinstance(item.value, str)
            name, target = item.value.split("=", 1)
            group_entries[name.strip()] = target.strip()
        groups[key.value] = group_entries
    return groups


def _default_asset_entry_points() -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = {
        "termin.asset_import_plugins": {},
        "termin.asset_runtime_plugins": {},
    }
    for rel_setup_path in DEFAULT_ASSET_PLUGIN_SETUP_FILES:
        for group_name, entries in _setup_entry_points(_repo_root() / rel_setup_path).items():
            if group_name in groups:
                groups[group_name].update(entries)
    return groups


def _module_source_path(module_name: str) -> Path:
    rel_module_path = Path(*module_name.split(".")).with_suffix(".py")
    root = _repo_root()
    if module_name.startswith("termin.default_assets."):
        return root / "termin-default-assets/python" / rel_module_path
    if module_name.startswith("termin.glb."):
        return root / "termin-glb/python" / rel_module_path
    if module_name.startswith("termin.prefab."):
        return root / "termin-prefab/python" / rel_module_path
    raise AssertionError(f"Unhandled default asset plugin module: {module_name}")


def _literal_string_set(value: ast.AST) -> set[str]:
    assert isinstance(value, ast.Set)
    result: set[str] = set()
    for item in value.elts:
        assert isinstance(item, ast.Constant)
        assert isinstance(item.value, str)
        result.add(item.value)
    return result


def _import_plugin_contract(module_name: str) -> tuple[str, set[str]]:
    source_path = _module_source_path(module_name)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not node.name.endswith("ImportPlugin"):
            continue
        type_id: str | None = None
        extensions: set[str] | None = None
        for statement in node.body:
            if not isinstance(statement, ast.Assign):
                continue
            targets = [
                target.id
                for target in statement.targets
                if isinstance(target, ast.Name)
            ]
            if "type_id" in targets:
                assert isinstance(statement.value, ast.Constant)
                assert isinstance(statement.value.value, str)
                type_id = statement.value.value
            if "extensions" in targets:
                extensions = _literal_string_set(statement.value)
        if type_id is not None and extensions is not None:
            return type_id, extensions
    raise AssertionError(f"Import plugin contract not found in {source_path}")


def test_default_asset_plugin_entry_points_declare_expected_types() -> None:
    groups = _default_asset_entry_points()

    assert set(groups["termin.asset_runtime_plugins"]) >= EXPECTED_PLUGIN_TYPES
    assert set(groups["termin.asset_import_plugins"]) >= EXPECTED_PLUGIN_TYPES


def test_default_import_plugin_sources_declare_expected_extensions() -> None:
    groups = _default_asset_entry_points()

    actual_extensions: dict[str, str] = {}
    for type_id, target in groups["termin.asset_import_plugins"].items():
        module_name, _factory_name = target.split(":", 1)
        declared_type, extensions = _import_plugin_contract(module_name)
        assert declared_type == type_id
        for extension in extensions:
            actual_extensions[extension] = type_id

    assert {
        extension: actual_extensions[extension]
        for extension in EXPECTED_IMPORT_EXTENSIONS
    } == EXPECTED_IMPORT_EXTENSIONS
