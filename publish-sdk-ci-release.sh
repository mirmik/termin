#!/bin/bash
# Publish the local Termin SDK as the mutable CI SDK release.
#
# This script intentionally runs outside GitHub Actions. It packages the local
# SDK layout and updates the sdk-latest-ci pre-release in the termin repository.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SDK_PREFIX="${SDK_PREFIX:-$SCRIPT_DIR/sdk}"
RELEASE_TAG="${RELEASE_TAG:-sdk-latest-ci}"
REPO="${REPO:-mirmik/termin}"
ASSET_BASENAME="${ASSET_BASENAME:-termin-sdk-linux-x86_64-py310}"
BUILD_WHEELS=0
PUBLISH_DIR=""
TRIGGER_DIFFUSION_EDITOR=0
DIFFUSION_EDITOR_REPO="${DIFFUSION_EDITOR_REPO:-mirmik/diffusion-editor}"

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --sdk DIR           SDK directory to publish (default: ./sdk)
  --repo OWNER/REPO   GitHub repository (default: mirmik/termin)
  --tag TAG           Release tag (default: sdk-latest-ci)
  --build-wheels      Run ./build-sdk-wheels.sh --force before packaging
  --publish-dir DIR   Directory for temporary archive output (default: mktemp)
  --trigger-diffusion-editor
                      Trigger diffusion-editor CI after publishing
  --help, -h          Show this help

Environment:
  SDK_PREFIX          SDK directory alternative to --sdk
  REPO                GitHub repository alternative to --repo
  RELEASE_TAG         Release tag alternative to --tag
  DIFFUSION_EDITOR_REPO
                      Downstream repository to trigger
  GH_TOKEN            Optional token for gh; otherwise gh's login is used
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sdk)
            SDK_PREFIX="$2"
            shift 2
            ;;
        --sdk=*)
            SDK_PREFIX="${1#--sdk=}"
            shift
            ;;
        --repo)
            REPO="$2"
            shift 2
            ;;
        --repo=*)
            REPO="${1#--repo=}"
            shift
            ;;
        --tag)
            RELEASE_TAG="$2"
            shift 2
            ;;
        --tag=*)
            RELEASE_TAG="${1#--tag=}"
            shift
            ;;
        --build-wheels)
            BUILD_WHEELS=1
            shift
            ;;
        --publish-dir)
            PUBLISH_DIR="$2"
            shift 2
            ;;
        --publish-dir=*)
            PUBLISH_DIR="${1#--publish-dir=}"
            shift
            ;;
        --trigger-diffusion-editor)
            TRIGGER_DIFFUSION_EDITOR=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: gh CLI is required. Install it and run 'gh auth login' first." >&2
    exit 1
fi
if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required." >&2
    exit 1
fi
if ! command -v sha256sum >/dev/null 2>&1; then
    echo "ERROR: sha256sum is required." >&2
    exit 1
fi

if ! tar --help 2>/dev/null | grep -q -- '--zstd'; then
    echo "ERROR: tar with --zstd support is required." >&2
    exit 1
fi

SDK_PREFIX="$(cd "$SDK_PREFIX" 2>/dev/null && pwd || true)"
if [[ -z "$SDK_PREFIX" || ! -d "$SDK_PREFIX" ]]; then
    echo "ERROR: SDK directory not found. Build Termin SDK first or pass --sdk DIR." >&2
    exit 1
fi

if [[ $BUILD_WHEELS -eq 1 ]]; then
    echo "Building SDK wheelhouse from local SDK..."
    TERMIN_SDK="$SDK_PREFIX" "$SCRIPT_DIR/build-sdk-wheels.sh" --force
fi

if [[ ! -d "$SDK_PREFIX/lib" ]]; then
    echo "ERROR: SDK is missing lib/: $SDK_PREFIX" >&2
    exit 1
fi
if [[ ! -d "$SDK_PREFIX/wheels" ]]; then
    echo "ERROR: SDK is missing wheels/: $SDK_PREFIX" >&2
    echo "Run '$0 --build-wheels' or './build-sdk-wheels.sh --force' first." >&2
    exit 1
fi
if ! find "$SDK_PREFIX/wheels" -maxdepth 1 -type f -name '*.whl' | grep -q .; then
    echo "ERROR: SDK wheelhouse is empty: $SDK_PREFIX/wheels" >&2
    exit 1
fi

sha="$(git -C "$SCRIPT_DIR" rev-parse HEAD)"
branch="$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD)"
dirty=0
if ! git -C "$SCRIPT_DIR" diff --quiet || ! git -C "$SCRIPT_DIR" diff --cached --quiet; then
    dirty=1
fi

python_version="$(
    python3 - <<'PY' 2>/dev/null || true
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
if [[ -z "$python_version" ]]; then
    python_version="unknown"
fi

if [[ -z "$PUBLISH_DIR" ]]; then
    PUBLISH_DIR="$(mktemp -d)"
else
    mkdir -p "$PUBLISH_DIR"
    PUBLISH_DIR="$(cd "$PUBLISH_DIR" && pwd)"
fi

sdk_asset="${ASSET_BASENAME}-latest-ci.tar.zst"
checksum_asset="${ASSET_BASENAME}-latest-ci.sha256"
manifest="$SDK_PREFIX/manifest.json"

cat > "$manifest" <<EOF
{
  "name": "termin-sdk",
  "channel": "latest-ci",
  "repository": "$REPO",
  "sha": "$sha",
  "ref": "$branch",
  "dirty": $dirty,
  "platform": "linux-x86_64",
  "python": "$python_version",
  "published_by": "publish-sdk-ci-release.sh"
}
EOF

echo "Packing SDK: $SDK_PREFIX"
tar --zstd -cf "$PUBLISH_DIR/$sdk_asset" -C "$SDK_PREFIX" .
(
    cd "$PUBLISH_DIR"
    sha256sum "$sdk_asset" > "$checksum_asset"
)

echo "Publishing release $RELEASE_TAG in $REPO"
git -C "$SCRIPT_DIR" tag -f "$RELEASE_TAG" "$sha"
git -C "$SCRIPT_DIR" push origin "refs/tags/$RELEASE_TAG" --force

if gh release view "$RELEASE_TAG" --repo "$REPO" >/dev/null 2>&1; then
    gh release edit "$RELEASE_TAG" \
        --repo "$REPO" \
        --title "Termin SDK latest CI" \
        --notes "Mutable manually-published CI SDK built from $sha." \
        --prerelease
else
    gh release create "$RELEASE_TAG" \
        --repo "$REPO" \
        --title "Termin SDK latest CI" \
        --notes "Mutable manually-published CI SDK built from $sha." \
        --prerelease
fi

for asset in "$sdk_asset" "$checksum_asset"; do
    gh release delete-asset "$RELEASE_TAG" "$asset" --repo "$REPO" -y >/dev/null 2>&1 || true
done

gh release upload "$RELEASE_TAG" \
    "$PUBLISH_DIR/$sdk_asset" \
    "$PUBLISH_DIR/$checksum_asset" \
    --repo "$REPO" \
    --clobber

if [[ $TRIGGER_DIFFUSION_EDITOR -eq 1 ]]; then
    echo "Triggering diffusion-editor CI in $DIFFUSION_EDITOR_REPO"
    gh api "repos/${DIFFUSION_EDITOR_REPO}/dispatches" \
        --method POST \
        --field event_type=termin-sdk-published \
        --field "client_payload[termin_sha]=$sha" \
        --field "client_payload[release_tag]=$RELEASE_TAG" \
        --field "client_payload[asset]=$sdk_asset"
fi

cat <<EOF
Published:
  release: https://github.com/$REPO/releases/tag/$RELEASE_TAG
  asset:   $sdk_asset
  sha256:  $checksum_asset
EOF
