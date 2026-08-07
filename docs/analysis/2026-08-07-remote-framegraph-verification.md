# Remote Framegraph Debugger verification

Date: 2026-08-07

This record closes the first end-to-end implementation pass for the network
Framegraph Debugger. It covers the native target/client pair, editor source
switching, Android render-runtime lifecycle and the release security gate.

## Native reciprocal smoke

The repeatable gate is:

```bash
./run-tests.sh
scripts/smoke-framegraph-remote
```

The smoke launches the production `RemoteFrameGraphTarget` and
`RemoteFrameGraphClient` in separate processes. The target renders a managed
256x256 Vulkan texture through a real `RenderingManager`; its clear pass is
shader-independent so this test measures the remote capture path rather than
the shader compiler installation.

The client verifies:

- authenticated handshake and topology discovery;
- rejection of a stale graph revision;
- an exact full-resolution Snapshot blob;
- Live Preview delivery and explicit stop;
- an ordered three-frame Burst;
- cancellation of an in-flight Burst;
- latest-wins dropping under a deliberately slow receiver;
- disconnect and a second authenticated session against the same target.

Observed on AMD Radeon Graphics (RADV STRIX_HALO, Mesa 26.0.3, Vulkan
1.4.335): 171 completed captures, 165 preview frames, 5 burst frames,
13,903,060 transmitted bytes and 136 capture-side drops. The effective preview
rate was 38.892 FPS. Aggregate work was 288.513 ms capture, 124.375 ms readback,
123.469 ms conversion and 740.832 ms encoding. These values are a regression
sample for this machine, not a cross-platform performance requirement.

## Editor and resource lifetime

`termin_tests` includes two complementary editor-side checks:

- `RemoteFrameGraphDebuggerSource assembles exact color HDR and depth blobs`
  validates exact Color, HDR and Depth assembly and verifies that replaced and
  disconnected remote textures are destroyed;
- `FrameGraphDebuggerView switches local remote stale and local in one tree`
  exercises local -> remote -> disconnected/stale -> local switching in one
  view, including authentication failure and Live Preview start/stop.

Together they guard against retaining imported GPU resources after source
replacement or disconnect.

## Android device lifecycle

Device: ONEPLUS A5000, Android 10, arm64-v8a. The debug APK was launched through
`scripts/android-framegraph-forward` and observed over one authenticated TCP
session. Pressing Home destroyed the render runtime and resuming recreated it
without restarting the application process:

```text
process pid:       30488 -> 30488
attached topology: revision 2, targets 1
suspended update:  revision 3, targets 0
resumed update:    revision 4, targets 1
```

The suspend and resume topology/status packets are emitted by debugger
detach/attach itself, so a paused runtime does not need another rendered frame
to tell the desktop that its old topology is stale.

## Android release gate

A signed release APK was installed on the same device and launched with the
same remote-framegraph intent extras. `dumpsys package` reported neither
`DEBUGGABLE` nor any equivalent package flag. A production protocol client
could reach the local `adb forward`, but the device side closed the connection
before the framegraph handshake; logcat contained no remote-framegraph listener
message and no authentication token. The debug APK was then restored without
uninstalling the package or clearing its data.

During this run an unrelated repeated failure to load
`engine-shader-catalog.json` from the APK was observed and recorded separately
as Kanboard task #1353.

## Intended limits

- The target listens only on device/host loopback and requires a non-empty
  authentication token.
- Snapshot preserves native pixel data; Preview is bounded RGBA8 latest-wins;
  Burst is 2--16 exact ordered frames within the negotiated memory budget.
- Socket I/O stays off the render thread. GPU capture and readback execute only
  through the render-thread pump.
- A graph revision is part of every capture request. Stale requests fail
  explicitly instead of reading a different resource accidentally.
- Disconnect, cancellation and Android render-runtime teardown release pending
  captures and imported texture resources.
