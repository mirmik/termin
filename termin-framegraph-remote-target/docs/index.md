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
status counters and logs.

Every accepted connection receives a fresh non-zero session ID. Target and
pass IDs are meaningful only together with that session and the published
`graph_revision`. Topology-bound commands with a stale revision are rejected
without changing debugger selection. V1 of this service advertises topology
only; capture commands are explicitly rejected until the capture service is
enabled.
