#!/usr/bin/env python3
"""Build and run the small-physics native benchmark against an installed SDK."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, capture: bool = False, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(command, cwd=ROOT, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None, env=env)
    return result.stdout.strip() if capture else ""


def positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def cpu_name() -> str:
    if sys.platform.startswith("linux"):
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    return platform.processor()


def sdk_hashes(sdk: Path, library_dir: Path) -> dict[str, str]:
    hashes = {}
    for name in ("termin_base", "termin_qopt", "termin_robotics", "termin_physics_qopt"):
        found = False
        for library in sorted(library_dir.glob(f"*{name}*")):
            if library.is_file() and not library.is_symlink():
                hashes[str(library.relative_to(sdk))] = hashlib.sha256(library.read_bytes()).hexdigest()
                found = True
        if not found:
            raise ValueError(f"No installed library found for {name} in {library_dir}; run task build")
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=ROOT / "sdk")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build/benchmarks/physics-small")
    parser.add_argument("--output", type=Path, default=ROOT / "build/benchmarks/physics-small/results.json")
    parser.add_argument("--sdk-build-cache", type=Path, help="SDK CMakeCache.txt to preserve as build evidence")
    parser.add_argument("--steps", type=positive, default=1000)
    parser.add_argument("--warmups", type=positive, default=1)
    parser.add_argument("--repeats", type=positive, default=7)
    parser.add_argument("--cpu", type=int, help="pin the runner and native process to one CPU (Linux)")
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    build = args.build_dir.resolve()
    if args.cpu is not None:
        if not sys.platform.startswith("linux"):
            parser.error("--cpu is supported on Linux; configure affinity externally on other systems")
        os.sched_setaffinity(0, {args.cpu})
    # Package directory arguments prevent stale CMake cache entries selecting a
    # different SDK after --sdk changes on a subsequent invocation.
    package_dirs = [f"-D{name}_DIR={sdk / 'lib/cmake' / name}"
                    for name in ("termin_base", "termin_qopt", "termin_robotics", "termin_physics_qopt")]
    run(["cmake", "-S", str(ROOT / "benchmarks/physics-small"), "-B", str(build),
         f"-DCMAKE_PREFIX_PATH={sdk}", "-DCMAKE_BUILD_TYPE=Release", *package_dirs])
    run(["cmake", "--build", str(build), "--config", "Release", "--parallel", "2"])
    executable = build / "physics_small_benchmark"
    if sys.platform == "win32":
        executable = build / "Release/physics_small_benchmark.exe"
        if not executable.is_file():
            executable = build / "physics_small_benchmark.exe"
    env = os.environ.copy()
    library_dir = sdk / ("bin" if sys.platform == "win32" else "lib")
    if sys.platform == "win32":
        env["PATH"] = str(library_dir) + os.pathsep + env.get("PATH", "")
    elif sys.platform == "darwin":
        env["DYLD_LIBRARY_PATH"] = str(library_dir) + os.pathsep + env.get("DYLD_LIBRARY_PATH", "")
    else:
        env["LD_LIBRARY_PATH"] = str(library_dir) + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    hashes = sdk_hashes(sdk, library_dir)
    metadata = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": run(["git", "rev-parse", "HEAD"], capture=True),
        "source_status": run(["git", "status", "--short"], capture=True),
        "sdk": str(sdk), "sdk_library_sha256": hashes,
        "sdk_commit_verified": False,
        "platform": platform.platform(), "cpu": cpu_name(),
        "affinity": sorted(os.sched_getaffinity(0)) if sys.platform.startswith("linux") else None,
        "steps": args.steps, "warmups": args.warmups, "repeats": args.repeats,
        "benchmark_build_type": "Release",
        "sdk_build_cache": args.sdk_build_cache.read_text() if args.sdk_build_cache else None,
        "loader_environment": {key: env.get(key) for key in
                               ("PATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "LD_PRELOAD")},
        "cmake_cache": (build / "CMakeCache.txt").read_text(),
        "benchmark_source_sha256": hashlib.sha256((ROOT / "benchmarks/physics-small/bench.cpp").read_bytes()).hexdigest(),
        "note": "Kernel timings use fixed initial q and nonzero qdot; they are not additive step stage timings. Contact measures solve only; no collision query or controller is included.",
    }
    measurements = json.loads(run([str(executable), str(args.steps), str(args.warmups), str(args.repeats)],
                                  capture=True, env=env))
    if hashes != sdk_hashes(sdk, library_dir):
        raise ValueError("SDK libraries changed during measurement; rerun after the SDK build finishes")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"metadata": metadata, "measurements": measurements}, indent=2) + "\n")
    print("DOF    step us (median [min,max])      mass us    bias us    M/step    bias/step")
    for case in measurements["chains"]:
        step = case["step"]
        counts = case["counts_per_step"]
        print(f'{case["dof"]:3d}    {step["median_us"]:9.3f} [{step["min_us"]:.3f},{step["max_us"]:.3f}]'
              f'    {case["mass_matrix"]["median_us"]:8.3f} {case["bias"]["median_us"]:8.3f}'
              f'    {counts["mass_evaluations"]:6.2f} {counts["bias_evaluations"]:9.2f}')
    print(f'Contact solve median: {measurements["contact"]["solve"]["median_us"]:.3f} us')
    print(f"Results: {output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"[physics-small-benchmark] {error}", file=sys.stderr)
        sys.exit(1)
