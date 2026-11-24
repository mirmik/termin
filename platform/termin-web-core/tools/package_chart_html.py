"""Bundle a built Termin chart demo and its local ES modules, Wasm and graphics package."""
import argparse
import base64
import json
from pathlib import Path
import re


# The chart modules use static imports of sibling .mjs files. Give each module a
# bare specifier since a data: module has no base URL for relative imports.
STATIC_IMPORT = re.compile(
    r"""^([ \t]*(?:import|export)\s+(?:[\w\s{},*]+?\bfrom\s*)?)(["'])([^"'\s]+)\2""",
    re.MULTILINE,
)
MODULE_SCRIPT = re.compile(r'(<script type="module">)(.*?)(</script>)', re.DOTALL)
ASSETS = {"termin_web_core.wasm": "application/wasm", "graphics.trpkg": "application/octet-stream"}


def data_url(data, mime):
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def bundle(source):
    modules = {}
    directory = source.parent

    def resolve(match):
        prefix, quote, specifier = match.groups()
        file, _, _ = specifier.partition("?")
        if not re.fullmatch(r"\./[\w.-]+\.mjs", file):
            raise ValueError(f"unsupported chart module import: {specifier}")
        name = file[2:]
        key = f"termin-chart/{name}"
        if key not in modules:
            modules[key] = None  # Static imports can form a cycle.
            code = STATIC_IMPORT.sub(resolve, (directory / name).read_text(encoding="utf-8"))
            modules[key] = data_url(code.encode("utf-8"), "text/javascript")
        return f"{prefix}{quote}{key}{quote}"

    html = source.read_text(encoding="utf-8")
    scripts = list(MODULE_SCRIPT.finditer(html))
    if len(scripts) != 1:
        raise ValueError("expected one inline chart entry module")
    script = scripts[0]
    entry = STATIC_IMPORT.sub(resolve, script[2])
    import_map = json.dumps({"imports": modules}, separators=(",", ":"))
    embedded = []
    for name, mime in ASSETS.items():
        url = data_url((directory / name).read_bytes(), mime)
        embedded.append(f'<link id="termin-web-asset-{name}" rel="termin-web-asset" href="{url}">')
    embedded.append(f'<script type="importmap">{import_map}</script>')
    if html.count("</head>") != 1 or html.index("</head>") > script.start():
        raise ValueError("expected the chart entry module after </head>")
    head = html[:script.start()].replace("</head>", "\n".join(embedded) + "\n</head>")
    return head + script[1] + entry + script[3] + html[script.end():]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="built demo HTML beside its runtime assets")
    parser.add_argument("output", type=Path, help="standalone output HTML")
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("output must differ from the input demo")
    args.output.write_text(bundle(args.source), encoding="utf-8")


if __name__ == "__main__":
    main()
