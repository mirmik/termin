#!/bin/bash
# Run C/C++ static analysis through clang-tidy.
#
# This is an opt-in lint entry point. It configures a dedicated CMake build
# directory with compile_commands.json and runs a narrow defect-oriented
# clang-tidy baseline over repository-owned translation units.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_PREFIX="${SDK_PREFIX:-$SCRIPT_DIR/sdk}"
BUILD_TYPE="Release"
BUILD_DIR="${BUILD_DIR:-}"
BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"
VULKAN_MODE="on"
SDL_MODE="on"
OPENGL_MODE="on"
CCACHE_MODE="on"
CLEAN=0
CONFIGURE_ONLY=0
NO_CONFIGURE=0
CMAKE_GENERATOR_NAME="${CMAKE_GENERATOR_NAME:-${TERMIN_CMAKE_GENERATOR:-}}"
CLANG_TIDY_BIN="${CLANG_TIDY_BIN:-clang-tidy}"
CHECKS="${CLANG_TIDY_CHECKS:--*,clang-diagnostic-*,-clang-diagnostic-nan-infinity-disabled,clang-analyzer-*,-clang-analyzer-deadcode.*,-clang-analyzer-optin.*,-clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling}"
WARNINGS_AS_ERRORS="${CLANG_TIDY_WARNINGS_AS_ERRORS:-*}"
HEADER_FILTER="^$SCRIPT_DIR/(termin-|tcplot|cmake|scripts|tools|CMakeLists\.txt)"
PATH_FILTERS=()

print_usage() {
    cat <<EOF
Usage: $0 [OPTIONS] [path ...]

Options:
  --debug, -d          Use Debug CMake build type
  --clean, -c          Remove lint build directory before configuring
  --configure-only     Configure CMake and generate compile_commands.json only
  --no-configure       Reuse existing compile_commands.json
  --no-vulkan          Disable Vulkan support
  --vulkan             Enable Vulkan support (default)
  --no-sdl             Disable SDL2 support
  --sdl                Enable SDL2 support (default)
  --no-opengl          Disable OpenGL support
  --opengl             Enable OpenGL support (default)
  --ccache             Use ccache if available (default)
  --no-ccache          Disable ccache compiler launcher
  --ninja              Use Ninja generator for a new build dir
  --jobs N, -j N       Parallel clang-tidy jobs (default: nproc)
  --checks CHECKS      Override clang-tidy checks
  --warnings-as-errors CHECKS
                       Override clang-tidy warnings-as-errors (default: *)
  --clang-tidy PATH    clang-tidy executable (default: clang-tidy)
  --help, -h           Show this help

Arguments:
  path                 Optional repository-relative file or directory filters.
                       Without filters, all repository-owned C/C++ translation
                       units from compile_commands.json are checked.

Environment:
  SDK_PREFIX           SDK prefix for CMake dependencies (default: ./sdk)
  BUILD_DIR            CMake build directory (default: ./build/<type>-lint)
  BUILD_JOBS           Parallel clang-tidy jobs
  CLANG_TIDY_BIN       clang-tidy executable
  CLANG_TIDY_CHECKS    clang-tidy checks string
  CLANG_TIDY_WARNINGS_AS_ERRORS
                       clang-tidy warnings-as-errors string
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --debug|-d) BUILD_TYPE="Debug"; shift ;;
        --clean|-c) CLEAN=1; shift ;;
        --configure-only) CONFIGURE_ONLY=1; shift ;;
        --no-configure) NO_CONFIGURE=1; shift ;;
        --no-vulkan) VULKAN_MODE="off"; shift ;;
        --vulkan) VULKAN_MODE="on"; shift ;;
        --no-sdl) SDL_MODE="off"; shift ;;
        --sdl) SDL_MODE="on"; shift ;;
        --no-opengl) OPENGL_MODE="off"; shift ;;
        --opengl) OPENGL_MODE="on"; shift ;;
        --ccache) CCACHE_MODE="on"; shift ;;
        --no-ccache) CCACHE_MODE="off"; shift ;;
        --ninja) CMAKE_GENERATOR_NAME="Ninja"; shift ;;
        --jobs|-j)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: $1 requires a value" >&2
                exit 1
            fi
            BUILD_JOBS="$2"
            shift 2
            ;;
        --checks)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --checks requires a value" >&2
                exit 1
            fi
            CHECKS="$2"
            shift 2
            ;;
        --warnings-as-errors)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --warnings-as-errors requires a value" >&2
                exit 1
            fi
            WARNINGS_AS_ERRORS="$2"
            shift 2
            ;;
        --clang-tidy)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --clang-tidy requires a value" >&2
                exit 1
            fi
            CLANG_TIDY_BIN="$2"
            shift 2
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        --*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            PATH_FILTERS+=("$1")
            shift
            ;;
    esac
done

if [[ -z "$BUILD_DIR" ]]; then
    BUILD_DIR="$SCRIPT_DIR/build/${BUILD_TYPE}-lint"
fi

case "$VULKAN_MODE" in
    off) TERMIN_ENABLE_VULKAN=OFF ;;
    on)  TERMIN_ENABLE_VULKAN=ON ;;
esac
case "$SDL_MODE" in
    off) TERMIN_ENABLE_SDL=OFF ;;
    on)  TERMIN_ENABLE_SDL=ON ;;
esac
case "$OPENGL_MODE" in
    off) TERMIN_ENABLE_OPENGL=OFF ;;
    on)  TERMIN_ENABLE_OPENGL=ON ;;
esac
case "$CCACHE_MODE" in
    off) TERMIN_USE_CCACHE=OFF ;;
    on)  TERMIN_USE_CCACHE=ON ;;
esac

echo ""
echo "========================================"
echo "  C/C++ lint ($BUILD_TYPE)"
echo "  mode: clang-tidy"
echo "========================================"
echo ""
echo "Source dir:  $SCRIPT_DIR"
echo "Build dir:   $BUILD_DIR"
echo "SDK prefix:  $SDK_PREFIX"
echo "Checks:      $CHECKS"
echo "Werror:      $WARNINGS_AS_ERRORS"
echo "clang-tidy:  $CLANG_TIDY_BIN"
echo "Vulkan:      $TERMIN_ENABLE_VULKAN"
echo "SDL2:        $TERMIN_ENABLE_SDL"
echo "OpenGL:      $TERMIN_ENABLE_OPENGL"
echo "ccache:      $TERMIN_USE_CCACHE"
echo "Unity build: OFF"
echo "PCH:         OFF"
echo "Generator:   ${CMAKE_GENERATOR_NAME:-existing/default}"
echo "Jobs:        $BUILD_JOBS"
if (( ${#PATH_FILTERS[@]} > 0 )); then
    echo "Path filters:${PATH_FILTERS[*]/#/ }"
fi
echo ""

if [[ $CLEAN -eq 1 ]]; then
    echo "Cleaning $BUILD_DIR..."
    rm -rf "$BUILD_DIR"
fi

if [[ $NO_CONFIGURE -eq 0 ]]; then
    PY_EXEC="$(command -v python3 || command -v python || true)"
    if [[ -z "$PY_EXEC" ]]; then
        echo "ERROR: python3 not found; cannot run build doctor" >&2
        exit 1
    fi
    if ! PYTHONPATH="$SCRIPT_DIR/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}" \
        "$PY_EXEC" -m termin_build.sdk --repo-root "$SCRIPT_DIR" doctor \
        --profile sdk-cpp \
        --vulkan "$TERMIN_ENABLE_VULKAN" \
        --init-submodules; then
        echo "ERROR: Termin build doctor failed" >&2
        exit 1
    fi

    cmake_args=()
    if [[ -n "$CMAKE_GENERATOR_NAME" && ! -f "$BUILD_DIR/CMakeCache.txt" ]]; then
        cmake_args+=(-G "$CMAKE_GENERATOR_NAME")
    fi

    if ! cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" "${cmake_args[@]}" \
        -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$SDK_PREFIX" \
        -DCMAKE_PREFIX_PATH="$SDK_PREFIX" \
        -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF \
        -DTERMIN_USE_CCACHE="$TERMIN_USE_CCACHE" \
        -DTERMIN_ENABLE_UNITY_BUILD=OFF \
        -DTERMIN_ENABLE_PCH=OFF \
        -DTERMIN_BUILD_PYTHON=OFF \
        -DTERMIN_BUILD_TESTS=OFF \
        -DTERMIN_BUILD_TGFX2_TESTS=OFF \
        -DTERMIN_BUILD_WINDOW_TESTS=OFF \
        -DTERMIN_ENABLE_VULKAN="$TERMIN_ENABLE_VULKAN" \
        -DTERMIN_ENABLE_SDL="$TERMIN_ENABLE_SDL" \
        -DTERMIN_ENABLE_OPENGL="$TERMIN_ENABLE_OPENGL" \
        -DTERMIN_BUILD_EDITOR_MINIMAL=OFF \
        -DTERMIN_BUILD_LAUNCHER=OFF \
        -DTERMIN_BUNDLE_PYTHON=OFF; then
        echo "ERROR: CMake configure failed" >&2
        exit 1
    fi
fi

COMPILE_COMMANDS="$BUILD_DIR/compile_commands.json"
if [[ ! -f "$COMPILE_COMMANDS" ]]; then
    echo "ERROR: compile_commands.json not found: $COMPILE_COMMANDS" >&2
    echo "Run without --no-configure first." >&2
    exit 1
fi

if [[ $CONFIGURE_ONLY -eq 1 ]]; then
    echo "Generated $COMPILE_COMMANDS"
    exit 0
fi

if ! command -v "$CLANG_TIDY_BIN" >/dev/null 2>&1; then
    echo "ERROR: clang-tidy not found: $CLANG_TIDY_BIN" >&2
    echo "Install clang-tidy or set CLANG_TIDY_BIN=/path/to/clang-tidy." >&2
    exit 1
fi

export TERMIN_REPO_ROOT="$SCRIPT_DIR"
export TERMIN_LINT_BUILD_DIR="$BUILD_DIR"
export TERMIN_CLANG_TIDY_BIN="$CLANG_TIDY_BIN"
export TERMIN_CLANG_TIDY_CHECKS="$CHECKS"
export TERMIN_CLANG_TIDY_WARNINGS_AS_ERRORS="$WARNINGS_AS_ERRORS"
export TERMIN_CLANG_TIDY_HEADER_FILTER="$HEADER_FILTER"
export TERMIN_CLANG_TIDY_JOBS="$BUILD_JOBS"
export TERMIN_LINT_PATH_FILTERS="$(printf '%s\n' "${PATH_FILTERS[@]}")"

python3 <<'PY'
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys

repo = Path(os.environ["TERMIN_REPO_ROOT"]).resolve()
build_dir = Path(os.environ["TERMIN_LINT_BUILD_DIR"]).resolve()
clang_tidy = os.environ["TERMIN_CLANG_TIDY_BIN"]
checks = os.environ["TERMIN_CLANG_TIDY_CHECKS"]
warnings_as_errors = os.environ["TERMIN_CLANG_TIDY_WARNINGS_AS_ERRORS"]
header_filter = os.environ["TERMIN_CLANG_TIDY_HEADER_FILTER"]
jobs = int(os.environ.get("TERMIN_CLANG_TIDY_JOBS", "1"))
filters_raw = os.environ.get("TERMIN_LINT_PATH_FILTERS", "")
path_filters = [item for item in filters_raw.splitlines() if item]

source_suffixes = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".m",
    ".mm",
}
excluded_parts = {
    ".git",
    "build",
    "sdk",
    "termin-thirdparty",
    "NavMeshes",
}


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def repo_relative(path: Path) -> Path:
    try:
        return path.relative_to(repo)
    except ValueError:
        return path


def matches_user_filters(path: Path) -> bool:
    if not path_filters:
        return True
    rel = str(repo_relative(path))
    for item in path_filters:
        candidate = (repo / item).resolve()
        if path == candidate or is_relative_to(path, candidate):
            return True
        if rel == item or rel.startswith(item.rstrip("/") + "/"):
            return True
    return False


def include_entry(file_value: str) -> bool:
    path = Path(file_value)
    if not path.is_absolute():
        path = (repo / path).resolve()
    else:
        path = path.resolve()

    if not is_relative_to(path, repo):
        return False
    rel = repo_relative(path)
    if any(part in excluded_parts for part in rel.parts):
        return False
    if path.suffix.lower() not in source_suffixes:
        return False
    if not matches_user_filters(path):
        return False
    return True


compile_commands = build_dir / "compile_commands.json"
with compile_commands.open("r", encoding="utf-8") as stream:
    entries = json.load(stream)

files: list[str] = []
seen: set[str] = set()
for entry in entries:
    file_value = entry.get("file")
    if not file_value or not include_entry(file_value):
        continue
    path = Path(file_value)
    if not path.is_absolute():
        path = (repo / path).resolve()
    resolved = str(path)
    if resolved not in seen:
        seen.add(resolved)
        files.append(resolved)

files.sort()
if not files:
    print("No C/C++ translation units matched lint filters.", file=sys.stderr)
    sys.exit(0)

print(f"clang-tidy translation units: {len(files)}")
for item in files[:20]:
    print(f"  {repo_relative(Path(item))}")
if len(files) > 20:
    print(f"  ... {len(files) - 20} more")


def run_one(path: str) -> tuple[str, int, str]:
    cmd = [
        clang_tidy,
        path,
        "-p",
        str(build_dir),
        f"--checks={checks}",
        f"--warnings-as-errors={warnings_as_errors}",
        f"--header-filter={header_filter}",
    ]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return path, proc.returncode, proc.stdout


failed = False
with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
    futures = [executor.submit(run_one, item) for item in files]
    for future in as_completed(futures):
        path, returncode, output = future.result()
        if output:
            print(f"\n--- clang-tidy: {repo_relative(Path(path))} ---")
            print(output, end="" if output.endswith("\n") else "\n")
        if returncode != 0:
            failed = True

if failed:
    sys.exit(1)
PY

status=$?
if [[ $status -ne 0 ]]; then
    echo ""
    echo "ERROR: C/C++ lint failed" >&2
    exit "$status"
fi

echo ""
echo "========================================"
echo "  C/C++ lint finished"
echo "========================================"
