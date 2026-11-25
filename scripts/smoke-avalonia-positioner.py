"""Build and run the Avalonia Positioner sample against a full installed SDK."""

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", type=Path)
    parser.add_argument("--capture-dir", type=Path)
    phase = parser.add_mutually_exclusive_group()
    phase.add_argument("--build-only", action="store_true")
    phase.add_argument("--run-only", action="store_true")
    parser.add_argument("--interactive", action="store_true", help="Open the sample window.")
    args = parser.parse_args()

    windows = platform.system() == "Windows"
    if platform.system() not in {"Windows", "Linux"} or platform.machine().lower() not in {"amd64", "x86_64"}:
        parser.error("the sample requires Windows x64 or Linux x64")

    repo = Path(__file__).resolve().parents[1]
    sdk = (args.sdk_root or repo / "sdk").resolve()
    sample = repo / "termin-csharp" / "examples" / "AvaloniaPositioner"
    build = repo / "build" / "avalonia-positioner"
    app = build / "app"
    sdk_native = sdk / "csharp" / "runtimes" / ("win-x64" if windows else "linux-x64") / "native"
    binding = sdk_native / ("termin.dll" if windows else "termin.so")
    share = sdk / "share" / "termin"
    font = share / "fonts" / "DroidSans.ttf"
    for required in (binding, sdk / "csharp" / "lib" / "Termin.Native.dll",
                     share / "builtin-shader-artifacts.json", font):
        if not required.is_file():
            parser.error(f"full native and C# SDK with built-in shaders required, missing {required}")

    if not args.run_only:
        subprocess.run(
            ["dotnet", "build", sample / "AvaloniaPositioner.csproj",
             "-c", "Release", f"-p:TerminSdkRoot={sdk}", "-o", app],
            check=True,
        )
        shutil.copy2(binding, app)

    if not args.build_only:
        env = os.environ.copy()
        env["TERMIN_SHADER_ARTIFACT_ROOT"] = str(share)
        env["TERMIN_BUILTIN_SHADER_ROOT"] = str(share / "builtin_shaders")
        env["TERMIN_POSITIONER_FONT"] = str(font)
        if args.capture_dir:
            env["TERMIN_POSITIONER_CAPTURE_DIR"] = str(args.capture_dir.resolve())
        path_var = "PATH" if windows else "LD_LIBRARY_PATH"
        native_dirs = (sdk_native, sdk / ("bin" if windows else "lib"))
        env[path_var] = os.pathsep.join([*(str(directory) for directory in native_dirs), env.get(path_var, "")]).rstrip(os.pathsep)

        command = ["dotnet", app / "AvaloniaPositioner.dll"]
        if not args.interactive:
            command.append("--smoke")
        subprocess.run(command, cwd=app, env=env, check=True)


if __name__ == "__main__":
    main()
