#!/bin/bash
# Install termin-base, termin-graphics, and termin-gui into the local venv.
# Run from the diffusion-editor directory.
set -e

cd "$(dirname "$0")"

VENV="./venv"
if [ ! -d "$VENV" ]; then
    echo "Creating venv..."
    python3 -m venv "$VENV"
fi

PIP="$VENV/bin/pip"

TERMIN_ENV="$(cd .. && pwd)"
LOCAL_TERMIN_SDK="$TERMIN_ENV/sdk"
if [ -z "${TERMIN_SDK:-}" ]; then
    if [ -d "$LOCAL_TERMIN_SDK/lib" ]; then
        export TERMIN_SDK="$LOCAL_TERMIN_SDK"
    else
        echo "ERROR: termin SDK not found."
        echo "Build it first with: cd \"$TERMIN_ENV\" && ./build-sdk.sh"
        echo "Or set TERMIN_SDK explicitly before running this script."
        exit 1
    fi
fi

echo "Using TERMIN_SDK=$TERMIN_SDK"

echo "=== Installing termin-build-tools ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-build-tools"

echo ""
echo "=== Installing nanobind + termin-nanobind ==="
$PIP install --no-cache-dir nanobind
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-nanobind-sdk"

echo ""
echo "=== Installing termin-base (tcbase) ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-base"

echo ""
echo ""
echo "=== Installing termin-mesh (tmesh) ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-mesh"

echo ""
echo "=== Installing termin-graphics (tgfx) ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-graphics"

echo ""
echo "=== Installing termin-gui (tcgui) ==="
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-gui"

echo ""
echo "=== Installing termin-inspect (transitive via termin-scene) ==="
# termin.scene.__init__ pulls in termin.scene.python_component which
# in turn needs termin.inspect.InspectField. The chain is forced by
# the nanobind cross-module registration below.
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-inspect"

echo ""
echo "=== Installing termin-scene (tc_scene_handle types) ==="
# `termin.display._display_native` hard-imports `termin.scene._scene_native`
# at nanobind init to resolve cross-module type references (tc_scene_handle
# in viewport bindings). Without it `termin.display.__init__` fails
# before `_platform_native` is reachable — we need termin-scene even
# though diffusion-editor only uses SDLBackendWindow.
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-scene"

echo ""
echo "=== Installing termin-display (SDLBackendWindow) ==="
# SDLBackendWindow replaces the old SDL+GL bootstrap in main.py; under
# TERMIN_BACKEND=vulkan it acquires a VkSurfaceKHR and drives the
# swapchain. Must be installed alongside tgfx so the process shares
# a single IRenderDevice.
$PIP install --no-cache-dir --no-build-isolation "$TERMIN_ENV/termin-display"

echo ""
echo "=== Installing diffusion-editor requirements ==="
$PIP install --no-cache-dir --no-build-isolation -r requirements.txt

echo ""
echo "Done. All dependencies installed into $VENV"
