#!/bin/bash
# Install termin Python packages into the current pip environment.
# Each package builds from source via CMake and bundles its own libraries.
#
# Usage:
#   ./install-pip-packages.sh              # Install all packages
#   ./install-pip-packages.sh --editable   # Install termin in editable mode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EDITABLE=0

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
