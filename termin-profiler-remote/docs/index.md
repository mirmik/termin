# termin-profiler-remote

`termin-profiler-remote` is the optional native remote-profiler protocol and
target transport layer above `termin-base`.

The public codec in `termin/profiler_remote/wire_codec.hpp` owns protocol
version 1, its fixed 32-byte big-endian envelope, typed payload schemas and all
hard allocation limits. It deliberately has no socket, editor, Android or
profiler-singleton dependency. Known message layouts accept newer minor
versions because minor revisions are additive; a different major version and
unknown message types are rejected.

See [the architecture decision](../../docs/analysis/2026-07-30-remote-profiler-network-android.md)
for transport ownership, backpressure and Android connection policy.

`RemoteProfilerTarget` is the bounded target-side service. Its lifecycle and
`pump_frame_thread()` run on the profiler frame thread; the owned I/O thread
owns all sockets and communicates through fixed-capacity SPSC queues. A full
outbound queue rejects one complete newest batch and reports the accumulated
loss before the next successfully queued batch. A stopped service clears its
capture and both queues, so restart begins from a deterministic idle state.

The listener accepts only `127.0.0.1` and requires a per-launch token in the
`ClientHello`. Android clients are expected to reach it through an explicit
ADB port forward; the service never exposes a device-network listener.

`RemoteProfilerClient` is the matching workstation-side transport. It owns a
background socket thread, accepts only `127.0.0.1`, reconnects with a fresh
authenticated handshake, and sends controls through a bounded SPSC queue.
Queued controls are session-scoped and are discarded on disconnect rather than
being replayed against a new process. Decoded messages are projected by the
editor's `RemoteFrameProfilerSource`; socket callbacks never mutate UI models.

For an Android target listening on port `46051`, establish the explicit tunnel
before connecting the Frame Profiler window:

```bash
adb forward tcp:46051 tcp:46051
```

Enter `46051` and the target's per-launch token in the window. The editor keeps
the last bounded remote history visible across a disconnect, marks the gap, and
can switch back to the still-live local source with **Use local**.
