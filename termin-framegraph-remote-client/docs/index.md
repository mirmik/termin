# Remote Framegraph Client

`termin-framegraph-remote-client` owns the desktop-side loopback TCP transport
for the versioned framegraph protocol. It has no editor, Python, engine or GPU
dependency. One network thread performs connect/reconnect, handshake, framing
and callbacks. A bounded SPSC queue accepts commands from one editor thread;
commands left by a disconnected session are discarded and never replayed.

The client validates monotonic sequence and session identity before publishing
messages. Authentication, malformed streams, callback failures, queue overflow
and abnormal disconnects are logged and also delivered through the disconnect
callback where possible.

The client advertises exact color/HDR/depth snapshot reception. Blob assembly
belongs to the editor source rather than this transport: metadata and chunks
remain ordinary validated protocol messages here, preserving the client's
engine/GPU independence.

## Reciprocal smoke

Test builds provide a standalone Vulkan target and client. The target renders
a shader-independent 256x256 framegraph through the installed SDK libraries;
the client verifies authentication, topology, stale revision handling, exact
snapshot bytes, bounded live preview, ordered burst, cancellation, a slow
receiver with visible drops, disconnect and reconnect:

```bash
scripts/smoke-framegraph-remote
```

By default the runner asks the OS for a free loopback port; an explicit port
may be passed as its first argument when a forwarding setup requires one.

For a manual two-process or forwarded run, start the target first:

```bash
build/Release-tests/bin/termin_framegraph_remote_smoke_target 46125 smoke-token
build/Release-tests/bin/termin_framegraph_remote_smoke_client 46125 smoke-token
```

The client prints topology/drop/session evidence. The target prints aggregate
capture, readback, conversion, transfer, bandwidth-facing byte and effective
preview-FPS counters. Either process exits non-zero on timeout, an unbounded
slow-receiver path, incomplete capture, or protocol failure.
