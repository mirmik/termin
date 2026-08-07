# termin-framegraph-remote

`termin-framegraph-remote` defines the native, versioned data contract for a
remote Framegraph Debugger. The codec is independent of sockets, the editor,
Python, `RenderingManager`, GPU handles and graphics backends. Target and
desktop services are layered above this module.

Protocol version 1 uses a fixed 32-byte big-endian envelope with the `TFGD`
magic, major/minor version, message type, flags, payload size, stream sequence
and session identity. Minor revisions are additive; a different major version
and unknown message types are rejected.

## Identity and revisions

Targets and passes use non-zero IDs that are stable only within the negotiated
session. A `TopologySnapshot` carries a non-zero `graph_revision`. Every
topology-bound command repeats the target ID and revision; a target service
must reject the command with `stale_revision` when its current revision no
longer matches. Resource and internal-symbol selectors contain names plus the
session-scoped pass ID where applicable. Native handles and pointers are never
part of the wire contract.

## Commands and captures

The command family covers topology refresh and target selection, exact
snapshot, live-preview start/update/stop, bounded burst capture, cancellation,
status/ping and graceful disconnect. Capabilities advertise which operations
the target implements.

Capture payloads use two phases:

1. `CaptureMetadata` fixes request/revision/blob/frame identity, dimensions,
   pixel format, encoding, byte count and chunk count.
2. Ordered `BlobChunk` messages carry bounded byte ranges. `BlobAssembler`
   rejects a wrong blob, changed chunk count, duplicate/out-of-order index,
   non-contiguous offset and an incomplete or oversized final blob.

An exact snapshot retains native pixel/depth/HDR meaning. RGBA8/PNG are
separate encodings suitable for bounded live preview and must not silently
replace exact capture semantics.

## Limits and failure policy

All counts and string/blob sizes have local hard limits checked before reserve
or allocation. Peers negotiate values no larger than those limits. A single
wire payload is at most 1 MiB; a capture blob is at most 256 MiB and is split
into at most 4096 chunks. Burst capture is limited to 16 frames and preview
requests to 60 FPS / 4096 pixels on the long edge.

Queue backpressure, readback/encoder loss and receiver loss are explicit
`DropEvent`s. Status/error messages correlate to a request and graph revision.
Transport and host layers must log malformed input, rejected commands,
authentication/version failure, drops and abnormal disconnects; no failure is
silently converted into a fallback capture.
