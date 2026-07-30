# Remote Profiler: network and Android feasibility

Date: 2026-07-30

## Decision

Remote profiling is feasible without replacing the existing profiler. The
recommended design is a native, versioned, bidirectional profiler protocol over
TCP, with a target-side capture service and an editor-side remote data source.
The target must never expose `tc_profiler_capture` to a network thread:
completed frames are copied at the profiler frame boundary into a bounded SPSC
queue, and only queue-owned immutable packets cross to the I/O thread.

The first Android delivery should use a TCP listener bound to device loopback
and `adb forward`. This is reliable over USB and wireless ADB, requires no
service discovery or TLS, and does not expose a diagnostics endpoint to the
local Wi-Fi network. Direct LAN connection is a follow-up mode: it must be
explicitly enabled and protected by an authenticated encrypted transport before
binding to a non-loopback address.

MCP is not the data plane. The current MCP implementation is Python HTTP/JSON-RPC,
is not present in the native Android runtime, and JSON-RPC per frame is a poor
fit for bounded high-rate telemetry. MCP may later expose coarse control or
discovery, but the profiler stream needs its own compact native protocol.

## Current state

### Useful foundations

`termin-base` already has most of the capture semantics needed by a remote
producer:

- `tc_profiler_capture` is an independent bounded subscription to completed
  frames;
- capture can retain cadence-only frames while hierarchical section profiling
  is disabled;
- cursor/range reads report overwritten frames explicitly;
- each completed frame owns a compact copy of its section array;
- frame identity, monotonic start time, start-to-start interval, active time,
  target interval, deadline lateness and missed intervals are already recorded.

The standalone Frame Profiler already presents raw frame timelines, exact
unsmoothed section trees, hitch navigation and statistics. Reusing its models
is preferable to creating a second remote-only UI.

### Blocking gaps

#### Android currently produces no profiler frames

`EngineCore::run()` owns `tc_profiler_begin_frame_with_info()` and
`tc_profiler_end_frame()`. `EngineCore::tick_and_render()` deliberately assumes
that a frame is already open and does not create one.

The Android host calls `tick_and_render()` directly from
`termin_android_render_frame()`, then performs swapchain composition/present
outside `EngineCore`. Consequently, enabling the profiler in an Android build
does not produce a completed frame and all section calls are no-ops.

This is a precondition independent of networking. The durable fix is an
explicit host-driven frame-scope API shared by `EngineCore::run()` and external
hosts. The Android scope should cover input dispatch, tick/render and
compose/present, and should consume the Choreographer timestamp rather than
inventing another clock. It must not make `tick_and_render()` silently create a
fallback frame because that would exclude host work and risk nested frames.

#### Capture reads are not thread-safe

The profiler singleton, capture list and capture rings have no synchronization.
Pointers returned by `tc_profiler_capture_at()` are valid only while the ring
slot remains retained. A network thread reading the ring concurrently with
`tc_profiler_end_frame()` can race an overwrite/free, and a network thread
toggling or destroying a capture can race the frame thread's capture-list
iteration.

Adding a mutex around every profiler section is unnecessary and would damage
the hot path. The ownership rule should instead remain strict:

- profiler state and subscription registration are frame-thread-owned;
- network commands are transferred to the frame thread through a bounded
  command queue or atomics;
- completed immutable frames are copied into a bounded producer/consumer queue
  at the end-frame boundary;
- the I/O thread owns sockets, framing, retransmission state and serialization
  buffers, but never a profiler pointer.

#### The Frame Profiler controller is local-source-specific

`FrameProfilerController` constructs a `tc_profiler_capture` directly and also
controls an `EngineCore` instance for the `Include UI` option. A remote target
needs the same timeline/tree/statistics projections but different commands and
capabilities.

Extract a source/session boundary rather than adding remote branches throughout
the controller. A source supplies immutable frames, gaps, connection metadata
and capabilities; commands such as capture, detailed sections and clear are
routed through that source. Local capture and remote connection become two
implementations. Target-specific controls such as `Include UI` are advertised
as optional capabilities and hidden/disabled when unsupported.

#### Android packaging has no network permission or profiler configuration

The current manifest has no `android.permission.INTERNET`. The native APK also
has no Python/MCP runtime and no command-line/environment configuration path.
Remote profiling must therefore be a native SDK component and must have an
explicit Android configuration boundary.

For development packages, configuration can initially be build-time/app
metadata: enabled flag, loopback bind address, port and generated/session token.
Project runtime-package data should describe application behavior, not silently
enable a diagnostics listener. Release artifacts should leave the target
disabled unless the exporter explicitly produces a profiling build.

## Proposed architecture

```text
frame/render thread                         network I/O thread

tc_profiler begin/sections/end
              |
              v
RemoteProfilerTarget::on_completed_frame()
  - applies queued control commands
  - interns section names
  - copies an immutable wire batch
  - never waits for the socket
              |
              v
       bounded SPSC queue  ----------------> TCP connection
          drop counter                       framing/auth/backpressure
                                                   |
                                                   v
editor RemoteProfilerSource <---------------- versioned stream
  - bounded received session
  - reconnect/session identity
  - gap/drop accounting
  - local statistics projection
              |
              v
shared Frame Profiler timeline/tree UI
```

Place the native protocol and target service in a small optional module above
`termin-base` (for example `termin-profiler-remote`), not in `termin-runtime`
and not in `termin-app`. The module may depend on `termin-base`; headless,
player, editor and Android hosts may opt into it. `termin-runtime` remains an
embeddable content/runtime library without a mandatory diagnostics server.

The editor receiver and source adapter belong to `termin-app`, while host
configuration belongs to each host (`termin-player`, Android, and possibly the
editor play-mode host).

## Wire protocol

Use a single full-duplex TCP connection. TCP gives ordered reliable delivery,
works with `adb forward`, and is adequate for the expected stream rate. UDP
adds fragmentation, reassembly and loss policy without a useful benefit here.
WebSocket/HTTP adds a library and framing layer but does not improve the native
target or editor integration.

Every message should have a fixed endian-independent envelope:

- magic;
- protocol major/minor;
- message type;
- flags;
- payload length;
- stream sequence number;
- session identifier.

The protocol begins with `ClientHello` / `TargetHello`. The target advertises:

- engine/profiler protocol versions;
- platform, ABI, build type and build identifier;
- process/session identity;
- clock frequency/epoch semantics;
- supported capabilities and limits;
- current capture/profiling state.

Control messages:

- start/resume cadence capture;
- pause capture;
- enable/disable hierarchical sections;
- clear target-side capture/stream cursor;
- request status;
- ping/clock correlation;
- graceful disconnect.

Data messages:

- section-name dictionary additions;
- one or more frame records;
- explicit producer queue drops;
- explicit capture-ring/source gaps;
- status/error events.

Do not serialize C structs verbatim: padding, `bool`, pointer fields, endianness
and future layout changes make them unsuitable as a contract. Encode named wire
fields with fixed-width integers and IEEE-754 values. Section names should be
interned per session so a frame carries small name IDs rather than repeating up
to 64 bytes per section.

With 256 sections, the current in-memory section array is roughly tens of
kilobytes per worst-case frame. Even a straightforward fixed-field wire format
is practical over USB/Wi-Fi, and dictionary encoding reduces the common case
further. Compression should be considered only after measuring real captures;
it is not required for the first protocol.

## Backpressure and failure semantics

The render thread must never block on networking. The producer queue is bounded.
When full, drop complete oldest or newest batches according to one documented
policy and increment a monotonic drop counter. The next delivered message marks
the gap. Do not partially deliver a frame.

The editor retains its own bounded session. Disconnect does not destroy already
received data. Reconnect creates a new session unless the target proves the same
session ID and can resume from the requested sequence; resumable replay is not
required for the first version.

All failures are logged on both sides:

- bind/listen/accept/connect failures;
- authentication and version mismatch;
- malformed/oversized frames;
- producer and receiver drops;
- failed control commands;
- abnormal disconnect and shutdown timeout.

Payload sizes, section counts and name lengths must be validated before
allocation. Protocol limits should be negotiated but remain capped by local
hard limits.

## Android connection modes

### First delivery: loopback plus ADB forwarding

The target listens on `127.0.0.1:<device-port>`. The workstation runs:

```bash
adb forward tcp:<host-port> tcp:<device-port>
```

The editor connects to `127.0.0.1:<host-port>`. The same approach works when
ADB itself is transported over Wi-Fi. Benefits:

- no LAN discovery;
- no device IP selection;
- no exposed Wi-Fi listener;
- deterministic device selection through `adb -s <serial>`;
- no TLS prerequisite for the tunnel-only mode.

Add `android.permission.INTERNET`, even for native sockets. Android's Java
cleartext HTTP policy is not the protocol boundary here because the service is
a native TCP socket, but the permission is still required.

The exporter/editor can later automate port allocation, `adb forward`, token
provisioning and connection metadata. Manual forwarding is enough for the first
end-to-end gate.

### Follow-up: direct Wi-Fi/LAN

Binding to `0.0.0.0` must require an explicit profiling/development option.
Bearer authentication alone does not protect profile contents or controls from
passive LAN observers. Direct LAN mode therefore needs authenticated encryption
(TLS with a pinned/generated development identity, or an equivalently reviewed
secure channel) before it is considered production-ready.

mDNS discovery is optional convenience after secure identity exists. Discovery
must not be used as authentication. An outbound target-to-collector mode may be
useful for devices behind restrictive networks, but should share the same
protocol and is not needed for Android over ADB.

## Frame semantics on Android

Use Choreographer's `frameTimeNanos` as the host frame timestamp and preserve
start-to-start cadence. The first frame has no interval. Target interval should
come from the active display/vsync cadence when available; it must not be
hard-coded to 16.666 ms because Android devices change refresh rate.

The profiled active scope should include:

1. queued input dispatch;
2. scene tick;
3. before-render/render/after-render;
4. output validation;
5. swapchain compose/present and recreation work.

Surface absence, pause/resume and renderer recreation introduce real gaps.
They should reset or annotate cadence rather than presenting lifecycle downtime
as a rendering hitch. Target/service lifetime belongs to application
initialize/shutdown, while capture frame lifetime follows successful render-loop
frames. Socket teardown must occur before profiler/runtime teardown.

The first version remains main/render-thread CPU profiling. The current global
section stack is not suitable for worker-thread event collection; remote
transport must not be presented as solving multithread or GPU profiling. Those
need later trace/event streams and explicit thread/GPU correlation.

## Delivery slices

### 1. External host frame scope

- expose one explicit, move-only/RAII host frame scope with cadence input;
- make `EngineCore::run()` use the same primitive;
- integrate it around the complete Android input/tick/render/present path;
- reset/annotate cadence across Android lifecycle gaps;
- test nested/unbalanced scope rejection and standalone `tick_and_render()`;
- verify Android captures non-empty frames and exact section trees.

### 2. Native remote target and protocol

- add versioned codec tests, malformed input limits and compatibility checks;
- add bounded frame-thread-to-I/O-thread queues and drop accounting;
- implement loopback TCP listener, token handshake, commands and clean shutdown;
- prove that a stalled/disconnected client cannot stall or grow target memory;
- run host-side integration tests without Android first.

### 3. Editor remote source

- separate local/remote frame sources from Frame Profiler presentation;
- add connect/disconnect/status and source capability projection;
- preserve received frames on disconnect and show transport/source gaps;
- test local behavior for regressions and remote deterministic replay.

### 4. Android packaging and device gate

- add the native module to the Android SDK/APK and add network permission;
- add explicit profiling-build configuration, loopback port and token handling;
- document/manual-script `adb forward` with device serial selection;
- verify on a physical Android device that capture can be started from the
  editor, paused, selected, and inspected while the app keeps rendering;
- record target overhead, stream bandwidth and drop count.

### 5. Secure direct LAN mode

- choose and integrate authenticated encryption;
- add explicit non-loopback opt-in and identity/pairing UX;
- add optional discovery only after identity is established;
- test hostile/malformed clients and reconnect behavior.

## Acceptance for the direction

- The same Frame Profiler window can switch between local and remote sources.
- An Android profiling build produces cadence and hierarchical section frames
  covering present, and can be inspected through `adb forward`.
- Network stalls cannot block the render thread or cause unbounded memory.
- Every loss point is visible as a gap/drop count rather than silently skipped.
- Release Android builds do not expose a listener by default.
- Direct LAN mode is not enabled without authenticated encryption.
- Full SDK/tests pass, followed by a physical-device Android smoke with measured
  profiler and transport overhead.

