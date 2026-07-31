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
