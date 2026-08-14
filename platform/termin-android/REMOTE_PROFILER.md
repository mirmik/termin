# Android remote profiler

The Android showcase can expose the engine frame profiler to the desktop Frame
Profiler over an ADB-forwarded, loopback-only TCP connection. The service is
process-scoped: destroying and recreating the Android surface does not interrupt
the profiling session. Socket I/O stays on its worker thread; the render thread
only applies controls and publishes completed frame snapshots.

## Build and run

Build the Android SDK and a debug APK, then install it on the selected device:

```bash
task build:android -- --abi arm64-v8a
task build:android:apk -- --abi arm64-v8a --variant debug
adb -s SERIAL install -r build/android-gradle/app/outputs/apk/debug/app-debug.apk
```

Start the APK and create the host-to-device forward with:

```bash
scripts/android-profiler-forward --serial SERIAL
```

The script prints the host port and generated authentication token. Enter those
values in the editor's Frame Profiler remote connection fields, connect, and use
Start/Pause and section profiling normally. For multiple concurrent devices,
give each invocation a distinct `--host-port` and, if needed, `--device-port`.

The APK listens only on device loopback. The remote service requires all of the
following intent extras:

- `termin.profiler.remote=true`
- `termin.profiler.port` in `1..65535`
- a non-empty `termin.profiler.token`

The gate additionally requires `ApplicationInfo.FLAG_DEBUGGABLE`, so a normal
release APK never starts the listener even if the extras are supplied. Tokens
are not written to logcat.

## Measurements and troubleshooting

`TerminAndroid` writes a `profiler_remote` status line for the first two frames
and every 60 frames afterward. It includes connection and capture state,
completed and dropped frames, transmitted bytes, and average render-thread pump
time. It also reports interval transmit bandwidth as `tx_kib_s`. These values
make cadence-only and section-enabled captures directly
comparable without putting socket work on the render thread.

Useful checks:

```bash
adb -s SERIAL logcat -s TerminAndroid TerminActivity TerminAndroidJNI
adb -s SERIAL forward --list
adb -s SERIAL forward --remove tcp:46051
```

A disconnected or stalled desktop receiver cannot block rendering: outbound
batches and controls use bounded queues, and overflow is reported as drops on
the next healthy session.
