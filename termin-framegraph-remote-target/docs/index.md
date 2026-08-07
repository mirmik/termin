# Remote Framegraph Target Service

`termin-framegraph-remote-target` is the optional target-side transport for the
versioned `termin-framegraph-remote` protocol. It depends on `termin-engine`,
but not on the editor or Python.

The owner render thread constructs the service around the process's sole
`FrameGraphDebugger`, calls `start()`/`stop()`, and pumps commands through
`pump_render_thread()`. Only that pump reads or mutates debugger state. The I/O
thread owns loopback TCP sockets, authentication, framing, and transmission.
Bounded SPSC queues carry copied commands and immutable topology/status values;
queue overflow rejects or drops a whole logical message and is visible in
status counters and logs. Exact capture payloads are additionally bounded by a
global CPU memory budget and the peer's negotiated blob/chunk limits.

Every accepted connection receives a fresh non-zero session ID. Target and
pass IDs are meaningful only together with that session and the published
`graph_revision`. Topology-bound commands with a stale revision are rejected
without changing debugger selection.

An exact snapshot command becomes the existing frame-local
`FrameGraphCaptureRequest`. The render thread waits for capture completion and
performs the GPU-to-CPU readback; it never waits for a socket. RGBA8 resources
remain RGBA8, HDR color is transferred as RGBA float32, and depth as float32.
Only the immutable bounded CPU blob crosses to the I/O thread, which frames it
as metadata plus ordered chunks. Completion reports capture/readback/transfer
latency and bytes; cancellation, topology changes, unavailable resources,
readback failures and budget violations produce terminal statuses and logs.

Live preview reuses the same frame-local request with a non-zero long-edge
limit. The capture texture is downscaled on the GPU before bounded readback
and converted to RGBA8 for transport. Scheduling is capped by the requested
FPS. One capture may execute while `LatestValueSlot` retains at most one ready
frame; a slow receiver replaces that slot with the newest frame and the next
delivery carries an explicit receiver `DropEvent`. Network transfer never runs
on the render thread. Start/update/stop/cancel are safe to repeat, and topology
revision changes terminate the operation visibly.

Burst capture schedules 2--16 exact frame-local captures in order. Metadata
carries the common request/revision plus `burst_index`/`burst_count`; the
target rejects a burst whose cumulative retained payload would exceed the
negotiated memory budget. Capture, readback, RGBA conversion, transfer time,
effective preview FPS, bytes and dropped frames are exported by service status
and terminal status details.
