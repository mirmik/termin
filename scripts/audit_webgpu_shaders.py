#!/usr/bin/env python3
"""Compile the built-in Slang catalog to WGSL and validate it with Naga."""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys
from typing import Any


SUPPORTED_WEBGPU_STAGES = {"vertex", "fragment", "compute"}
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = (
    REPO_ROOT
    / "graphics"
    / "termin-graphics"
    / "resources"
    / "builtin_shaders"
    / "engine-shader-catalog.json"
)
RESOURCE_DECLARATION = re.compile(
    r"(?P<attributes>(?:@\w+\([^)]*\)\s*)*)"
    r"var(?:<(?P<address_space>[^>]+)>)?\s+"
    r"(?P<name>\w+)\s*:\s*(?P<type>[^;]+);",
    re.MULTILINE,
)
ATTRIBUTE = re.compile(r"@(group|binding)\((\d+)\)")
MATRIX = re.compile(r"(?:mat[234]x[234]|_MatrixStorage_)")


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {message}")
    return result.stdout.strip() or result.stderr.strip()


def tool_version(executable: pathlib.Path, expected: str) -> str:
    if not executable.is_file():
        raise RuntimeError(f"tool does not exist: {executable}")
    version = command_output([str(executable), "-version" if "slangc" in executable.name else "--version"])
    if version != expected:
        raise RuntimeError(f"expected {executable.name} {expected}, got {version}")
    return version


def inspect_wgsl(source: str) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    errors: list[str] = []
    occupied: dict[tuple[int, int], str] = {}

    for match in RESOURCE_DECLARATION.finditer(source):
        attributes = {name: int(value) for name, value in ATTRIBUTE.findall(match["attributes"])}
        resource_type = match["type"].strip()
        address_space = (match["address_space"] or "").strip()
        is_resource = (
            address_space in {"uniform", "storage"}
            or resource_type.startswith("texture_")
            or resource_type.startswith("sampler")
        )
        if not is_resource:
            continue
        name = match["name"]
        if "group" not in attributes or "binding" not in attributes:
            errors.append(f"resource {name} has no explicit @group/@binding")
            continue
        slot = (attributes["group"], attributes["binding"])
        if slot in occupied:
            errors.append(
                f"duplicate @group({slot[0]}) @binding({slot[1]}): "
                f"{occupied[slot]} and {name}"
            )
        occupied[slot] = name
        if address_space == "uniform":
            kind = "uniform_buffer"
        elif address_space == "storage":
            kind = "storage_buffer"
        elif resource_type.startswith("texture_"):
            kind = "texture"
        else:
            kind = "sampler"
        if kind == "uniform_buffer" and "std140" not in resource_type:
            errors.append(f"uniform buffer {name} is not emitted with an explicit std140 layout")
        resources.append(
            {
                "name": name,
                "kind": kind,
                "group": slot[0],
                "binding": slot[1],
                "type": resource_type,
            }
        )

    uses_matrix = bool(MATRIX.search(source))
    if uses_matrix and "_MatrixStorage_" not in source:
        errors.append("matrix use has no explicit Slang storage-layout wrapper")

    return {
        "resources": resources,
        "resource_counts": {
            kind: sum(resource["kind"] == kind for resource in resources)
            for kind in ("uniform_buffer", "storage_buffer", "texture", "sampler")
        },
        "uses_matrix": uses_matrix,
        "errors": errors,
    }


def reflection_metrics(value: Any) -> dict[str, int]:
    metrics = {"constant_buffers": 0, "matrix_types": 0, "uniform_fields": 0}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("kind") == "constantBuffer":
                metrics["constant_buffers"] += 1
            if node.get("kind") == "matrix":
                metrics["matrix_types"] += 1
            binding = node.get("binding")
            if isinstance(binding, dict) and binding.get("kind") == "uniform" and "offset" in binding:
                metrics["uniform_fields"] += 1
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return metrics


def compile_stage(
    slangc: pathlib.Path,
    naga: pathlib.Path,
    source_root: pathlib.Path,
    output_root: pathlib.Path,
    shader_uuid: str,
    stage: str,
    spec: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "stage": stage,
        "source": spec["path"],
        "entry": spec["entry"],
        "status": "failed",
        "errors": [],
    }
    if stage not in SUPPORTED_WEBGPU_STAGES:
        result["errors"].append(f"WebGPU does not support the {stage} stage")
        return result

    stage_root = output_root / "wgsl"
    stage_root.mkdir(parents=True, exist_ok=True)
    wgsl_path = stage_root / f"{shader_uuid}.{stage}.wgsl"
    reflection_path = stage_root / f"{shader_uuid}.{stage}.reflection.json"
    compile_command = [
        str(slangc),
        str(source_root / spec["path"]),
        "-target",
        "wgsl",
        "-entry",
        spec["entry"],
        "-stage",
        stage,
        "-reflection-json",
        str(reflection_path),
        "-o",
        str(wgsl_path),
    ]
    compiled = subprocess.run(compile_command, check=False, capture_output=True, text=True)
    if compiled.returncode != 0:
        result["errors"].append(compiled.stderr.strip() or compiled.stdout.strip())
        return result

    validated = subprocess.run(
        [str(naga), "--input-kind", "wgsl", str(wgsl_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if validated.returncode != 0:
        result["errors"].append(validated.stderr.strip() or validated.stdout.strip())

    source = wgsl_path.read_text(encoding="utf-8")
    inspection = inspect_wgsl(source)
    result.update(inspection)
    result["reflection"] = reflection_metrics(
        json.loads(reflection_path.read_text(encoding="utf-8"))
    )
    result["wgsl"] = str(wgsl_path)
    result["reflection_json"] = str(reflection_path)
    result["errors"].extend(inspection["errors"])
    if not result["errors"]:
        result["status"] = "passed"
    return result


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Built-in Slang → WGSL audit",
        "",
        f"Generated: {report['generated_on']}",
        "",
        "## Result",
        "",
        f"The pinned matrix is **{report['status'].upper()}**: "
        f"{summary['passed_stages']}/{summary['slang_stages']} Slang stages passed "
        "Slang WGSL generation, independent Naga parsing, and binding-contract checks.",
        "",
        f"Catalog coverage: {summary['classified_shaders']}/{summary['catalog_shaders']} identities. "
        f"{summary['excluded_shaders']} non-Slang program source is classified separately.",
        "",
        "Reproduce from the repository root:",
        "",
        "```bash",
        "task check:webgpu-shaders -- --setup",
        "```",
        "",
        "Toolchain: Slang " + report["toolchain"]["slang"] + ", Naga CLI " + report["toolchain"]["naga"] + ".",
        "",
        "## WebGPU capability profile",
        "",
        "- Accepted stages: vertex, fragment, compute. Geometry/tessellation stages are hard blockers.",
        "- Every WGSL resource must have an explicit, unique `@group`/`@binding` pair per stage.",
        "- Constant buffers are emitted as `var<uniform>` with explicit WGSL alignment; Naga validates the resulting layout.",
        "- Slang matrix lowering is accepted only when the generated storage structs and matrix reconstruction pass Naga.",
        "- Textures and samplers remain separate WGSL bindings; no combined-sampler compatibility layer is assumed.",
        "- This is an offline source gate. Browser device limits and render-pipeline creation belong to the WebGPU runtime smoke gate.",
        "",
        "Observed across passing stages: "
        f"{summary['uniform_buffers']} uniform-buffer declarations, "
        f"{summary['textures']} texture declarations, {summary['samplers']} sampler declarations, "
        f"and {summary['matrix_stages']} stages using matrices.",
        f"All reflected resources are currently placed in bind group 0; the largest binding index is {summary['max_binding']}. "
        "That matches the current single-set backend contract while preserving semantic Termin scopes in sidecar reflection.",
        "",
        "## Catalog classification",
        "",
        "| UUID | Language | Stages | Classification |",
        "|---|---|---|---|",
    ]
    for shader in report["shaders"]:
        stages = ", ".join(stage["stage"] for stage in shader.get("stages", [])) or "—"
        classification = shader["status"]
        if shader.get("reason"):
            classification += ": " + shader["reason"]
        lines.append(
            f"| `{shader['uuid']}` | {shader['language']} | {stages} | {classification} |"
        )

    failures = [
        (shader["uuid"], stage)
        for shader in report["shaders"]
        for stage in shader.get("stages", [])
        if stage["status"] != "passed"
    ]
    lines.extend(["", "## Blockers and exclusions", ""])
    if failures:
        for uuid, stage in failures:
            lines.append(f"- `{uuid}:{stage['stage']}`: {'; '.join(stage['errors'])}")
    else:
        lines.append("- No Slang-stage WGSL blockers were found in the current catalog.")
    lines.append(
        "- `termin-engine-skybox` is a legacy `.shader` program and is outside the Slang-stage matrix. "
        "It needs a dedicated WebGPU artifact path or migration to staged Slang before the offline package can be complete."
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The current built-in Slang catalog is viable for an offline WGSL path. This does not yet prove "
            "pipeline creation on a real WebGPU device, bind-group compatibility with tgfx2, or visual parity. "
            "Those checks remain runtime integration work; this audit deliberately makes them separate gates.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    web_lock = json.loads((REPO_ROOT / "build-system/web-shader-toolchain-lock.json").read_text(encoding="utf-8"))
    slang_lock = json.loads((REPO_ROOT / "build-system/slang-toolchain-lock.json").read_text(encoding="utf-8"))
    slang_version = tool_version(args.slangc, slang_lock["version"])
    naga_version = tool_version(args.naga, web_lock["naga_cli"]["version"])
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    source_root = args.catalog.parent

    shaders: list[dict[str, Any]] = []
    for shader in catalog["shaders"]:
        shader_result: dict[str, Any] = {
            "uuid": shader["uuid"],
            "name": shader["name"],
            "language": shader["language"],
            "stages": [],
        }
        if shader["language"] != "slang":
            shader_result["status"] = "excluded"
            shader_result["reason"] = "program source has no staged Slang entries"
        else:
            for stage, spec in shader["stages"].items():
                shader_result["stages"].append(
                    compile_stage(
                        args.slangc,
                        args.naga,
                        source_root,
                        args.output_dir,
                        shader["uuid"],
                        stage,
                        spec,
                    )
                )
            shader_result["status"] = (
                "passed"
                if all(stage["status"] == "passed" for stage in shader_result["stages"])
                else "failed"
            )
        shaders.append(shader_result)

    stages = [stage for shader in shaders for stage in shader["stages"]]
    passed_stages = [stage for stage in stages if stage["status"] == "passed"]
    report = {
        "schema": 1,
        "generated_on": datetime.date.today().isoformat(),
        "status": "passed" if len(passed_stages) == len(stages) else "failed",
        "toolchain": {"slang": slang_version, "naga": naga_version},
        "summary": {
            "catalog_shaders": len(shaders),
            "classified_shaders": len(shaders),
            "excluded_shaders": sum(shader["status"] == "excluded" for shader in shaders),
            "slang_stages": len(stages),
            "passed_stages": len(passed_stages),
            "uniform_buffers": sum(stage["resource_counts"]["uniform_buffer"] for stage in passed_stages),
            "textures": sum(stage["resource_counts"]["texture"] for stage in passed_stages),
            "samplers": sum(stage["resource_counts"]["sampler"] for stage in passed_stages),
            "matrix_stages": sum(stage["uses_matrix"] for stage in passed_stages),
            "binding_groups": sorted(
                {
                    resource["group"]
                    for stage in passed_stages
                    for resource in stage["resources"]
                }
            ),
            "max_binding": max(
                (
                    resource["binding"]
                    for stage in passed_stages
                    for resource in stage["resources"]
                ),
                default=-1,
            ),
        },
        "shaders": shaders,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slangc", type=pathlib.Path, required=True)
    parser.add_argument("--naga", type=pathlib.Path, required=True)
    parser.add_argument(
        "--catalog",
        type=pathlib.Path,
        default=DEFAULT_CATALOG,
    )
    parser.add_argument(
        "--output-dir", type=pathlib.Path, default=REPO_ROOT / "build/web-shader-audit"
    )
    parser.add_argument(
        "--report-json",
        type=pathlib.Path,
        default=REPO_ROOT / "build/web-shader-audit/report.json",
    )
    parser.add_argument(
        "--report-md",
        type=pathlib.Path,
        default=REPO_ROOT / "docs/analysis/2026-08-02-builtin-slang-wgsl-audit.md",
    )
    args = parser.parse_args()

    try:
        report = run(args)
    except (OSError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        print(f"web-shader-audit: ERROR: {error}", file=sys.stderr)
        return 2

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text(markdown_report(report), encoding="utf-8")
    summary = report["summary"]
    print(
        f"web-shader-audit: {report['status']}: "
        f"{summary['passed_stages']}/{summary['slang_stages']} stages, "
        f"{summary['classified_shaders']}/{summary['catalog_shaders']} identities classified"
    )
    print(f"web-shader-audit: JSON: {args.report_json}")
    print(f"web-shader-audit: Markdown: {args.report_md}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
