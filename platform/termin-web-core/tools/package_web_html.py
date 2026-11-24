"""Bundle a Termin web page with its ES modules, Wasm and runtime package."""
import argparse
import base64
import gzip
from html import escape
import os
from pathlib import Path
import re
import sys
import tempfile


# The web modules use static imports of sibling .mjs files. Give each module a
# bare specifier since a blob: module has no base URL for relative imports.
STATIC_IMPORT = re.compile(
    r"""^([ \t]*(?:import|export)\s+(?:[\w\s{},*]+?\bfrom\s*)?)(["'])([^"'\s]+)\2""",
    re.MULTILINE,
)
MODULE_SCRIPT = re.compile(r'<script type="module">(.*?)</script>', re.DOTALL)


def packed_asset(name, mime, data):
    packed = gzip.compress(data, compresslevel=9, mtime=0)
    encoded = base64.b64encode(packed).decode("ascii")
    return f'<script type="application/octet-stream" data-termin-asset="{name}" data-mime="{mime}">{encoded}</script>'


def bundle(source, scene_package, project_name=None, *, wasm_name="termin_web_core.wasm"):
    modules = {}
    directory = source.parent

    def resolve(match):
        prefix, quote, specifier = match.groups()
        file, _, _ = specifier.partition("?")
        if not re.fullmatch(r"\./[\w.-]+\.mjs", file):
            raise ValueError(f"unsupported web module import: {specifier}")
        name = file[2:]
        key = f"termin-web/{name}"
        if key not in modules:
            modules[key] = None  # Static imports can form a cycle.
            code = STATIC_IMPORT.sub(resolve, (directory / name).read_text(encoding="utf-8"))
            modules[key] = packed_asset(key, "text/javascript", code.encode("utf-8"))
        return f"{prefix}{quote}{key}{quote}"

    html = source.read_text(encoding="utf-8")
    if project_name is not None:
        html = html.replace("</head>", f'<meta name="termin-project" content="{escape(project_name)}">\n</head>', 1)
    scripts = list(MODULE_SCRIPT.finditer(html))
    if len(scripts) != 1:
        raise ValueError("expected one inline page entry module")
    script = scripts[0]
    entry = STATIC_IMPORT.sub(resolve, script[1])
    embedded = list(modules.values())
    package_name = "scene.trpkg" if scene_package else "graphics.trpkg"
    assets = (
        (wasm_name, directory / wasm_name, "application/wasm"),
        (package_name, scene_package or directory / package_name, "application/octet-stream"),
    )
    for name, path, mime in assets:
        embedded.append(packed_asset(name, mime, path.read_bytes()))
    if html.count("</head>") != 1 or html.index("</head>") > script.start():
        raise ValueError("expected the page entry module after </head>")
    loader = Path(__file__).with_name("standalone-loader.js").read_text(encoding="utf-8")
    embedded.append(f'<script type="text/plain" id="termin-web-entry">{entry}</script>')
    embedded.append(f"<script>{loader}</script>")
    return html[:script.start()] + "\n".join(embedded) + html[script.end():]


def bundle_project(source, project, entry_scene):
    from termin.project_build.common import (
        cleanup_project_build_runtime_state,
        initialize_project_build_runtime_state,
        preload_project_resources,
        read_project_name,
    )
    from termin.project_build.runtime_package_blob import write_runtime_package_blob
    from termin.project_build.runtime_package_exporter import export_runtime_package
    from termin.project_build.runtime_package_validator import validate_runtime_package

    # Use the exact offline tools and built-ins selected by task build:web.
    cache = source.parent.parent / "CMakeCache.txt"
    tools = dict(re.findall(r"^(TERMIN_WEB_HOST_\w+):(?:PATH|FILEPATH)=(.+)$", cache.read_text(), re.MULTILINE))
    os.environ["TERMIN_SLANGC"] = tools["TERMIN_WEB_HOST_SLANGC"]
    os.environ["TERMIN_WGSL_VALIDATOR"] = tools["TERMIN_WEB_HOST_WGSL_VALIDATOR"]
    project = project.resolve()
    log_prefix = "[WebPackage]"
    initialize_project_build_runtime_state(log_prefix)
    try:
        preload_project_resources(project, log_prefix)
        with tempfile.TemporaryDirectory(prefix="termin-web-project-") as staging:
            root = Path(staging)
            result = export_runtime_package(
                project, entry_scene, root / "package",
                shader_compiler=tools["TERMIN_WEB_HOST_SHADERC"],
                builtin_shader_artifact_root=tools["TERMIN_WEB_HOST_BUILTIN_SHADER_ROOT"],
                shader_targets=("webgpu", "webgl2"),
                target_platform=("web", "wasm32"),
                resource_policy="strict",
            )
            diagnostics = [*result.diagnostics, *validate_runtime_package(result.package_dir)]
            for item in diagnostics:
                print(f"{item.level}: {item.path}: {item.message}", file=sys.stderr)
            if any(item.level == "error" for item in diagnostics):
                raise ValueError("Web runtime package failed validation")
            blob = write_runtime_package_blob(result.package_dir, root / "scene.trpkg")
            return bundle(source, blob, read_project_name(project))
    finally:
        cleanup_project_build_runtime_state(log_prefix)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="built demo HTML beside its runtime assets")
    parser.add_argument("output", type=Path, help="standalone output HTML")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--scene-package", type=Path, help="runtime .trpkg to embed in the scene viewer")
    inputs.add_argument("--project", type=Path, help="Termin project directory to export with the host SDK")
    parser.add_argument("--wasm", help="Wasm module beside the built page (default: termin_web_core.wasm)")
    parser.add_argument("--entry-scene", type=Path, help="entry scene relative to the project")
    args = parser.parse_args()
    if bool(args.project) != bool(args.entry_scene):
        parser.error("--project and --entry-scene must be used together")
    if args.wasm and (args.project or not re.fullmatch(r"[\w.-]+\.wasm", args.wasm)):
        parser.error("--wasm expects a local .wasm filename for a prebuilt page")
    if args.output.suffix.lower() != ".html" or args.source.resolve() == args.output.resolve():
        parser.error("output must be a separate .html file")
    if args.project:
        html = bundle_project(args.source, args.project, args.entry_scene)
    else:
        html = bundle(args.source, args.scene_package, wasm_name=args.wasm or "termin_web_core.wasm")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
