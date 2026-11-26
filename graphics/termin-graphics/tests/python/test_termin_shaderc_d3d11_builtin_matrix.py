import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _termin_shaderc() -> Path:
    binary_names = ["termin_shaderc.exe", "termin_shaderc"] if os.name == "nt" else ["termin_shaderc"]
    candidates: list[Path] = []
    explicit = os.environ.get("TERMIN_SHADERC")
    if explicit:
        candidates.append(Path(explicit))
    root = _repo_root()
    candidate_dirs = [
        root / "build" / "Release" / "bin" / "Release",
        root / "build" / "Release" / "bin",
        root / "sdk" / "bin",
    ]
    candidates.extend(candidate_dir / name for candidate_dir in candidate_dirs for name in binary_names)
    sdk = os.environ.get("TERMIN_SDK")
    if sdk:
        candidates.extend(Path(sdk) / "bin" / name for name in binary_names)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    pytest.skip("termin_shaderc binary is not available in this test environment")


def _resolve_slangc() -> Path:
    explicit = os.environ.get("TERMIN_SLANGC")
    if explicit and Path(explicit).exists():
        return Path(explicit)
    found = shutil.which("slangc")
    if found:
        return Path(found)
    pytest.skip("slangc is not available")


def _resolve_fxc() -> Path:
    explicit = os.environ.get("TERMIN_FXC")
    if explicit and Path(explicit).exists():
        return Path(explicit)
    found = shutil.which("fxc")
    if found:
        return Path(found)
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    kit_bin = Path(program_files_x86) / "Windows Kits" / "10" / "bin"
    candidates = sorted(kit_bin.glob(r"*\x64\fxc.exe"))
    if candidates:
        return candidates[-1]
    pytest.skip("fxc.exe is not available")


def _builtin_shader_stage_jobs() -> list[tuple[Path, str, str]]:
    source_root = _repo_root() / "graphics" / "termin-graphics" / "resources" / "builtin_shaders"
    attr_re = re.compile(r'\[shader\("(?P<stage>vertex|fragment|geometry|compute)"\)\]')
    entry_re = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    jobs: list[tuple[Path, str, str]] = []
    for path in sorted(source_root.glob("*.slang")):
        text = path.read_text(encoding="utf-8")
        for match in attr_re.finditer(text):
            search_window = text[match.end():match.end() + 300]
            entry_match = entry_re.search(search_window)
            assert entry_match is not None, f"could not infer entry point for {path.name}"
            jobs.append((path, match.group("stage"), entry_match.group(1)))
    assert jobs, "no builtin Slang shader stages were discovered"
    return jobs


@pytest.mark.skipif(os.name != "nt", reason="D3D11 .cso artifact matrix is Windows-only")
def test_builtin_slang_shaders_compile_to_d3d11_cso(tmp_path: Path) -> None:
    shaderc = _termin_shaderc()
    slangc = _resolve_slangc()
    fxc = _resolve_fxc()
    source_root = _repo_root() / "graphics" / "termin-graphics" / "resources" / "builtin_shaders"
    stage_suffix = {
        "vertex": "vs",
        "fragment": "ps",
        "geometry": "gs",
        "compute": "cs",
    }

    failures: list[str] = []
    for source, stage, entry in _builtin_shader_stage_jobs():
        suffix = stage_suffix[stage]
        output = tmp_path / "shaders" / "d3d11" / f"{source.stem}.{entry}.{suffix}.cso"
        result = subprocess.run(
            [
                str(shaderc),
                "compile",
                "--language",
                "slang",
                "--target",
                "d3d11",
                "--stage",
                stage,
                "--entry",
                entry,
                "--input",
                str(source),
                "--output",
                str(output),
                "--slangc",
                str(slangc),
                "--fxc",
                str(fxc),
                "--include-dir",
                str(source_root),
                "--debug-name",
                f"{source.name}:{stage}:{entry}",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0 or not output.exists() or not Path(str(output) + ".layout.json").exists():
            failures.append(
                f"{source.name}:{stage}:{entry} rc={result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    assert not failures, "\n\n".join(failures)


def _compile_stage(
    stage: str, entry: str, source: Path, artifact: Path, program_sources: tuple[Path, ...] = ()
) -> tuple[dict, str]:
    args = [
        str(_termin_shaderc()), "compile",
        "--language", "slang",
        "--target", "d3d11",
        "--stage", stage,
        "--entry", entry,
        "--input", str(source),
        "--output", str(artifact),
        "--slangc", str(_resolve_slangc()),
        "--fxc", str(_resolve_fxc()),
        "--include-dir", str(_repo_root() / "graphics" / "termin-graphics" / "resources" / "builtin_shaders"),
    ]
    for path in program_sources:
        args.extend(["--program-source", str(path)])
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    diagnostics = result.stdout + result.stderr
    assert result.returncode == 0, diagnostics
    assert artifact.is_file()
    return json.loads(Path(f"{artifact}.layout.json").read_text(encoding="utf-8")), diagnostics


@pytest.mark.skipif(os.name != "nt", reason="D3D11 .cso artifact matrix is Windows-only")
@pytest.mark.parametrize("program_layout", [False, True], ids=["stage", "program"])
def test_shadow_helper_with_material_and_ibl_textures(tmp_path: Path, program_layout: bool) -> None:
    shader = tmp_path / "shadow-warning-smoke.slang"
    shader.write_text(
        "import termin_prelude;\n"
        "import termin_shadows;\n"
        "import termin_ibl;\n"
        "struct MaterialParams { float4 color; float metallic; float roughness; float4 emission; float intensity; float strength; };\n"
        '[[TerminScope("material")]] ConstantBuffer<MaterialParams> material;\n'
        '[[TerminScope("material")]] Sampler2D u_albedo_texture;\n'
        "struct FragmentInput { float3 world_pos : TEXCOORD0; };\n"
        '[shader("fragment")]\n'
        "float4 fs_main(FragmentInput input) : SV_Target0 {\n"
        "    float visibility = compute_shadow_auto(0, input.world_pos);\n"
        "    float3 n = normalize(input.world_pos);\n"
        "    float3 light = sample_ibl_diffuse_irradiance(n) + sample_ibl_prefiltered_specular(n, 1.0);\n"
        "    float2 brdf = sample_ibl_brdf(n.z, 0.4);\n"
        "    return u_albedo_texture.Sample(n.xy) * float4(light * visibility, brdf.x) * material.strength;\n"
        "}\n",
        encoding="utf-8",
    )
    output = tmp_path / "shadow-warning-smoke.ps.cso"
    program_sources = ()
    if program_layout:
        vertex = tmp_path / "shadow-warning-smoke.vert.slang"
        vertex.write_text(
            "import termin_prelude;\n"
            "import termin_ibl;\n"
            '[[TerminScope("draw")]] StructuredBuffer<float4> positions;\n'
            '[shader("vertex")] float4 vs_main(uint id : SV_VertexID) : SV_Position {\n'
            "    float4 pos = positions[id];\n"
            "    return pos + float4(sample_ibl_prefiltered_specular(pos.xyz, 1.0), 0.0);\n"
            "}\n",
            encoding="utf-8",
        )
        program_sources = (vertex, shader)

    layout, diagnostics = _compile_stage("fragment", "fs_main", shader, output, program_sources)
    material = next(r for r in layout["resources"] if r["name"] == "material")
    assert material["fields"][-1]["offset"] == 52
    assert material["size"] == 64
    textures = {r["name"]: r["d3d11"] for r in layout["resources"] if r["kind"] == "texture"}
    shadow = textures.pop("shadow_maps")
    assert shadow["scalar_sampler_for_texture_array"] is True
    assert shadow["register_class"] == "t"
    shadow_slots = range(shadow["register_index"], shadow["register_index"] + 16)
    assert textures.keys() == {
        "u_albedo_texture",
        "ibl_diffuse_irradiance",
        "ibl_prefiltered_specular",
        "ibl_brdf_lut",
    }
    slots = {tex["register_index"] for tex in textures.values()}
    assert len(slots) == len(textures)
    assert slots.isdisjoint(shadow_slots)
    samplers = [tex.get("sampler_register_index", tex["register_index"]) for tex in [shadow, *textures.values()]]
    assert len(set(samplers)) == len(samplers)
    assert all(0 <= slot < 16 for slot in samplers)
    assert "warning X3570" not in diagnostics
    assert "warning X4000" not in diagnostics
    assert "compilation object save succeeded" in diagnostics
    if program_layout:
        vertex_layout, _ = _compile_stage(
            "vertex", "vs_main", vertex, tmp_path / "shadow-warning-smoke.vs.cso", program_sources
        )
        bindings = {r["name"]: r["d3d11"] for r in vertex_layout["resources"]}
        assert bindings["ibl_prefiltered_specular"] == textures["ibl_prefiltered_specular"]
        assert bindings["positions"]["register_index"] not in shadow_slots


@pytest.mark.skipif(os.name != "nt", reason="D3D11 .cso artifact matrix is Windows-only")
def test_split_texture_array_uses_only_its_explicit_sampler(tmp_path: Path) -> None:
    source = tmp_path / "tiles.slang"
    source.write_text(
        "import termin_prelude;\n"
        '[[TerminScope("material")]] Texture2D<float4> tiles[16];\n'
        '[[TerminScope("material")]] SamplerState tile_sampler;\n'
        '[shader("fragment")] float4 fs_main(float2 uv : TEXCOORD0) : SV_Target0 {\n'
        "    return tiles[0].Sample(tile_sampler, uv) + tiles[15].Sample(tile_sampler, uv);\n"
        "}\n",
        encoding="utf-8",
    )
    layout, _ = _compile_stage("fragment", "fs_main", source, tmp_path / "tiles.ps.cso")
    bindings = {r["name"]: r["d3d11"] for r in layout["resources"]}
    assert bindings["tiles"]["register_class"] == "t"
    assert bindings["tiles"]["sampler_register_index"] is None
    assert bindings["tile_sampler"] == {"register_class": "s", "register_index": 0}
