# Android remote Framegraph Debugger

The Android runtime can expose its native Framegraph Debugger to the desktop
editor through an ADB-forwarded, loopback-only TCP connection. The listener is
process-scoped, while its `FrameGraphDebugger` attachment follows the Android
render runtime. During pause or surface loss the service publishes an empty,
revised topology and reports a suspended session. When Vulkan, `EngineCore` and
`RenderingManager` are recreated, the same authenticated connection receives a
new topology revision. Attach and detach push these lifecycle updates directly;
they do not depend on another render-thread pump. No GPU handle crosses the
service boundary.

## Build and connect

Build and install a debug APK:

```bash
task build:android -- --abi arm64-v8a
task build:android:apk -- --abi arm64-v8a --variant debug
adb -s SERIAL install -r build/android-gradle/app/outputs/apk/debug/app-debug.apk
```

Launch it and create the host-to-device route:

```bash
scripts/android-framegraph-forward --serial SERIAL
```

The helper prints the host port and generated launch token. Enter them in the
Framegraph Debugger remote connection controls. Defaults are host/device port
`46052`; use distinct `--host-port` values for concurrent devices.

The listener starts only when all of these conditions hold:

- the APK has `ApplicationInfo.FLAG_DEBUGGABLE`;
- `termin.framegraph.remote=true` is present in the launch intent;
- `termin.framegraph.port` is in `1..65535`;
- `termin.framegraph.token` is non-empty.

Release APKs therefore ignore a request to enable the listener. The token is
passed to native code but is never written to logcat. The native service also
rejects non-loopback binds and invalid authentication. If the remote profiler
is enabled in the same launch, its device port must differ from the framegraph
port.

## Lifecycle and troubleshooting

`TerminAndroid` logs a `framegraph_remote` telemetry line for the first two
rendered frames and every 60 frames. It includes connection/attachment state,
graph revision, Snapshot/Preview/Burst counts, bytes, bandwidth, drops and
average render-thread pump time. It never includes the authentication token.

Pause/resume and surface recreation intentionally detach and rebuild the render
runtime. A connected desktop may temporarily show an empty suspended topology;
it must reconcile the new revision after resume. Pending capture operations end
with `resource_unavailable` instead of retaining graphics objects.

Useful checks:

```bash
adb -s SERIAL logcat -s TerminAndroid TerminActivity TerminAndroidJNI
adb -s SERIAL forward --list
adb -s SERIAL forward --remove tcp:46052
```

Snapshot keeps exact native pixel semantics. Live Preview is GPU-bounded by its
long-edge setting, converted to RGBA8 and delivered latest-wins; Burst retains
2--16 exact frames under the negotiated memory budget. Socket I/O never runs on
the Android render thread.
