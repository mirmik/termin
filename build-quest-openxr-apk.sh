#!/bin/bash
# Build the experimental Quest/OpenXR APK entry point.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$SCRIPT_DIR/termin-openxr/platform"
ANDROID_GRADLE_BUILD_ROOT="$SCRIPT_DIR/build/android-gradle-openxr"

ANDROID_ABI_VALUE="${ANDROID_ABI:-arm64-v8a}"
ANDROID_PLATFORM_VALUE="${ANDROID_PLATFORM:-android-26}"
ANDROID_SDK_ROOT_VALUE="${TERMIN_ANDROID_SDK_ROOT:-$SCRIPT_DIR/sdk/android}"
ANDROID_NDK_VERSION_VALUE="${TERMIN_ANDROID_NDK_VERSION:-27.2.12479018}"
GRADLE_BIN_VALUE="${GRADLE_BIN:-gradle}"
GRADLE_TASK="assembleDebug"
INSTALL_APK=0
LAUNCH_OPENXR=0
ADB_BIN_VALUE="${ADB:-adb}"

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
        --adb)
            ADB_BIN_VALUE="$2"
            shift
            ;;
        --adb=*)
            ADB_BIN_VALUE="${1#--adb=}"
            ;;
        --install)
            INSTALL_APK=1
            ;;
        --launch)
            INSTALL_APK=1
            LAUNCH_OPENXR=1
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --abi ABI             Android ABI (default: arm64-v8a)"
            echo "  --platform API        Android platform (default: android-26)"
            echo "  --sdk-root DIR        Termin Android SDK root (default: ./sdk/android)"
            echo "  --ndk-version VER     Android NDK version for Gradle (default: 27.2.12479018)"
            echo "  --gradle PATH         Gradle executable (default: \$GRADLE_BIN or gradle)"
            echo "  --adb PATH            adb executable (default: \$ADB or adb)"
            echo "  --install             Install the APK with adb after build"
            echo "  --launch              Install and launch TerminOpenXRActivity"
            echo "  --help, -h            Show this help"
            echo ""
            echo "This script intentionally does not call or modify ./build-android-apk.sh."
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
    shift
done

if ! command -v "$GRADLE_BIN_VALUE" >/dev/null 2>&1; then
    echo "ERROR: Gradle executable not found: $GRADLE_BIN_VALUE" >&2
    echo "  Install Gradle 8.x or pass --gradle /path/to/gradle." >&2
    exit 1
fi

GRADLE_VERSION="$("$GRADLE_BIN_VALUE" --version | sed -n 's/^Gradle //p' | head -n 1)"
GRADLE_MAJOR="${GRADLE_VERSION%%.*}"
if [[ -z "$GRADLE_MAJOR" || "$GRADLE_MAJOR" -lt 8 ]]; then
    echo "ERROR: Gradle 8.x is required, found: ${GRADLE_VERSION:-unknown}." >&2
    echo "  Pass --gradle /path/to/gradle-8.x/bin/gradle or set GRADLE_BIN." >&2
    exit 1
fi

if [[ "$INSTALL_APK" -eq 1 ]] && ! command -v "$ADB_BIN_VALUE" >/dev/null 2>&1; then
    echo "ERROR: adb executable not found: $ADB_BIN_VALUE" >&2
    echo "  Pass --adb /path/to/adb or set ADB." >&2
    exit 1
fi

export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$SCRIPT_DIR/build/gradle-home}"
GRADLE_PROJECT_CACHE_DIR="$ANDROID_GRADLE_BUILD_ROOT/project-cache"
APK_PATH="$ANDROID_GRADLE_BUILD_ROOT/app/outputs/apk/debug/app-debug.apk"

echo ""
echo "========================================"
echo "  Building Termin Quest/OpenXR smoke APK"
echo "========================================"
echo ""
echo "Gradle:          $GRADLE_BIN_VALUE ($GRADLE_VERSION)"
echo "Gradle home:     $GRADLE_USER_HOME"
echo "Project cache:   $GRADLE_PROJECT_CACHE_DIR"
echo "Project:         $PLATFORM_DIR"
echo "Task:            $GRADLE_TASK"
echo "Termin SDK root: $ANDROID_SDK_ROOT_VALUE"
echo "ABI:             $ANDROID_ABI_VALUE"
echo "Platform:        $ANDROID_PLATFORM_VALUE"
echo "NDK version:     $ANDROID_NDK_VERSION_VALUE"
echo ""

cd "$PLATFORM_DIR"
"$GRADLE_BIN_VALUE" --no-daemon "$GRADLE_TASK" \
    --project-cache-dir "$GRADLE_PROJECT_CACHE_DIR" \
    -PterminAndroidSdkRoot="$ANDROID_SDK_ROOT_VALUE" \
    -PterminAndroidAbi="$ANDROID_ABI_VALUE" \
    -PterminAndroidPlatform="$ANDROID_PLATFORM_VALUE" \
    -PterminAndroidNdkVersion="$ANDROID_NDK_VERSION_VALUE"

rm -rf "$PLATFORM_DIR/.gradle" "$PLATFORM_DIR/app/.cxx" "$PLATFORM_DIR/app/build"

echo ""
echo "APK: $APK_PATH"
echo "OpenXR Activity: org.termin.openxr/.TerminOpenXRActivity"

if [[ "$INSTALL_APK" -eq 1 ]]; then
    "$ADB_BIN_VALUE" install -r "$APK_PATH"
fi

if [[ "$LAUNCH_OPENXR" -eq 1 ]]; then
    "$ADB_BIN_VALUE" shell am start -n org.termin.openxr/.TerminOpenXRActivity
fi
