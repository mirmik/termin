import argparse
import json
import pathlib
import subprocess
import sys


STAGE_EXTENSIONS = {
    "vertex": "vert.glsl",
    "fragment": "frag.glsl",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile Termin builtin Slang shaders to OpenGL artifacts."
    )
    parser.add_argument("--shaderc")
    parser.add_argument("--slangc")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--validate-existing",
        action="store_true",
        help="Validate prebuilt OpenGL artifacts without invoking termin_shaderc.",
    )
    args = parser.parse_args()

    shaderc = pathlib.Path(args.shaderc) if args.shaderc else None
    source_dir = pathlib.Path(args.source_dir)
    output_dir = pathlib.Path(args.output_dir)
    catalog_path = source_dir / "engine-shader-catalog.json"

    if not args.validate_existing and shaderc is None:
        print("termin-csharp: --shaderc is required unless --validate-existing is set", file=sys.stderr)
        return 2
    if shaderc is not None and not shaderc.exists():
        print(f"termin-csharp: termin_shaderc does not exist: {shaderc}", file=sys.stderr)
        return 2
    if not catalog_path.exists():
        print(f"termin-csharp: shader catalog does not exist: {catalog_path}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)

    with catalog_path.open("r", encoding="utf-8") as f:
        catalog = json.load(f)

    expected_outputs: list[pathlib.Path] = []
    failures: list[tuple[str, str, int]] = []
    compiled = 0
    for shader in catalog.get("shaders", []):
        if shader.get("language") != "slang":
            continue

        uuid = shader.get("uuid")
        if not uuid:
            print("termin-csharp: catalog shader entry is missing uuid", file=sys.stderr)
            return 2

        for stage, spec in shader.get("stages", {}).items():
            extension = STAGE_EXTENSIONS.get(stage)
            if extension is None:
                continue

            source_path = source_dir / spec["path"]
            entry = spec.get("entry", "vs_main" if stage == "vertex" else "fs_main")
            output_path = output_dir / f"{uuid}.{extension}"
            expected_outputs.append(output_path)
            expected_outputs.append(pathlib.Path(f"{output_path}.layout.json"))
            if args.validate_existing:
                continue
            cmd = [
                str(shaderc),
                "compile",
                "--language",
                "slang",
                "--target",
                "opengl",
                "--stage",
                stage,
                "--entry",
                entry,
                "--input",
                str(source_path),
                "--output",
                str(output_path),
                "-I",
                str(source_dir),
                "--debug-name",
                f"{uuid}:{stage}",
            ]
            if args.slangc:
                cmd.extend(["--slangc", args.slangc])
            result = subprocess.run(cmd)
            compiled += 1
            if result.returncode != 0:
                failures.append((uuid, stage, result.returncode))

    if args.validate_existing:
        missing = [path for path in expected_outputs if not path.exists()]
        if missing:
            for path in missing:
                print(f"termin-csharp: missing checked-in OpenGL shader artifact: {path}", file=sys.stderr)
            return 1
        print(f"termin-csharp: validated {len(expected_outputs)} checked-in OpenGL shader artifacts")
        return 0

    if failures:
        for uuid, stage, rc in failures:
            print(
                f"termin-csharp: failed to compile {uuid}:{stage} for OpenGL, rc={rc}",
                file=sys.stderr,
            )
        return 1

    print(f"termin-csharp: compiled {compiled} OpenGL builtin shader artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
