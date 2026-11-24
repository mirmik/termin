import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _catalog_module():
    path = _repo_root() / "termin-graphics" / "cmake" / "compile_builtin_shader_artifacts.py"
    spec = importlib.util.spec_from_file_location("compile_builtin_shader_artifacts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_root() -> Path:
    return _repo_root() / "termin-graphics" / "resources" / "builtin_shaders"


def test_builtin_shader_manifest_is_complete_and_resolves_every_source() -> None:
    source_root = _source_root()
    catalog = json.loads((source_root / "engine-shader-catalog.json").read_text())

    assert _catalog_module().validate_catalog(catalog, source_root) == []
    registered_sources = {
        stage["path"]
        for shader in catalog["shaders"]
        for field in ("stages", "artifact_stages")
        for stage in shader.get(field, {}).values()
    }
    registered_sources.update(
        shader["program"]["path"] for shader in catalog["shaders"] if "program" in shader
    )
    engine_sources = {
        path.name for path in source_root.glob("termin-engine-*") if path.suffix in {".slang", ".shader"}
    }
    assert engine_sources
    assert engine_sources <= registered_sources, engine_sources - registered_sources
    assert any(shader["uuid"] == "termin-engine-id-batched" for shader in catalog["shaders"])
    assert any(shader["uuid"] == "termin-engine-multiview-output-transform" for shader in catalog["shaders"])
    assert all(shader["uuid"] != "termin-engine-foliage-shadow" for shader in catalog["shaders"])


def test_builtin_shader_manifest_rejects_duplicate_uuid_and_missing_source(tmp_path: Path) -> None:
    catalog = {
        "shaders": [
            {
                "uuid": "duplicate",
                "name": "First",
                "language": "slang",
                "stages": {"vertex": {"path": "missing.slang", "entry": "vs_main"}},
            },
            {
                "uuid": "duplicate",
                "name": "Second",
                "language": "slang",
                "stages": {"fragment": {"path": "also-missing.slang", "entry": ""}},
            },
        ]
    }

    errors = _catalog_module().validate_catalog(catalog, tmp_path)

    assert "duplicate shader uuid: duplicate" in errors
    assert any("source does not exist" in error for error in errors)
    assert any("has no entry" in error for error in errors)


def test_builtin_shader_webgpu_artifact_name_uses_wgsl_extension() -> None:
    module = _catalog_module()

    assert module.artifact_name("termin-engine-example", "webgpu", "vertex") == "termin-engine-example.vert.wgsl"
    assert module.artifact_name("termin-engine-example", "webgpu", "fragment") == "termin-engine-example.frag.wgsl"
    assert module.artifact_name("termin-engine-example", "webgpu", "compute") == "termin-engine-example.comp.wgsl"


def test_builtin_shader_constrained_gl_artifact_names_are_distinct() -> None:
    module = _catalog_module()

    assert module.artifact_name("termin-engine-example", "opengl330", "vertex") == "termin-engine-example.vert.glsl"
    assert module.artifact_name("termin-engine-example", "webgl2", "fragment") == "termin-engine-example.frag.glsl"


def test_builtin_shader_compiler_writes_versioned_artifact_manifest(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "example.slang").write_text("shader source", encoding="utf-8")
    catalog = {
        "version": 1,
        "shaders": [
            {
                "uuid": "termin-engine-example",
                "name": "Example",
                "language": "slang",
                "stages": {"vertex": {"path": "example.slang", "entry": "vs_main"}},
            }
        ],
    }
    (source_root / "engine-shader-catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    compiler = tmp_path / "fake_shaderc.py"
    compiler.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "out.write_text('compiled', encoding='utf-8')\n"
        "pathlib.Path(str(out) + '.layout.json').write_text(json.dumps({'version': 1}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    compiler.chmod(0o755)
    output_root = tmp_path / "output"

    completed = subprocess.run(
        [
            sys.executable,
            str(_repo_root() / "termin-graphics/cmake/compile_builtin_shader_artifacts.py"),
            "--shaderc",
            str(compiler),
            "--source-dir",
            str(source_root),
            "--output-root",
            str(output_root),
            "--target",
            "webgl2",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((output_root / "builtin-shader-artifacts.json").read_text(encoding="utf-8"))
    artifact = output_root / manifest["artifacts"][0]["path"]
    assert manifest["schema_version"] == 1
    assert manifest["targets"] == ["webgl2"]
    assert manifest["artifacts"][0]["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert (output_root / "builtin_shaders/example.slang").is_file()


def test_builtin_shader_cache_tracks_program_inputs_and_recovers_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    (source_root / "vertex.slang").write_text("import shared;\n", encoding="utf-8")
    (source_root / "shared.slang").write_text('#include "math.slang"\n', encoding="utf-8")
    (source_root / "math.slang").write_text("// a helper\n", encoding="utf-8")
    (source_root / "fragment.slang").write_text("// a fragment\n", encoding="utf-8")
    (source_root / "other.slang").write_text("// unrelated\n", encoding="utf-8")
    shaders = [
        {
            "uuid": "program",
            "name": "Program",
            "language": "slang",
            "stages": {
                "vertex": {"path": "vertex.slang", "entry": "main"},
                "fragment": {"path": "fragment.slang", "entry": "main"},
            },
        },
        {
            "uuid": "other",
            "name": "Other",
            "language": "slang",
            "stages": {"vertex": {"path": "other.slang", "entry": "main"}},
        },
    ]
    catalog_path = source_root / "engine-shader-catalog.json"
    catalog_path.write_text(json.dumps({"shaders": shaders}), encoding="utf-8")
    compiler = tmp_path / "fake_shaderc.py"
    compiler.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "def opt(name): return sys.argv[sys.argv.index(name) + 1]\n"
        "if 'BROKEN' in pathlib.Path(opt('--input')).read_text(): sys.exit(1)\n"
        "out = pathlib.Path(opt('--output'))\n"
        "inputs = [pathlib.Path(sys.argv[index + 1]).read_text()\n"
        "          for index, arg in enumerate(sys.argv) if arg == '--program-source']\n"
        "out.write_text(opt('--debug-name') + opt('--target') + ''.join(inputs))\n"
        "pathlib.Path(str(out) + '.layout.json').write_text('{}')\n",
        encoding="utf-8",
    )
    compiler.chmod(0o755)
    output = tmp_path / "output"

    def build(destination=output, *, expected=0, count=None):
        result = subprocess.run(
            [
                sys.executable, str(_catalog_module().__file__),
                "--shaderc", str(compiler), "--source-dir", str(source_root),
                "--output-root", str(destination), "--target", "vulkan", "--target", "webgl2",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == expected, result.stderr
        if count is not None:
            assert result.stdout.count("] compiling ") == count, result.stdout
        return result.stdout

    build(count=6)
    manifest = output / "builtin-shader-artifacts.json"
    reused = output / "shaders/vulkan/other.vert.spv"
    original_times = (manifest.stat().st_mtime_ns, reused.stat().st_mtime_ns)
    build(count=0)
    assert (manifest.stat().st_mtime_ns, reused.stat().st_mtime_ns) == original_times

    (source_root / "math.slang").write_text("// updated helper\n", encoding="utf-8")
    progress = build(count=4)
    assert "program:vertex" in progress and "program:fragment" in progress
    assert reused.stat().st_mtime_ns == original_times[1]
    (source_root / "fragment.slang").write_text("// updated fragment\n", encoding="utf-8")
    build(count=4)

    layout = output / "shaders/vulkan/program.vert.spv.layout.json"
    layout.unlink()
    build(count=1)
    reused.write_bytes(b"corrupt")
    build(count=1)
    clean = tmp_path / "clean"
    build(clean, count=6)
    assert manifest.read_bytes() == (clean / manifest.name).read_bytes()

    successful = manifest.read_bytes()
    original_artifact = (output / "shaders/vulkan/program.vert.spv").read_bytes()
    (source_root / "fragment.slang").write_text("BROKEN", encoding="utf-8")
    build(expected=1)
    assert manifest.read_bytes() == successful
    assert (output / "shaders/vulkan/program.vert.spv").read_bytes() == original_artifact

    catalog_path.write_text(json.dumps({"shaders": [shaders[1]]}), encoding="utf-8")
    build(count=0)
    assert not layout.exists()
    assert reused.exists()
    compiler.write_text(compiler.read_text(encoding="utf-8") + "# compiler update\n", encoding="utf-8")
    build(count=2)
