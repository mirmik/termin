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

## Reciprocal desktop smoke

Test builds provide a standalone target and client that exercise the complete
handshake, capture controls, cadence frames and detailed section frames:

```bash
build/Release-tests/bin/termin_profiler_remote_smoke_target 46123 smoke-token
build/Release-tests/bin/termin_profiler_remote_smoke_client 46123 smoke-token
```

Start the target first. The client starts and pauses a cadence capture, then
repeats the sequence with section profiling enabled. Both programs exit with a
non-zero status on timeout or protocol failure.

The target deliberately listens only on loopback. To test two desktop machines,
run the target on the machine being profiled and create a local SSH forward on
the machine running the client:

```bash
ssh -N -L 46124:127.0.0.1:46123 user@target-machine
build/Release-tests/bin/termin_profiler_remote_smoke_client 46124 smoke-token
```

This smoke verifies the transport independently of an editor integration.

## Desktop editor and player target

`termin_editor` and `termin_player` can expose their real host frames through
the same loopback-only target. The listener is disabled unless the explicit
opt-in flag is present. Configure one process launch with:

```bash
TERMIN_REMOTE_PROFILER=1 \
TERMIN_REMOTE_PROFILER_ADDRESS=127.0.0.1 \
TERMIN_REMOTE_PROFILER_PORT=46123 \
TERMIN_REMOTE_PROFILER_TOKEN='per-launch-secret' \
./sdk/bin/termin_editor /path/to/Project.terminproj
```

The address variable is optional and defaults to `127.0.0.1`; non-loopback
addresses are rejected. Port and token are mandatory whenever the opt-in flag
is enabled. Leaving `TERMIN_REMOTE_PROFILER` unset creates no listener.

For the player, apply the same variables to `./sdk/bin/termin_player`. To
inspect a process on another desktop machine, preserve the loopback boundary
with an SSH local forward from the workstation running Frame Profiler:

```bash
ssh -N -L 46124:127.0.0.1:46123 user@target-machine
```

Connect Frame Profiler to local port `46124` with the same token. The target is
pumped after the complete `EngineHostFrameScope` closes, so cadence and section
data cover the editor/player host frame rather than only render callbacks.
