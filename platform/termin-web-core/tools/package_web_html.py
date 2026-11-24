"""Bundle a Termin web page with its ES modules, Wasm and runtime package."""
import argparse
import base64
import gzip
from pathlib import Path
import re


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


def bundle(source, scene_package):
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
    scripts = list(MODULE_SCRIPT.finditer(html))
    if len(scripts) != 1:
        raise ValueError("expected one inline page entry module")
    script = scripts[0]
    entry = STATIC_IMPORT.sub(resolve, script[1])
    embedded = list(modules.values())
    package_name = "scene.trpkg" if scene_package else "graphics.trpkg"
    assets = (
        ("termin_web_core.wasm", directory / "termin_web_core.wasm", "application/wasm"),
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="built demo HTML beside its runtime assets")
    parser.add_argument("output", type=Path, help="standalone output HTML")
    parser.add_argument("--scene-package", type=Path, help="runtime .trpkg to embed in the scene viewer")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".html" or args.source.resolve() == args.output.resolve():
        parser.error("output must be a separate .html file")
    args.output.write_text(bundle(args.source, args.scene_package), encoding="utf-8")


if __name__ == "__main__":
    main()
