"""Stage, package, verify, and publish the full C# Termin SDK."""

import argparse
from pathlib import Path
import os
import platform
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "core/termin-build-tools"))

from termin_build import engine_nuget_product as product


def main():
    default_root = REPO / "build/engine-nuget"
    host_rid = {"Windows": "win-x64", "Linux": "linux-x64"}.get(platform.system())
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    stage = commands.add_parser("stage", help="Stage an installed native and full C# SDK for this host.")
    stage.add_argument("--sdk-root", type=Path, default=Path(os.environ.get("SDK_PREFIX", REPO / "sdk")))
    stage.add_argument("--rid", choices=product.BACKENDS, default=host_rid)
    stage.add_argument("--output", type=Path)

    pack = commands.add_parser("pack", help="Assemble the staged Windows and Linux inputs.")
    pack.add_argument("--linux-stage", type=Path, default=default_root / "linux-x64.zip")
    pack.add_argument("--windows-stage", type=Path, default=default_root / "win-x64.zip")
    pack.add_argument("--destination", type=Path, default=REPO / "dist/engine-nuget")

    smoke = commands.add_parser("smoke", help="Build and run an external PackageReference consumer.")
    smoke.add_argument("--package", type=Path, default=REPO / "dist/engine-nuget" / f"{product.PACKAGE_ID}.{product.public_version()}.nupkg")
    smoke.add_argument("--work-dir", type=Path, default=default_root / f"gate-{host_rid}")
    smoke.add_argument("--dependency-source", default="https://api.nuget.org/v3/index.json")
    phase = smoke.add_mutually_exclusive_group()
    phase.add_argument("--build-only", action="store_true")
    phase.add_argument("--run-only", action="store_true")

    publish = commands.add_parser("publish", help="Verify both consumer reports and check or submit to NuGet.org.")
    publish.add_argument("--package", type=Path, default=REPO / "dist/engine-nuget" / f"{product.PACKAGE_ID}.{product.public_version()}.nupkg")
    publish.add_argument("--linux-report", type=Path, default=default_root / "gate-linux-x64/report.json")
    publish.add_argument("--windows-report", type=Path, default=default_root / "gate-win-x64/report.json")
    publish.add_argument("--upload", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "stage":
            if args.rid is None:
                parser.error("provide --rid for the installed SDK")
            product.stage_sdk(REPO, args.sdk_root.resolve(), args.rid,
                              (args.output or default_root / f"{args.rid}.zip").resolve())
        elif args.command == "pack":
            product.pack(REPO, {"linux-x64": args.linux_stage, "win-x64": args.windows_stage},
                         args.destination.resolve())
        elif args.command == "smoke":
            from termin_build.engine_nuget_gate import smoke_candidate
            if host_rid is None or platform.machine().lower() not in {"amd64", "x86_64"}:
                parser.error("the consumer gate requires Windows or Linux x64")
            smoke_candidate(REPO, args.package.resolve(), args.work_dir.resolve(), host_rid,
                            args.dependency_source, build_only=args.build_only, run_only=args.run_only)
        else:
            from termin_build.engine_nuget_gate import publish_candidate
            publish_candidate(args.package.resolve(),
                              {"linux-x64": args.linux_report, "win-x64": args.windows_report},
                              upload=args.upload)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        print(f"Termin.Engine NuGet build error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
