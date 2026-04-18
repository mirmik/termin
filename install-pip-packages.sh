#!/bin/bash
# Install termin Python packages.
#
# Pip packages are THIN: they ship only nanobind binding .so files plus
# Python wrappers. The shared C++ libraries live in $TERMIN_SDK (default:
# ./sdk). build-sdk-cpp.sh + build-sdk-bindings.sh must be run first to
# produce the SDK.
#
# By default, packages are installed into the current pip environment.
# With --target DIR, packages are installed directly into DIR (via
# `pip install --target`), skipping dependency resolution. This mode is
# used by build-sdk.sh to populate the bundled Python site-packages in
# sdk/lib/python3.10/site-packages/ without going through a second Python
# interpreter.
#
# Usage:
#   ./install-pip-packages.sh                             # Install into current pip env
#   ./install-pip-packages.sh --editable                  # Install termin in editable mode
#   ./install-pip-packages.sh --target DIR                # Install into DIR (no deps)
#   ./install-pip-packages.sh --force                     # Force-reinstall, bypass pip cache
#
# When the SDK changes in an ABI-breaking way (namespace rename, virtual
# table layout, enum re-ordering, ...) the nanobind .so files that pip
# copies out of $TERMIN_SDK change, but pip's wheel cache may still serve
# an old build. `compute_local_version()` mitigates this by embedding the
# SDK mtime into the package version, but if a wheel is already cached
# under that version string — or worse, a package is not in the list
# below and was installed ad-hoc — pip stays happy with the stale install.
# --force trades rebuild time for guaranteed-fresh bindings.

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

# Locate termin SDK so thin pip packages can copy their pre-built bindings.
# Used both at install time (TerminCMakeBuildExt copies _X_native.so from
# $TERMIN_SDK/lib/python/termin/) and at runtime (preload_sdk_libs).
#
# Discovery order mirrors termin_nanobind.runtime.find_sdk():
#   1. $TERMIN_SDK environment variable (if set and valid)
#   2. $SCRIPT_DIR/sdk (in-tree build via build-sdk-bindings.sh)
#   3. /opt/termin (system-wide install via install-to-opt.sh)
_sdk_valid() { [[ -d "$1/lib/python/termin" ]]; }

if [[ -n "$TERMIN_SDK" ]]; then
    if ! _sdk_valid "$TERMIN_SDK"; then
        echo "ERROR: TERMIN_SDK=$TERMIN_SDK is set but does not contain lib/python/termin" >&2
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
# Main termin is installed BEFORE subpackages so that its uninstall step
# does not remove __init__.py files that subpackages later provide.
PACKAGES=(
    termin-build-tools
    termin-nanobind-sdk
    termin-app
    termin-base
    termin-mesh
    termin-graphics
    termin-modules
    termin-inspect
    termin-scene
    termin-input
    termin-collision
    termin-render
    termin-display
    termin-lighting
    termin-entity
    termin-navmesh
    termin-physics
    termin-engine
    termin-skeleton
    termin-animation
    termin-components/termin-components-render
    termin-components/termin-components-mesh
    termin-components/termin-components-kinematic
    termin-gui
    termin-nodegraph
    tcplot
)

# When --force is set, nuke each package's build cache and egg-info so
# setuptools re-runs the CMake copy step from $TERMIN_SDK instead of
# reusing a cached wheel. This is the only reliable way to recover from
# an ABI-breaking SDK change — compute_local_version() fails when pip
# has already cached a wheel under the matching +sdkNNN suffix.
if [[ $FORCE -eq 1 ]]; then
    echo "--force: clearing per-package build caches before install"
    for pkg in "${PACKAGES[@]}"; do
        rm -rf "$SCRIPT_DIR/$pkg/build" "$SCRIPT_DIR/$pkg"/*.egg-info 2>/dev/null || true
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
    PIP_ARGS=(--no-build-isolation --no-deps --upgrade --target "$TARGET_DIR" "${FORCE_FLAGS[@]}")
    for pkg in "${PACKAGES[@]}"; do
        PIP_ARGS+=("$SCRIPT_DIR/$pkg")
    done
    echo ""
    echo "========================================"
    echo "  Installing ${#PACKAGES[@]} packages into $TARGET_DIR"
    echo "========================================"
    echo ""
    pip install "${PIP_ARGS[@]}"
else
    # Host-env mode: sequential installs so errors are attributed to a
    # specific package and intermediate state is inspectable.
    for pkg in "${PACKAGES[@]}"; do
        if [[ "$pkg" == "termin-app" && $EDITABLE -eq 1 ]]; then
            echo ""
            echo "========================================"
            echo "  Installing $pkg (editable)"
            echo "========================================"
            echo ""
            pip install --no-build-isolation "${FORCE_FLAGS[@]}" -e "$SCRIPT_DIR/$pkg"
        else
            echo ""
            echo "========================================"
            echo "  Installing $pkg"
            echo "========================================"
            echo ""
            pip install --no-build-isolation "${FORCE_FLAGS[@]}" "$SCRIPT_DIR/$pkg"
        fi
    done
fi

echo ""
echo "========================================"
echo "  All pip packages installed!"
echo "========================================"
