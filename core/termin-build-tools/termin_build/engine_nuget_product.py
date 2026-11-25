"""Stage installed full C# SDKs and compose one Termin.Engine NuGet package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from .engine_nuget_native import collect_native
from .graphics_nuget_product import (
    FIXED_ZIP_TIME,
    PackageDefinition,
    compose_package,
    load_lock,
)
from .versioning import public_version

PACKAGE_ID = "Termin.Engine"
FRAMEWORK = "net8.0"
BACKENDS = {"linux-x64": "vulkan", "win-x64": "d3d11"}
MANAGED = "Termin.Native.dll"
SHARE = "share/termin/"
SHADERS = SHARE + "builtin-shader-artifacts.json"
STAGE_MANIFEST = "stage.json"
PACKAGE_MANIFEST = "termin-engine-nuget.json"
SDK_FONT = SHARE + "fonts/DroidSans.ttf"
REDISTRIBUTABLE_FONT = (
    "termin-thirdparty/recastnavigation/RecastDemo/Contrib/imgui/misc/fonts/DroidSans.ttf"
)


class EngineNugetError(RuntimeError):
    """A full runtime input or candidate violates the package contract."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _asset(root: Path, name: str) -> bytes:
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise EngineNugetError(f"Missing or out-of-tree SDK file {path}")
    return path.read_bytes()


def _shader_payload(sdk: Path, backend: str) -> dict[str, bytes]:
    manifest = json.loads(_asset(sdk, SHADERS))
    if manifest["schema_version"] != 1 or backend not in manifest["targets"]:
        raise EngineNugetError(f"{sdk} has no compatible built-in {backend} artifacts")

    relevant = [item for item in manifest["artifacts"] if item["target"] == backend]
    if not relevant:
        raise EngineNugetError(f"{sdk} contains an empty {backend} shader manifest")
    for item in relevant:
        for path_field, hash_field in [("path", "sha256"), ("layout", "layout_sha256")]:
            name = item[path_field]
            data = _asset(sdk, SHARE + name)
            if not name.startswith(f"shaders/{backend}/") or digest(data) != item[hash_field]:
                raise EngineNugetError(f"Invalid {backend} artifact {name}")
    catalog_name = SHARE + manifest["catalog"]
    if digest(_asset(sdk, catalog_name)) != manifest["catalog_sha256"]:
        raise EngineNugetError(f"Built-in shader catalog hash mismatch in {sdk}")

    payload: dict[str, bytes] = {}
    for path in sorted((sdk / SHARE / "builtin_shaders").rglob("*")):
        if path.is_file() and path.suffix in {".json", ".shader", ".slang"}:
            name = path.relative_to(sdk).as_posix()
            # Windows checkouts may use CRLF. Verify the original catalog
            # above, then normalize the copy shared by both runtimes.
            payload[name] = _asset(sdk, name).replace(b"\r\n", b"\n")
    for path in sorted((sdk / SHARE / "shaders" / backend).rglob("*")):
        if path.is_file():
            name = path.relative_to(sdk).as_posix()
            payload[name] = _asset(sdk, name)
    payload[SHADERS] = json_bytes({
        **manifest, "catalog_sha256": digest(payload[catalog_name]),
        "targets": [backend], "artifacts": relevant,
    })
    return payload


def stage_sdk(repo: Path, sdk: Path, rid: str, output: Path) -> Path:
    backend = BACKENDS[rid]
    native, external = collect_native(sdk, rid)
    native_prefix = f"runtimes/{rid}/native/"
    payload = {native_prefix + name: data for name, data in native.items()}
    payload[f"runtimes/{rid}/lib/{FRAMEWORK}/{MANAGED}"] = _asset(sdk, f"csharp/lib/{MANAGED}")
    payload.update(_shader_payload(sdk, backend))
    revision = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", repo, "status", "--porcelain"]))
    payload[STAGE_MANIFEST] = json_bytes({
        "kind": "termin-engine-nuget-stage",
        "version": public_version(),
        "revision": revision,
        "dirty": dirty,
        "rid": rid,
        "backend": backend,
        "external_dependencies": external,
        "files": {name: digest(data) for name, data in payload.items()},
    })

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        candidate = Path(tmp) / output.name
        with zipfile.ZipFile(candidate, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                member = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
                member.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(member, data)
        candidate.replace(output)
    print(f"Staged {rid} {backend} at {output}; external dependencies: {', '.join(external)}")
    return output


def _read_stage(path: Path, rid: str, version: str) -> tuple[dict, dict[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise EngineNugetError(f"Duplicate entries in {path}")
        manifest = json.loads(archive.read(STAGE_MANIFEST))
        if (manifest["kind"], manifest["version"], manifest["rid"], manifest["backend"]) != (
            "termin-engine-nuget-stage", version, rid, BACKENDS[rid]
        ):
            raise EngineNugetError(f"{path} is not a compatible {rid} stage for {version}")
        files = manifest["files"]
        if set(names) != set(files) | {STAGE_MANIFEST}:
            raise EngineNugetError(f"Unexpected or missing members in {path}")
        payload = {name: archive.read(name) for name in files}
        if any(digest(data) != files[name] for name, data in payload.items()):
            raise EngineNugetError(f"File hash mismatch in {path}")
    return manifest, payload


def _combine_shaders(hashes: list[dict]) -> bytes:
    catalog_keys = ("schema_version", "catalog", "catalog_sha256")
    common = {key: hashes[0][key] for key in catalog_keys}
    if any({key: manifest[key] for key in catalog_keys} != common for manifest in hashes[1:]):
        raise EngineNugetError("Linux and Windows SDKs have different built-in shader catalogs")
    return json_bytes({
        **common,
        "targets": [target for manifest in hashes for target in manifest["targets"]],
        "artifacts": [artifact for manifest in hashes for artifact in manifest["artifacts"]],
    })


def _licenses(repo: Path) -> dict[str, bytes]:
    sources = {
        record.name: record.path for record in load_lock(repo).release_licenses
    }
    sources.update({
        "RecastNavigation": Path("termin-thirdparty/recastnavigation/License.txt"),
        "VulkanMemoryAllocator": Path("termin-thirdparty/vulkan-memory-allocator/LICENSE.txt"),
        "miniaudio": Path("termin-thirdparty/miniaudio/LICENSE"),
        "libogg": Path("termin-thirdparty/libogg/COPYING"),
        "libvorbis": Path("termin-thirdparty/libvorbis/COPYING"),
        "SDL2": Path("termin-thirdparty/sdl2/LICENSE.txt"),
    })
    return {
        f"licenses/{name}/{path.name}": _asset(repo, path.as_posix())
        for name, path in sources.items()
    }


def pack(repo: Path, stages: dict[str, Path], destination: Path) -> Path:
    version = public_version()
    payload: dict[str, bytes] = {}
    inputs, shaders = [], []
    for rid in BACKENDS:
        manifest, files = _read_stage(stages[rid], rid, version)
        shaders.append(json.loads(files.pop(SHADERS)))
        # Earlier SDKs installed a different font with the same filename.
        files.pop(SDK_FONT, None)
        inputs.append(manifest)
        for name, data in files.items():
            if name in payload and payload[name] != data:
                raise EngineNugetError(f"Linux and Windows SDK assets differ for {name}")
            payload[name] = data
    if len({manifest["revision"] for manifest in inputs}) != 1:
        raise EngineNugetError("Linux and Windows must be staged from the same base revision")

    repository_revision = inputs[0]["revision"] if not any(stage["dirty"] for stage in inputs) else ""
    payload[SHADERS] = _combine_shaders(shaders)
    payload[SDK_FONT] = _asset(repo, REDISTRIBUTABLE_FONT)
    payload["licenses/DroidSans/NOTICE.txt"] = (
        b"Droid Sans, digitized data copyright 2007 Google Corporation.\n"
        b"Licensed under the Apache License, Version 2.0. See licenses/Termin/LICENSE.\n"
        b"Source: RecastDemo/Contrib/imgui/misc/fonts/DroidSans.ttf.\n"
    )
    payload[f"ref/{FRAMEWORK}/{MANAGED}"] = payload[f"runtimes/win-x64/lib/{FRAMEWORK}/{MANAGED}"]
    payload["buildTransitive/net8.0/Termin.Engine.targets"] = _asset(
        repo, "termin-csharp/nuget/Termin.Engine.targets"
    )
    payload["README.md"] = _asset(repo, "termin-csharp/nuget/README.md")
    payload.update(_licenses(repo))
    payload[PACKAGE_MANIFEST] = json_bytes({
        "kind": "termin-engine-nuget",
        "version": version,
        "inputs": inputs,
        "files": {name: digest(data) for name, data in payload.items()},
    })
    definition = PackageDefinition(
        package_id=PACKAGE_ID,
        description="Full Termin C# scene and rendering runtime for Linux Vulkan and Windows D3D11.",
        target_frameworks=(FRAMEWORK,),
        dependencies=(),
        payloads=payload,
        tags="termin scene rendering avalonia vulkan d3d11 linux windows",
    )
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination) as tmp:
        candidate = compose_package(
            definition, Path(tmp), version=version,
            source_revision=repository_revision, license_path="licenses/Termin/LICENSE"
        )
        output = destination / candidate.name
        candidate.replace(output)
    print(f"{output} SHA-256 {digest(output.read_bytes())}")
    return output
