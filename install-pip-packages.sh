#!/bin/bash
# Install termin Python packages into the current pip environment.
#
# Pip packages are THIN: they ship only nanobind binding .so files plus
# Python wrappers. The shared C++ libraries live in $TERMIN_SDK (default:
# ./sdk). build-sdk-cpp.sh + build-sdk-bindings.sh must be run first to
# produce the SDK.
#
# Usage:
#   ./install-pip-packages.sh              # Install all packages
#   ./install-pip-packages.sh --editable   # Install termin in editable mode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EDITABLE=0

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

for arg in "$@"; do
    case "$arg" in
        --editable|-e) EDITABLE=1 ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --editable, -e  Install termin in editable mode"
            echo "  --help, -h      Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

install_pkg() {
    local pkg="$1"
    echo ""
    echo "========================================"
    echo "  Installing $pkg"
    echo "========================================"
    echo ""
    pip install --no-build-isolation "$SCRIPT_DIR/$pkg"
}

# Build tools (needed by all C++ packages)
install_pkg "termin-build-tools"

# Nanobind shared runtime (needed by all packages with Python bindings)
install_pkg "termin-nanobind-sdk"

# C++ packages with native bindings (order matters — dependencies first)
for pkg in termin-base termin-mesh termin-graphics termin-modules; do
    install_pkg "$pkg"
done

# Subpackages of termin namespace — all ship only nanobind bindings (.so)
# plus Python wrappers; shared C++ libraries live in the termin SDK.
#
# Order must respect build-time and import-time dependencies:
#   inspect → scene → input → collision → render → display → lighting
#     → entity → navmesh → physics → engine → skeleton → animation
#     → components-render → components-mesh → components-kinematic
#
# Note: several "components-*" C++ targets install into the same Python
# namespace as their parent subproject (e.g. termin.colliders owns both
# _colliders_native and _components_collision_native). Those are merged
# into the parent pip package rather than shipped separately to avoid
# filesystem overlap at install time.
for pkg in \
        termin-inspect termin-scene termin-input termin-collision \
        termin-render termin-display termin-lighting \
        termin-entity termin-navmesh termin-physics termin-engine \
        termin-skeleton termin-animation \
        termin-components/termin-components-render \
        termin-components/termin-components-mesh \
        termin-components/termin-components-kinematic; do
    install_pkg "$pkg"
done

# Pure Python packages
for pkg in termin-gui termin-nodegraph; do
    install_pkg "$pkg"
done

# Main termin package
echo ""
echo "========================================"
echo "  Installing termin"
echo "========================================"
echo ""
if [[ $EDITABLE -eq 1 ]]; then
    pip install --no-build-isolation -e "$SCRIPT_DIR/termin"
else
    pip install --no-build-isolation "$SCRIPT_DIR/termin"
fi

echo ""
echo "========================================"
echo "  All pip packages installed!"
echo "========================================"
