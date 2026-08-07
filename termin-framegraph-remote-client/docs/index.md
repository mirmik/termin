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
