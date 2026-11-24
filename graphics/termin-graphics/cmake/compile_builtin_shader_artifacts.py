import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time


STAGE_EXTENSIONS = {
    "vertex": "vert",
    "fragment": "frag",
    "geometry": "geom",
    "compute": "comp",
}

D3D11_STAGE_EXTENSIONS = {
    "vertex": "vs",
    "fragment": "ps",
    "geometry": "gs",
    "compute": "cs",
}

TARGET_EXTENSIONS = {
    "vulkan": "spv",
    "opengl": "glsl",
    "opengl330": "glsl",
    "webgl2": "glsl",
    "d3d11": "cso",
    "webgpu": "wgsl",
}

ARTIFACT_MANIFEST_NAME = "builtin-shader-artifacts.json"
ARTIFACT_MANIFEST_SCHEMA_VERSION = 1


def validate_catalog(catalog: object, source_dir: pathlib.Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(catalog, dict):
        return ["catalog root must be an object"]
    shaders = catalog.get("shaders")
    if not isinstance(shaders, list):
        return ["catalog 'shaders' must be an array"]

    seen_uuids: set[str] = set()
    for index, shader in enumerate(shaders):
        where = f"shaders[{index}]"
        if not isinstance(shader, dict):
            errors.append(f"{where} must be an object")
            continue
        uuid = shader.get("uuid")
        name = shader.get("name")
        language = shader.get("language")
        if not isinstance(uuid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", uuid):
            errors.append(f"{where}.uuid must be a non-empty artifact name")
            continue
        if uuid in seen_uuids:
            errors.append(f"duplicate shader uuid: {uuid}")
        seen_uuids.add(uuid)
        if not isinstance(name, str) or not name:
            errors.append(f"shader '{uuid}' has no non-empty name")
        if language == "shader":
            program = shader.get("program")
            path = program.get("path") if isinstance(program, dict) else None
            if not isinstance(path, str) or not path:
                errors.append(f"shader program '{uuid}' has no path")
            elif not (source_dir / path).is_file():
                errors.append(f"shader program '{uuid}' source does not exist: {path}")
            if "stages" in shader:
                errors.append(f"shader program '{uuid}' must not also declare stages")
            artifact_language = shader.get("artifact_language")
            if artifact_language != "slang":
                errors.append(f"shader program '{uuid}' must declare artifact_language 'slang'")
            artifact_stages = shader.get("artifact_stages")
            errors.extend(
                validate_stage_map(
                    uuid,
                    artifact_stages,
                    source_dir,
                    field="artifact_stages",
                )
            )
            continue
        if language not in {"slang", "glsl"}:
            errors.append(f"shader '{uuid}' has unsupported language: {language!r}")
            continue
        stages = shader.get("stages")
        if "program" in shader:
            errors.append(f"stage shader '{uuid}' must not also declare a program")
        errors.extend(validate_stage_map(uuid, stages, source_dir, field="stages"))
    return errors


def validate_stage_map(
    uuid: str,
    stages: object,
    source_dir: pathlib.Path,
    *,
    field: str,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(stages, dict) or not stages:
        return [f"shader '{uuid}' must declare at least one {field} entry"]
    for stage, spec in stages.items():
        if stage not in STAGE_EXTENSIONS:
            errors.append(f"shader '{uuid}' has unsupported stage: {stage}")
            continue
        if not isinstance(spec, dict):
            errors.append(f"shader '{uuid}' stage '{stage}' must be an object")
            continue
        path = spec.get("path")
        entry = spec.get("entry")
        if not isinstance(path, str) or not path:
            errors.append(f"shader '{uuid}' stage '{stage}' has no path")
        elif not (source_dir / path).is_file():
            errors.append(f"shader '{uuid}' stage '{stage}' source does not exist: {path}")
        if not isinstance(entry, str) or not entry:
            errors.append(f"shader '{uuid}' stage '{stage}' has no entry")
    return errors


def artifact_name(uuid: str, target: str, stage: str) -> str:
    if target == "d3d11":
        stage_ext = D3D11_STAGE_EXTENSIONS[stage]
    else:
        stage_ext = STAGE_EXTENSIONS[stage]
    return f"{uuid}.{stage_ext}.{TARGET_EXTENSIONS[target]}"


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: pathlib.Path, value: object) -> None:
    contents = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == contents:
        return
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(contents, encoding="utf-8")
    temporary.replace(path)


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def tool_fingerprint(tool: str | pathlib.Path | None, *, slang: bool = False) -> dict[str, str]:
    if tool is None:
        return {}
    executable = pathlib.Path(tool).resolve(strict=True)
    files = {executable}
    if slang:
        for directory in (executable.parent, executable.parent.parent / "lib"):
            files.update(path.resolve() for path in directory.glob("*slang*") if path.is_file())
            for modules in directory.glob("slang-standard-module-*"):
                files.update(path.resolve() for path in modules.rglob("*") if path.is_file())
    return {str(path): file_sha256(path) for path in sorted(files)}


class ShaderSources:
    """Track local Slang modules and literal includes for program layout and stage code."""

    _comments_or_strings = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"', re.DOTALL)
    _import = re.compile(
        r'\b(?:import|__include)\s+([A-Za-z_][A-Za-z0-9_.]*)\s*;|"(?:\\.|[^"\\])*"'
    )
    _include = re.compile(r'^[ \t]*#[ \t]*include[ \t]*([^\n]+)', re.MULTILINE)

    def __init__(self, root: pathlib.Path):
        self.root = root
        self.digests = {}
        self.dependencies = {}

    def direct_imports(self, path: pathlib.Path) -> list[pathlib.Path]:
        if path in self.dependencies:
            return self.dependencies[path]
        content = path.read_bytes()
        self.digests[path] = hashlib.sha256(content).hexdigest()
        source = self._comments_or_strings.sub(
            lambda match: match[0] if match[0].startswith('"') else
            "".join("\n" if char == "\n" else " " for char in match[0]),
            content.decode("utf-8"),
        )
        dependencies = []
        for module in filter(None, self._import.findall(source)):
            dependencies.append(self._resolve(path, [
                self.root / f"{module}.slang",
                self.root / f"{module.replace('.', '/')}.slang",
                path.parent / f"{module}.slang",
            ]))
        for include in self._include.findall(source):
            literal = re.fullmatch(r'"([^"]+)"|<([^>]+)>', include.strip())
            if literal is None:
                raise ValueError(f"{path}: built-in shader include must be a literal path: {include}")
            filename = literal[1] or literal[2]
            dependencies.append(self._resolve(path, [path.parent / filename, self.root / filename]))
        self.dependencies[path] = dependencies
        return dependencies

    @staticmethod
    def _resolve(path: pathlib.Path, candidates: list[pathlib.Path]) -> pathlib.Path:
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        raise ValueError(f"{path}: shader dependency not found: {candidates[0]}")

    def program_fingerprint(self, stage_paths: list[pathlib.Path]) -> dict[str, str]:
        seen = set()
        pending = list(stage_paths)
        while pending:
            path = pending.pop().resolve()
            if path in seen:
                continue
            seen.add(path)
            pending.extend(self.direct_imports(path))
        return {str(path): self.digests[path] for path in sorted(seen)}


def previous_artifacts(output_root: pathlib.Path) -> dict[str, dict]:
    manifest = output_root / ARTIFACT_MANIFEST_NAME
    if not manifest.is_file():
        return {}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("schema_version") == ARTIFACT_MANIFEST_SCHEMA_VERSION:
            return {entry["path"]: entry for entry in data["artifacts"]}
    except (ValueError, AttributeError, TypeError, KeyError) as error:
        print(f"termin-graphics: rebuilding invalid previous manifest: {error}", file=sys.stderr)
    return {}


def cache_matches(output_root: pathlib.Path, path: str, layout: str, old: dict, key: str) -> bool:
    if old.get("input_sha256") != key or old.get("layout") != layout:
        return False
    return all(
        (output_root / name).is_file() and file_sha256(output_root / name) == old.get(field)
        for name, field in [(path, "sha256"), (layout, "layout_sha256")]
    )


def synchronize_sources(source_dir: pathlib.Path, destination: pathlib.Path) -> None:
    if source_dir.resolve() == destination.resolve():
        return

    def copy_changed(source, target):
        source, target = pathlib.Path(source), pathlib.Path(target)
        if not target.is_file() or file_sha256(source) != file_sha256(target):
            shutil.copy2(source, target)

    shutil.copytree(source_dir, destination, dirs_exist_ok=True, copy_function=copy_changed)


def is_artifact_path(name: object) -> bool:
    if not isinstance(name, str):
        return False
    parts = pathlib.PurePosixPath(name).parts
    return len(parts) == 3 and parts[0] == "shaders" and parts[1] in TARGET_EXTENSIONS and parts[2] != ".."


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile Termin built-in Slang shaders to backend artifacts.")
    parser.add_argument("--shaderc", required=True)
    parser.add_argument("--tool-dependency", action="append", default=[])
    parser.add_argument("--slangc")
    parser.add_argument("--fxc")
    parser.add_argument("--wgsl-validator")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--target", action="append", required=True)
    args = parser.parse_args()

    shaderc = pathlib.Path(args.shaderc)
    source_dir = pathlib.Path(args.source_dir)
    output_root = pathlib.Path(args.output_root)
    catalog_path = source_dir / "engine-shader-catalog.json"

    if not shaderc.exists():
        print(f"termin-graphics: termin_shaderc does not exist: {shaderc}", file=sys.stderr)
        return 2
    if not catalog_path.exists():
        print(f"termin-graphics: shader catalog does not exist: {catalog_path}", file=sys.stderr)
        return 2

    targets = []
    for target in args.target:
        normalized = target.strip().lower()
        if normalized not in TARGET_EXTENSIONS:
            print(f"termin-graphics: unsupported shader target: {target}", file=sys.stderr)
            return 2
        if normalized not in targets:
            targets.append(normalized)

    with catalog_path.open("r", encoding="utf-8") as f:
        catalog = json.load(f)

    validation_errors = validate_catalog(catalog, source_dir)
    if validation_errors:
        for error in validation_errors:
            print(f"termin-graphics: invalid shader catalog: {error}", file=sys.stderr)
        return 2

    try:
        return compile_artifacts(args, source_dir.resolve(), output_root.resolve(), targets, catalog, catalog_path)
    except (OSError, ValueError) as error:
        print(f"termin-graphics: failed to prepare built-in shader artifacts: {error}", file=sys.stderr)
        return 1


def compile_artifacts(args, source_dir, output_root, targets, catalog, catalog_path) -> int:
    start_time = time.monotonic()
    source_graph = ShaderSources(source_dir)
    previous = previous_artifacts(output_root)
    shaderc = str(pathlib.Path(args.shaderc).absolute())
    base_inputs = {
        "driver": file_sha256(pathlib.Path(__file__)),
        "shaderc": tool_fingerprint(shaderc),
        "tool_dependencies": [tool_fingerprint(path) for path in args.tool_dependency],
        "slang": tool_fingerprint(args.slangc, slang=True),
        "environment": {key: os.environ.get(key) for key in ("LD_LIBRARY_PATH", "TERMIN_SLANGC")},
    }
    tool_inputs = {
        target: fingerprint({
            **base_inputs,
            "backend": target,
            "fxc": tool_fingerprint(args.fxc) if target == "d3d11" else {},
            "validator": tool_fingerprint(args.wgsl_validator) if target == "webgpu" else {},
        })
        for target in targets
    }

    jobs = []
    for shader in catalog["shaders"]:
        language = shader["language"]
        if language == "shader":
            language = shader["artifact_language"]
            stages = shader["artifact_stages"]
        else:
            stages = shader["stages"]
        if language != "slang":
            continue

        stage_paths = [source_dir / spec["path"] for spec in stages.values()]
        dependencies = source_graph.program_fingerprint(stage_paths)
        program_inputs = fingerprint({
            "language": language,
            "stages": list(stages.items()),
            "dependencies": dependencies,
        })
        for stage, spec in stages.items():
            for target in targets:
                jobs.append((shader["uuid"], stage, spec, stage_paths, target, program_inputs))

    output_root.mkdir(parents=True, exist_ok=True)
    artifacts = []
    changed = []
    reused = 0
    with tempfile.TemporaryDirectory(prefix=".builtin-shaders-", dir=output_root) as temporary:
        build_root = pathlib.Path(temporary)
        for index, (uuid, stage, spec, stage_paths, target, program_inputs) in enumerate(jobs, 1):
            path = f"shaders/{target}/{artifact_name(uuid, target, stage)}"
            layout = path + ".layout.json"
            key = fingerprint([tool_inputs[target], program_inputs, uuid, stage])
            old = previous.get(path, {})
            if cache_matches(output_root, path, layout, old, key):
                artifacts.append(old)
                reused += 1
                continue

            print(
                f"termin-graphics: [{index}/{len(jobs)}] compiling {uuid}:{stage} for {target} "
                f"({time.monotonic() - start_time:.1f}s elapsed)",
                flush=True,
            )
            output_path = build_root / path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                shaderc, "compile", "--language", "slang", "--target", target,
                "--stage", stage, "--entry", spec["entry"],
                "--input", str(source_dir / spec["path"]), "--output", str(output_path),
                "-I", str(source_dir), "--debug-name", f"{uuid}:{stage}",
            ]
            for stage_path in stage_paths:
                cmd.extend(["--program-source", str(stage_path)])
            if args.slangc:
                cmd.extend(["--slangc", args.slangc])
            if target == "d3d11" and args.fxc:
                cmd.extend(["--fxc", args.fxc])
            if target == "webgpu" and args.wgsl_validator:
                cmd.extend(["--wgsl-validator", args.wgsl_validator])
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0 or not output_path.is_file() or not (build_root / layout).is_file():
                print(
                    f"termin-graphics: failed to produce artifact and layout for {uuid}:{stage} "
                    f"({target}), compiler exit={result.returncode}",
                    file=sys.stderr,
                )
                return 1
            artifacts.append({
                "uuid": uuid,
                "target": target,
                "stage": stage,
                "path": path,
                "sha256": file_sha256(output_path),
                "layout": layout,
                "layout_sha256": file_sha256(build_root / layout),
                "input_sha256": key,
            })
            changed.extend((path, layout))

        # Publish only after every changed job succeeds. If publication is
        # interrupted, the next build verifies file hashes against the manifest.
        for name in changed:
            destination = output_root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            (build_root / name).replace(destination)

    staged_source_dir = output_root / "builtin_shaders"
    synchronize_sources(source_dir, staged_source_dir)
    desired = {entry["path"] for entry in artifacts}
    for path in previous.keys() - desired:
        for name in (path, previous[path].get("layout")):
            if is_artifact_path(name):
                (output_root / name).unlink(missing_ok=True)

    write_json_atomic(
        output_root / ARTIFACT_MANIFEST_NAME,
        {
            "schema_version": ARTIFACT_MANIFEST_SCHEMA_VERSION,
            "catalog": "builtin_shaders/engine-shader-catalog.json",
            "catalog_sha256": file_sha256(catalog_path),
            "targets": targets,
            "artifacts": artifacts,
        },
    )

    print(
        f"termin-graphics: compiled {len(jobs) - reused}, reused {reused} built-in shader artifacts "
        f"in {time.monotonic() - start_time:.1f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
