#!/bin/bash
# Install termin Python packages.
#
# Pip packages copy pre-built nanobind binding modules from
# $TERMIN_BINDINGS_DIR (normally build/<config>/bin). For normal pip installs
# they also bundle the shared C++ libraries from $TERMIN_SDK/lib into each
# package's local lib/ directory so the package can run without an SDK.
#
# By default, packages are installed into the current pip environment.
# With --target DIR, packages are installed directly into DIR (via
# `pip install --target`), skipping dependency resolution. This mode is
# used by build-sdk.sh to populate the bundled Python site-packages in
# sdk/lib/python3.*/site-packages/ without going through a second Python
# interpreter.
#
# Usage:
#   ./install-pip-packages.sh                             # Install into current pip env
#   ./install-pip-packages.sh --editable                  # Install termin in editable mode
#   ./install-pip-packages.sh --target DIR                # Install into DIR (no deps)
#   ./install-pip-packages.sh --force                     # Force-reinstall, bypass pip cache
#
# When native artifacts change, pip's wheel cache may still serve an old build.
# `compute_local_version()` mitigates this by embedding native artifact mtimes
# into the package version. --force trades rebuild time for guaranteed-fresh
# bindings.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EDITABLE=0
TARGET_DIR=""
FORCE=0

# Parse options first so --target takes effect before SDK discovery / logging.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --editable|-e) EDITABLE=1; shift ;;
        --force|-f) FORCE=1; shift ;;
        --target)
            TARGET_DIR="$2"
            shift 2
            ;;
        --target=*)
            TARGET_DIR="${1#--target=}"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --editable, -e   Install termin in editable mode (host env only)"
            echo "  --force, -f      Force-reinstall all packages, bypass pip cache"
            echo "                   (needed after SDK ABI-breaking rebuilds)"
            echo "  --target DIR     Install into DIR (typically bundled Python's site-packages)"
            echo "  --help, -h       Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [[ -n "$TARGET_DIR" && $EDITABLE -eq 1 ]]; then
    echo "ERROR: --editable is incompatible with --target" >&2
    exit 1
fi

# Locate termin SDK so pip packages can bundle shared libraries when needed.
#
# Discovery order mirrors termin_nanobind.runtime.find_sdk():
#   1. $TERMIN_SDK environment variable (if set and valid)
#   2. $SCRIPT_DIR/sdk (in-tree build via build-sdk-bindings.sh)
#   3. /opt/termin (system-wide install via install-to-opt.sh)
_sdk_valid() { [[ -d "$1/lib" ]]; }

if [[ -n "$TERMIN_SDK" ]]; then
    if ! _sdk_valid "$TERMIN_SDK"; then
        echo "ERROR: TERMIN_SDK=$TERMIN_SDK is set but does not contain lib/" >&2
        exit 1
    fi
elif _sdk_valid "$SCRIPT_DIR/sdk"; then
    export TERMIN_SDK="$SCRIPT_DIR/sdk"
elif _sdk_valid "/opt/termin"; then
    export TERMIN_SDK="/opt/termin"
else
    echo "ERROR: termin SDK not found." >&2
    echo "  Tried: \$TERMIN_SDK (unset), $SCRIPT_DIR/sdk, /opt/termin" >&2
    echo "  Run build-sdk-cpp.sh and build-sdk-bindings.sh first, or set TERMIN_SDK." >&2
    exit 1
fi
echo "Using TERMIN_SDK=$TERMIN_SDK"

if [[ -z "${TERMIN_BINDINGS_DIR:-}" ]]; then
    if [[ -n "${BUILD_DIR:-}" && -d "$BUILD_DIR/bin" ]]; then
        export TERMIN_BINDINGS_DIR="$BUILD_DIR/bin"
    elif [[ -d "$SCRIPT_DIR/build/Release/bin" ]]; then
        export TERMIN_BINDINGS_DIR="$SCRIPT_DIR/build/Release/bin"
    elif [[ -d "$SCRIPT_DIR/build/Debug/bin" ]]; then
        export TERMIN_BINDINGS_DIR="$SCRIPT_DIR/build/Debug/bin"
    fi
fi
if [[ -n "${TERMIN_BINDINGS_DIR:-}" ]]; then
    echo "Using TERMIN_BINDINGS_DIR=$TERMIN_BINDINGS_DIR"
fi

if [[ -z "${TERMIN_PIP_BUNDLE_LIBS:-}" ]]; then
    if [[ -n "$TARGET_DIR" || $EDITABLE -eq 1 ]]; then
        export TERMIN_PIP_BUNDLE_LIBS=0
    else
        export TERMIN_PIP_BUNDLE_LIBS=1
    fi
fi
if [[ -z "${TERMIN_PIP_COPY_TO_SOURCE:-}" ]]; then
    if [[ $EDITABLE -eq 1 ]]; then
        export TERMIN_PIP_COPY_TO_SOURCE=1
    else
        export TERMIN_PIP_COPY_TO_SOURCE=0
    fi
fi
echo "TERMIN_PIP_BUNDLE_LIBS=$TERMIN_PIP_BUNDLE_LIBS"
echo "TERMIN_PIP_COPY_TO_SOURCE=$TERMIN_PIP_COPY_TO_SOURCE"

if [[ -z "${PYTHON_BIN:-}" ]]; then
    PYTHON_LAUNCHER="$(command -v python3 || command -v python || true)"
    if [[ -n "$PYTHON_LAUNCHER" ]]; then
        PYTHON_BIN="$("$PYTHON_LAUNCHER" -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
    fi
fi
if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: python3 not found" >&2
    exit 1
fi
PIP_CMD=("$PYTHON_BIN" -m pip)
echo "Using pip: ${PIP_CMD[*]}"

if [[ -n "$TARGET_DIR" ]]; then
    mkdir -p "$TARGET_DIR"
    TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
    echo "Install mode: --target $TARGET_DIR (single pip invocation, no-deps)"
else
    echo "Install mode: current pip environment (sequential pip install)"
fi

# List of termin packages to install, in topological dependency order.
# Each entry is a path relative to SCRIPT_DIR.
#
# Note: several "components-*" C++ targets install into the same Python
# namespace as their parent subproject (e.g. termin.colliders owns both
# _colliders_native and _components_collision_native). Those are merged
# into the parent pip package rather than shipped separately to avoid
# filesystem overlap at install time.
# Packages are ordered by dependency: each package is listed after its
# install_requires. termin-app owns the termin namespace root and comes
# near the end, after all subpackages that extend termin.*.
PACKAGES=(
    termin-build-tools
    termin-nanobind-sdk
    termin-base
    termin-assets
    termin-mesh
    termin-graphics
    termin-materials
    termin-gui
    termin-display
    termin-csg
    termin-modules
    termin-inspect
    termin-components/termin-components-kinematic
    termin-scene
    termin-lighting
    termin-input
    termin-collision
    termin-render
    termin-render-passes
    termin-navmesh
    termin-physics
    termin-engine
    termin-skeleton
    termin-animation
    termin-components/termin-components-render
    termin-components/termin-components-mesh
    termin-nodegraph
    termin-app
    tcplot
)

# When --force is set, nuke each package's build cache and egg-info so
# setuptools re-runs the native artifact copy step from TERMIN_BINDINGS_DIR instead of
# reusing a cached wheel. This is the only reliable way to recover from
# an ABI-breaking SDK change — compute_local_version() fails when pip
# has already cached a wheel under the matching +sdkNNN suffix.
if [[ $FORCE -eq 1 ]]; then
    # Clear ONLY pip's build artefacts — build/lib.*, build/bdist.*,
    # *.egg-info. The `build/` dir also houses CMake build trees
    # (Release/, etc.) for the C++ libs whose output we copy into the
    # pip wheel; wiping that wastes 5+ minutes of recompile and we
    # never needed to in the first place, pip cache lives in
    # build/lib*/ + build/bdist*/ only.
    echo "--force: clearing per-package pip build caches before install"
    for pkg in "${PACKAGES[@]}"; do
        rm -rf "$SCRIPT_DIR/$pkg"/build/lib.* \
               "$SCRIPT_DIR/$pkg"/build/bdist.* \
               "$SCRIPT_DIR/$pkg"/*.egg-info 2>/dev/null || true
    done
fi

FORCE_FLAGS=()
if [[ $FORCE -eq 1 ]]; then
    # --no-deps is mandatory alongside --force-reinstall: pip otherwise
    # tries to re-resolve dependencies like `tcbase`, `tmesh`, `tgfx`
    # that live locally and are not on PyPI — fails with "No matching
    # distribution found". The PyPI transitive deps (numpy, nanobind,
    # ...) have already been installed by the initial no-force run, so
    # skipping their re-resolve is harmless here.
    FORCE_FLAGS=(--force-reinstall --no-cache-dir --no-deps)
fi

if [[ -n "$TARGET_DIR" ]]; then
    # --target mode: install ALL packages in a single pip invocation.
    # This is required because pip --target treats each package-dir
    # overlap (multiple packages contributing to termin/*) as a conflict
    # and either errors out (no --upgrade) or wipes previously-installed
    # subdirs (with --upgrade). When given the whole set at once, pip
    # merges contributions correctly into the same namespace.
    #
    # We pass --no-deps because the dependency closure is the same set
    # we're already enumerating, and --no-deps avoids pulling PyPI
    # packages (numpy, nanobind, …) into the SDK — those are provided
    # separately by BUNDLE_PACKAGES_EXTERNAL in termin/CMakeLists.txt.
    #
    # Make termin_build.cmake_ext importable while pip prepares metadata for
    # sibling packages. Do not install into the host Python environment here:
    # build-sdk.sh uses --target specifically to keep the SDK self-contained.
    export PYTHONPATH="$SCRIPT_DIR/termin-build-tools${PYTHONPATH:+:$PYTHONPATH}"
    PIP_ARGS=(--no-build-isolation --no-deps --upgrade --target "$TARGET_DIR" "${FORCE_FLAGS[@]}")
    for pkg in "${PACKAGES[@]}"; do
        PIP_ARGS+=("$SCRIPT_DIR/$pkg")
    done
    echo ""
    echo "========================================"
    echo "  Installing ${#PACKAGES[@]} packages into $TARGET_DIR"
    echo "========================================"
    echo ""
    "${PIP_CMD[@]}" install "${PIP_ARGS[@]}"
else
    # Host-env mode: sequential installs so errors are attributed to a
    # specific package and intermediate state is inspectable.
    EDITABLE_FLAG=()
    NODEPS_FLAG=()
    if [[ $EDITABLE -eq 1 ]]; then
        # Editable installs pre-suppose all external dependencies are already
        # installed in the environment (see setup-test-venv.sh). --no-deps
        # avoids pip trying to resolve heavy/unavailable packages like pyassimp
        # during the editable loop.
        EDITABLE_FLAG=(-e)
        NODEPS_FLAG=(--no-deps)
    fi
    for pkg in "${PACKAGES[@]}"; do
        mode=""
        if [[ $EDITABLE -eq 1 ]]; then
            mode=" (editable)"
        fi
        echo ""
        echo "========================================"
        echo "  Installing $pkg$mode"
        echo "========================================"
        echo ""
        "${PIP_CMD[@]}" install --no-build-isolation "${FORCE_FLAGS[@]}" "${NODEPS_FLAG[@]}" "${EDITABLE_FLAG[@]}" "$SCRIPT_DIR/$pkg"
    done
fi

echo ""
echo "========================================"
echo "  All pip packages installed!"
echo "========================================"
