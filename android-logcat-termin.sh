#!/bin/bash
# Filter logcat down to Termin Android tags.

set -e

ADB_BIN="${ADB:-adb}"
CLEAR=0
FOLLOW=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --clear|-c)
            CLEAR=1
            ;;
        --follow|-f)
            FOLLOW=1
            ;;
        --help|-h)
            echo "Usage: $0 [--clear] [--follow]"
            echo ""
            echo "Options:"
            echo "  --clear, -c     Clear logcat before reading"
            echo "  --follow, -f    Stream logs until interrupted"
            echo "  --help, -h      Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
    shift
done

if [[ $CLEAR -eq 1 ]]; then
    "$ADB_BIN" logcat -c
fi

LOGCAT_ARGS=()
if [[ $FOLLOW -eq 0 ]]; then
    LOGCAT_ARGS+=("-d")
fi

"$ADB_BIN" logcat "${LOGCAT_ARGS[@]}" \
    -s \
    TerminActivity:I \
    TerminOpenXRActivity:I \
    TerminAndroidJNI:I \
    TerminAndroid:I \
    TerminTcLog:I \
    AndroidRuntime:E \
    DEBUG:E \
    libc:E \
    BufferQueueProducer:E \
    '*:S'
