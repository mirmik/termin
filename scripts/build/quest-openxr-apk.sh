#!/bin/bash
# Build the experimental Quest/OpenXR APK entry point.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLATFORM_DIR="$SCRIPT_DIR/platform/termin-openxr/platform"
ANDROID_GRADLE_BUILD_ROOT="$SCRIPT_DIR/build/android-gradle-openxr"

ANDROID_ABI_VALUE="${ANDROID_ABI:-arm64-v8a}"
ANDROID_PLATFORM_VALUE="${ANDROID_PLATFORM:-android-26}"
ANDROID_SDK_ROOT_VALUE="${TERMIN_ANDROID_SDK_ROOT:-}"
SYSTEM_ANDROID_SDK_ROOT_VALUE="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
ANDROID_NDK_ROOT_VALUE="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
JAVA_HOME_VALUE="${JAVA_HOME:-}"
ANDROID_NDK_VERSION_VALUE="${TERMIN_ANDROID_NDK_VERSION:-27.2.12479018}"
OPENXR_ASSETS_DIR_VALUE="${TERMIN_OPENXR_ASSETS_DIR:-$SCRIPT_DIR/platform/termin-android/assets}"
ANDROID_APPLICATION_ID_VALUE="${TERMIN_ANDROID_APPLICATION_ID:-}"
ANDROID_APP_LABEL_VALUE="${TERMIN_ANDROID_APP_LABEL:-Termin OpenXR}"
ANDROID_VERSION_CODE_VALUE="${TERMIN_ANDROID_VERSION_CODE:-1}"
ANDROID_VERSION_NAME_VALUE="${TERMIN_ANDROID_VERSION_NAME:-0.1.0}"
GRADLE_BIN_VALUE="${GRADLE_BIN:-}"
ANDROID_VARIANT="debug"
INSTALL_APK=0
LAUNCH_OPENXR=0
ADB_BIN_VALUE="${ADB:-}"

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
        --ndk-root)
            ANDROID_NDK_ROOT_VALUE="$2"
            shift
            ;;
        --ndk-root=*)
            ANDROID_NDK_ROOT_VALUE="${1#--ndk-root=}"
            ;;
        --android-home)
            SYSTEM_ANDROID_SDK_ROOT_VALUE="$2"
            shift
            ;;
        --android-home=*)
            SYSTEM_ANDROID_SDK_ROOT_VALUE="${1#--android-home=}"
            ;;
        --java-home)
            JAVA_HOME_VALUE="$2"
            shift
            ;;
        --java-home=*)
            JAVA_HOME_VALUE="${1#--java-home=}"
            ;;
        --assets-dir)
            OPENXR_ASSETS_DIR_VALUE="$2"
            shift
            ;;
        --assets-dir=*)
            OPENXR_ASSETS_DIR_VALUE="${1#--assets-dir=}"
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
        --gradle)
            GRADLE_BIN_VALUE="$2"
            shift
            ;;
        --gradle=*)
            GRADLE_BIN_VALUE="${1#--gradle=}"
            ;;
        --variant)
            ANDROID_VARIANT="$2"
            shift
            ;;
        --variant=*)
            ANDROID_VARIANT="${1#--variant=}"
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
            echo "  --ndk-root DIR        Explicit Android NDK root"
            echo "  --android-home DIR    Google Android SDK root"
            echo "  --java-home DIR       Java/JDK root used by Gradle"
            echo "  --assets-dir DIR      Runtime package assets dir (default: termin-android/assets)"
            echo "  --application-id ID   Android applicationId (required)"
            echo "  --app-label LABEL     Android launcher label (default: Termin OpenXR)"
            echo "  --version-code CODE   Positive Android version code (default: 1)"
            echo "  --version-name NAME   User-visible version name (default: 0.1.0)"
            echo "  --gradle PATH         Gradle executable (default: \$GRADLE_BIN, Build/gradle, or gradle)"
            echo "  --variant VARIANT     Gradle variant: debug or release (default: debug)"
            echo "  --adb PATH            adb executable (default: \$ADB or adb)"
            echo "  --install             Install the APK with adb after build"
            echo "  --launch              Install and launch the OpenXR NativeActivity"
            echo "  --help, -h            Show this help"
            echo ""
            echo "This script intentionally does not call or modify ./scripts/build/android-apk.sh."
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
    shift
done

SETTINGS_PYTHON="${TERMIN_HOST_PYTHON:-$SCRIPT_DIR/sdk/bin/termin_python}"
if [[ ! -x "$SETTINGS_PYTHON" ]]; then
    SETTINGS_PYTHON="$(command -v python3 || command -v python || true)"
fi

read_termin_setting() {
    local key="$1"
    [[ -n "$SETTINGS_PYTHON" ]] || return 0
    "$SETTINGS_PYTHON" "$SCRIPT_DIR/build-system/read-termin-user-setting.py" "$key"
}

if [[ -z "$ANDROID_SDK_ROOT_VALUE" ]] && ! ANDROID_SDK_ROOT_VALUE="$(read_termin_setting "Build/androidSdkRoot")"; then
    echo "WARNING: Failed to read Build/androidSdkRoot from Termin user settings." >&2
    ANDROID_SDK_ROOT_VALUE=""
fi
if [[ -z "$SYSTEM_ANDROID_SDK_ROOT_VALUE" ]] && ! SYSTEM_ANDROID_SDK_ROOT_VALUE="$(read_termin_setting "Build/androidHome")"; then
    echo "WARNING: Failed to read Build/androidHome from Termin user settings." >&2
    SYSTEM_ANDROID_SDK_ROOT_VALUE=""
fi
if [[ -z "$ANDROID_NDK_ROOT_VALUE" ]] && ! ANDROID_NDK_ROOT_VALUE="$(read_termin_setting "Build/androidNdkRoot")"; then
    echo "WARNING: Failed to read Build/androidNdkRoot from Termin user settings." >&2
    ANDROID_NDK_ROOT_VALUE=""
fi
if [[ -z "$JAVA_HOME_VALUE" ]] && ! JAVA_HOME_VALUE="$(read_termin_setting "Build/javaHome")"; then
    echo "WARNING: Failed to read Build/javaHome from Termin user settings." >&2
    JAVA_HOME_VALUE=""
fi
if [[ -z "$GRADLE_BIN_VALUE" ]] && ! GRADLE_BIN_VALUE="$(read_termin_setting "Build/gradle")"; then
    echo "WARNING: Failed to read Build/gradle from Termin user settings." >&2
    GRADLE_BIN_VALUE=""
fi
if [[ -z "$ADB_BIN_VALUE" ]] && ! ADB_BIN_VALUE="$(read_termin_setting "Build/adb")"; then
    echo "WARNING: Failed to read Build/adb from Termin user settings." >&2
    ADB_BIN_VALUE=""
fi
ANDROID_SDK_ROOT_VALUE="${ANDROID_SDK_ROOT_VALUE:-$SCRIPT_DIR/sdk/android}"
GRADLE_BIN_VALUE="${GRADLE_BIN_VALUE:-gradle}"
if [[ -z "$ADB_BIN_VALUE" && -n "$SYSTEM_ANDROID_SDK_ROOT_VALUE" && -x "$SYSTEM_ANDROID_SDK_ROOT_VALUE/platform-tools/adb" ]]; then
    ADB_BIN_VALUE="$SYSTEM_ANDROID_SDK_ROOT_VALUE/platform-tools/adb"
fi
ADB_BIN_VALUE="${ADB_BIN_VALUE:-adb}"

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

if [[ -z "$ANDROID_APPLICATION_ID_VALUE" ]]; then
    echo "ERROR: Quest/OpenXR application ID is required." >&2
    echo "  Pass --application-id ID or set TERMIN_ANDROID_APPLICATION_ID." >&2
    exit 1
fi

if ! command -v "$GRADLE_BIN_VALUE" >/dev/null 2>&1; then
    echo "ERROR: Gradle executable not found: $GRADLE_BIN_VALUE" >&2
    echo "  Install Gradle 8.x or pass --gradle /path/to/gradle." >&2
    exit 1
fi

if [[ -n "$SYSTEM_ANDROID_SDK_ROOT_VALUE" && ! -d "$SYSTEM_ANDROID_SDK_ROOT_VALUE/platforms" ]]; then
    echo "ERROR: Configured Android SDK has no platforms directory: $SYSTEM_ANDROID_SDK_ROOT_VALUE" >&2
    exit 1
fi
if [[ -z "$SYSTEM_ANDROID_SDK_ROOT_VALUE" ]]; then
    echo "ERROR: Android SDK location is not configured." >&2
    echo "  Set ANDROID_HOME/ANDROID_SDK_ROOT, pass --android-home, or configure Build/androidHome." >&2
    echo "  TERMIN_ANDROID_SDK_ROOT is the separate Termin cross-compiled SDK." >&2
    exit 1
fi
export ANDROID_HOME="$SYSTEM_ANDROID_SDK_ROOT_VALUE"
export ANDROID_SDK_ROOT="$SYSTEM_ANDROID_SDK_ROOT_VALUE"
if [[ -n "$JAVA_HOME_VALUE" ]]; then
    if [[ ! -x "$JAVA_HOME_VALUE/bin/java" ]]; then
        echo "ERROR: Java home has no executable bin/java: $JAVA_HOME_VALUE" >&2
        exit 1
    fi
    export JAVA_HOME="$JAVA_HOME_VALUE"
fi
if [[ -n "$ANDROID_NDK_ROOT_VALUE" && ! -f "$ANDROID_NDK_ROOT_VALUE/build/cmake/android.toolchain.cmake" ]]; then
    echo "ERROR: Android NDK has no CMake toolchain: $ANDROID_NDK_ROOT_VALUE" >&2
    exit 1
fi

# Keep every Gradle invocation, including version probing, inside the
# repository-owned cache. This also makes builds work in isolated agents where
# the user's global ~/.gradle is intentionally read-only.
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$SCRIPT_DIR/build/gradle-home}"

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

TERMIN_ANDROID_SDK_PREFIX="$ANDROID_SDK_ROOT_VALUE/$ANDROID_ABI_VALUE"
TERMIN_ANDROID_SDK_LIB_DIR="$TERMIN_ANDROID_SDK_PREFIX/lib"
TERMIN_OPENXR_CONFIG="$TERMIN_ANDROID_SDK_LIB_DIR/cmake/termin_openxr/termin_openxrConfig.cmake"

if [[ ! -d "$ANDROID_SDK_ROOT_VALUE" ]]; then
    echo "ERROR: Termin Android SDK is not installed." >&2
    echo "  Expected SDK root: $ANDROID_SDK_ROOT_VALUE" >&2
    echo "  Build and install it first:" >&2
    echo "    $SCRIPT_DIR/scripts/build/android.sh --abi $ANDROID_ABI_VALUE --platform $ANDROID_PLATFORM_VALUE" >&2
    echo "  Or pass --sdk-root /path/to/sdk/android." >&2
    exit 1
fi

if [[ ! -d "$TERMIN_ANDROID_SDK_PREFIX" ]]; then
    echo "ERROR: Termin Android SDK is missing the requested ABI." >&2
    echo "  Expected ABI prefix: $TERMIN_ANDROID_SDK_PREFIX" >&2
    echo "  Build and install it first:" >&2
    echo "    $SCRIPT_DIR/scripts/build/android.sh --abi $ANDROID_ABI_VALUE --platform $ANDROID_PLATFORM_VALUE" >&2
    echo "  Or choose an ABI that exists in the Termin Android SDK." >&2
    exit 1
fi

if [[ ! -d "$TERMIN_ANDROID_SDK_LIB_DIR" ]]; then
    echo "ERROR: Termin Android SDK ABI prefix is incomplete: lib directory is missing." >&2
    echo "  Expected lib directory: $TERMIN_ANDROID_SDK_LIB_DIR" >&2
    echo "  Rebuild and reinstall the Android SDK:" >&2
    echo "    $SCRIPT_DIR/scripts/build/android.sh --abi $ANDROID_ABI_VALUE --platform $ANDROID_PLATFORM_VALUE" >&2
    exit 1
fi

if [[ ! -f "$TERMIN_OPENXR_CONFIG" ]]; then
    echo "ERROR: Termin Android SDK is installed, but OpenXR support is missing." >&2
    echo "  Expected CMake package: $TERMIN_OPENXR_CONFIG" >&2
    echo "  Rebuild and reinstall the Android SDK with termin-openxr enabled:" >&2
    echo "    $SCRIPT_DIR/scripts/build/android.sh --abi $ANDROID_ABI_VALUE --platform $ANDROID_PLATFORM_VALUE" >&2
    exit 1
fi

GRADLE_PROJECT_CACHE_DIR="$ANDROID_GRADLE_BUILD_ROOT/project-cache"
APK_OUTPUT_DIR="$ANDROID_GRADLE_BUILD_ROOT/app/outputs/apk/$ANDROID_VARIANT"

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
echo "Variant:         $ANDROID_VARIANT"
echo "Termin SDK root: $ANDROID_SDK_ROOT_VALUE"
echo "Android SDK:      $SYSTEM_ANDROID_SDK_ROOT_VALUE"
echo "Android NDK:      ${ANDROID_NDK_ROOT_VALUE:-<SDK-managed version>}"
echo "Java home:        ${JAVA_HOME_VALUE:-<Gradle/default>}"
echo "OpenXR assets:   $OPENXR_ASSETS_DIR_VALUE"
echo "ABI:             $ANDROID_ABI_VALUE"
echo "Platform:        $ANDROID_PLATFORM_VALUE"
echo "NDK version:     $ANDROID_NDK_VERSION_VALUE"
echo "Application ID:  $ANDROID_APPLICATION_ID_VALUE"
echo "App label:       $ANDROID_APP_LABEL_VALUE"
echo "Version:         $ANDROID_VERSION_NAME_VALUE ($ANDROID_VERSION_CODE_VALUE)"
echo ""

GRADLE_TOOLCHAIN_ARGS=()
if [[ -n "$ANDROID_NDK_ROOT_VALUE" ]]; then
    GRADLE_TOOLCHAIN_ARGS+=("-PterminAndroidNdkRoot=$ANDROID_NDK_ROOT_VALUE")
fi

cd "$PLATFORM_DIR"
"$GRADLE_BIN_VALUE" --no-daemon "$GRADLE_TASK" \
    --project-cache-dir "$GRADLE_PROJECT_CACHE_DIR" \
    -PterminAndroidSdkRoot="$ANDROID_SDK_ROOT_VALUE" \
    -PterminAndroidAbi="$ANDROID_ABI_VALUE" \
    -PterminAndroidPlatform="$ANDROID_PLATFORM_VALUE" \
    -PterminAndroidNdkVersion="$ANDROID_NDK_VERSION_VALUE" \
    "${GRADLE_TOOLCHAIN_ARGS[@]}" \
    -PterminOpenXRAssetsDir="$OPENXR_ASSETS_DIR_VALUE" \
    -PterminAndroidApplicationId="$ANDROID_APPLICATION_ID_VALUE" \
    -PterminAndroidAppLabel="$ANDROID_APP_LABEL_VALUE" \
    -PterminAndroidVersionCode="$ANDROID_VERSION_CODE_VALUE" \
    -PterminAndroidVersionName="$ANDROID_VERSION_NAME_VALUE"

rm -rf "$PLATFORM_DIR/.gradle" "$PLATFORM_DIR/app/.cxx" "$PLATFORM_DIR/app/build"

echo ""
echo "Gradle APK metadata: $APK_OUTPUT_DIR/output-metadata.json"
echo "OpenXR Activity: $ANDROID_APPLICATION_ID_VALUE/android.app.NativeActivity"

if [[ "$INSTALL_APK" -eq 1 ]]; then
    APK_CANDIDATES=("$APK_OUTPUT_DIR"/*.apk)
    if [[ ${#APK_CANDIDATES[@]} -ne 1 || ! -f "${APK_CANDIDATES[0]}" ]]; then
        echo "ERROR: Expected exactly one APK in $APK_OUTPUT_DIR." >&2
        exit 1
    fi
    APK_PATH="${APK_CANDIDATES[0]}"
    "$ADB_BIN_VALUE" install -r "$APK_PATH"
fi

if [[ "$LAUNCH_OPENXR" -eq 1 ]]; then
    "$ADB_BIN_VALUE" shell input keyevent KEYCODE_WAKEUP
    "$ADB_BIN_VALUE" shell monkey -p "$ANDROID_APPLICATION_ID_VALUE" 1
fi
