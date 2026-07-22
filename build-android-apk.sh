#!/bin/bash
# Build a Termin Android APK.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$SCRIPT_DIR/termin-android/platform"
ANDROID_GRADLE_BUILD_ROOT="$SCRIPT_DIR/build/android-gradle"

ANDROID_ABI_VALUE="${ANDROID_ABI:-arm64-v8a}"
ANDROID_PLATFORM_VALUE="${ANDROID_PLATFORM:-android-26}"
ANDROID_SDK_ROOT_VALUE="${TERMIN_ANDROID_SDK_ROOT:-$SCRIPT_DIR/sdk/android}"
ANDROID_NDK_VERSION_VALUE="${TERMIN_ANDROID_NDK_VERSION:-27.2.12479018}"
ANDROID_ASSETS_DIR_VALUE="${TERMIN_ANDROID_ASSETS_DIR:-$SCRIPT_DIR/termin-android/assets}"
ANDROID_APPLICATION_ID_VALUE="${TERMIN_ANDROID_APPLICATION_ID:-org.termin.android}"
ANDROID_APP_LABEL_VALUE="${TERMIN_ANDROID_APP_LABEL:-Termin Android}"
ANDROID_VERSION_CODE_VALUE="${TERMIN_ANDROID_VERSION_CODE:-1}"
ANDROID_VERSION_NAME_VALUE="${TERMIN_ANDROID_VERSION_NAME:-0.1.0}"
GRADLE_BIN_VALUE="${GRADLE_BIN:-gradle}"
ANDROID_VARIANT="debug"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --abi)
            ANDROID_ABI_VALUE="$2"
            shift
            ;;
        --abi=*)
            ANDROID_ABI_VALUE="${1#--abi=}"
            ;;
        --platform)
            ANDROID_PLATFORM_VALUE="$2"
            shift
            ;;
        --platform=*)
            ANDROID_PLATFORM_VALUE="${1#--platform=}"
            ;;
        --sdk-root)
            ANDROID_SDK_ROOT_VALUE="$2"
            shift
            ;;
        --sdk-root=*)
            ANDROID_SDK_ROOT_VALUE="${1#--sdk-root=}"
            ;;
        --ndk-version)
            ANDROID_NDK_VERSION_VALUE="$2"
            shift
            ;;
        --ndk-version=*)
            ANDROID_NDK_VERSION_VALUE="${1#--ndk-version=}"
            ;;
        --gradle)
            GRADLE_BIN_VALUE="$2"
            shift
            ;;
        --gradle=*)
            GRADLE_BIN_VALUE="${1#--gradle=}"
            ;;
        --assets-dir)
            ANDROID_ASSETS_DIR_VALUE="$2"
            shift
            ;;
        --assets-dir=*)
            ANDROID_ASSETS_DIR_VALUE="${1#--assets-dir=}"
            ;;
        --application-id)
            ANDROID_APPLICATION_ID_VALUE="$2"
            shift
            ;;
        --application-id=*)
            ANDROID_APPLICATION_ID_VALUE="${1#--application-id=}"
            ;;
        --app-label)
            ANDROID_APP_LABEL_VALUE="$2"
            shift
            ;;
        --app-label=*)
            ANDROID_APP_LABEL_VALUE="${1#--app-label=}"
            ;;
        --version-code)
            ANDROID_VERSION_CODE_VALUE="$2"
            shift
            ;;
        --version-code=*)
            ANDROID_VERSION_CODE_VALUE="${1#--version-code=}"
            ;;
        --version-name)
            ANDROID_VERSION_NAME_VALUE="$2"
            shift
            ;;
        --version-name=*)
            ANDROID_VERSION_NAME_VALUE="${1#--version-name=}"
            ;;
        --variant)
            ANDROID_VARIANT="$2"
            shift
            ;;
        --variant=*)
            ANDROID_VARIANT="${1#--variant=}"
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --abi ABI             Android ABI (default: arm64-v8a)"
            echo "  --platform API        Android platform (default: android-26)"
            echo "  --sdk-root DIR        Termin Android SDK root (default: ./sdk/android)"
            echo "  --ndk-version VER     Android NDK version for Gradle (default: 27.2.12479018)"
            echo "  --assets-dir DIR      APK assets directory (default: ./termin-android/assets)"
            echo "  --application-id ID   Android applicationId (default: org.termin.android)"
            echo "  --app-label LABEL     Android launcher label (default: Termin Android)"
            echo "  --version-code CODE   Positive Android version code (default: 1)"
            echo "  --version-name NAME   User-visible version name (default: 0.1.0)"
            echo "  --gradle PATH         Gradle executable (default: \$GRADLE_BIN or gradle)"
            echo "  --variant VARIANT     Gradle variant: debug or release (default: debug)"
            echo "  --help, -h            Show this help"
            echo ""
            echo "Environment:"
            echo "  GRADLE_BIN            Gradle executable. Gradle 8.x is required."
            echo "  GRADLE_USER_HOME      Gradle cache dir (default: ./build/gradle-home)"
            echo "  TERMIN_ANDROID_SDK_ROOT"
            echo "                        Termin Android SDK root if --sdk-root is omitted"
            echo "  TERMIN_ANDROID_NDK_VERSION"
            echo "                        NDK version if --ndk-version is omitted"
            echo "  TERMIN_ANDROID_ASSETS_DIR"
            echo "                        APK assets directory if --assets-dir is omitted"
            echo "  TERMIN_ANDROID_APPLICATION_ID"
            echo "                        Android applicationId if --application-id is omitted"
            echo "  TERMIN_ANDROID_APP_LABEL"
            echo "                        Android launcher label if --app-label is omitted"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
    shift
done

case "$ANDROID_VARIANT" in
    debug)
        GRADLE_TASK="assembleDebug"
        ;;
    release)
        GRADLE_TASK="assembleRelease"
        ;;
    *)
        echo "ERROR: Unsupported Android variant: $ANDROID_VARIANT (expected debug or release)." >&2
        exit 1
        ;;
esac

if ! command -v "$GRADLE_BIN_VALUE" >/dev/null 2>&1; then
    echo "ERROR: Gradle executable not found: $GRADLE_BIN_VALUE" >&2
    echo "  Install Gradle 8.x or pass --gradle /path/to/gradle." >&2
    exit 1
fi

GRADLE_VERSION="$("$GRADLE_BIN_VALUE" --version | sed -n 's/^Gradle //p' | head -n 1)"
GRADLE_MAJOR="${GRADLE_VERSION%%.*}"
if [[ -z "$GRADLE_MAJOR" || "$GRADLE_MAJOR" -lt 8 ]]; then
    echo "ERROR: Gradle 8.x is required, found: ${GRADLE_VERSION:-unknown}." >&2
    echo "  The apt package may install Gradle 4.x, which is too old for Android Gradle Plugin 8.x." >&2
    echo "  Pass --gradle /path/to/gradle-8.x/bin/gradle or set GRADLE_BIN." >&2
    exit 1
fi

export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$SCRIPT_DIR/build/gradle-home}"
GRADLE_PROJECT_CACHE_DIR="$ANDROID_GRADLE_BUILD_ROOT/project-cache"

echo ""
echo "========================================"
echo "  Building Termin Android APK"
echo "========================================"
echo ""
echo "Gradle:          $GRADLE_BIN_VALUE ($GRADLE_VERSION)"
echo "Gradle home:     $GRADLE_USER_HOME"
echo "Project cache:   $GRADLE_PROJECT_CACHE_DIR"
echo "Project:         $PLATFORM_DIR"
echo "Task:            $GRADLE_TASK"
echo "Variant:         $ANDROID_VARIANT"
echo "Termin SDK root: $ANDROID_SDK_ROOT_VALUE"
echo "ABI:             $ANDROID_ABI_VALUE"
echo "Platform:        $ANDROID_PLATFORM_VALUE"
echo "NDK version:     $ANDROID_NDK_VERSION_VALUE"
echo "Assets dir:      $ANDROID_ASSETS_DIR_VALUE"
echo "Application ID:  $ANDROID_APPLICATION_ID_VALUE"
echo "App label:       $ANDROID_APP_LABEL_VALUE"
echo "Version:         $ANDROID_VERSION_NAME_VALUE ($ANDROID_VERSION_CODE_VALUE)"
echo ""

cd "$PLATFORM_DIR"
"$GRADLE_BIN_VALUE" --no-daemon "$GRADLE_TASK" \
    --project-cache-dir "$GRADLE_PROJECT_CACHE_DIR" \
    -PterminAndroidSdkRoot="$ANDROID_SDK_ROOT_VALUE" \
    -PterminAndroidAbi="$ANDROID_ABI_VALUE" \
    -PterminAndroidPlatform="$ANDROID_PLATFORM_VALUE" \
    -PterminAndroidNdkVersion="$ANDROID_NDK_VERSION_VALUE" \
    -PterminAndroidAssetsDir="$ANDROID_ASSETS_DIR_VALUE" \
    -PterminAndroidApplicationId="$ANDROID_APPLICATION_ID_VALUE" \
    -PterminAndroidAppLabel="$ANDROID_APP_LABEL_VALUE" \
    -PterminAndroidVersionCode="$ANDROID_VERSION_CODE_VALUE" \
    -PterminAndroidVersionName="$ANDROID_VERSION_NAME_VALUE"

rm -rf "$PLATFORM_DIR/.gradle" "$PLATFORM_DIR/app/.cxx" "$PLATFORM_DIR/app/build"

echo ""
echo "Gradle APK metadata: $ANDROID_GRADLE_BUILD_ROOT/app/outputs/apk/$ANDROID_VARIANT/output-metadata.json"
