# Native section storage

The profiler aggregates sections by name under their parent. Repeated calls
contribute to the same node's timing and call_count; the same name under another
parent has its own node. There is no configured limit on nodes per frame.

The current frame uses a growable contiguous scratch buffer. Capacity starts at
64 nodes, doubles when needed and remains allocated across frames and history
clears. Frames within the previous high-water capacity do not allocate section
scratch storage. Stack entries and tree links are indices, so growth preserves
open parent scopes and the tree's insertion order.

tc_profiler_current_frame()->sections can move during begin_section. Do not
retain section pointers while a frame is open; reacquire sections through the
frame and use indices. Completed history and independent capture entries each
own a compact copy of exactly section_count nodes. Those copies still allocate
when a frame closes, remain independent of scratch growth/reuse and are released
when their ring entry is overwritten, cleared or destroyed.

If growth fails or the requested storage is not representable, the profiler
logs an error and suppresses the affected subtree with balanced begin/end
semantics. Existing parent scopes and frame timing remain usable. Profiling
does not turn a memory allocation failure into a fabricated complete tree.

The separate maximum nesting depth is TC_PROFILER_MAX_DEPTH (16); sections
beyond it stay balanced and preserve their valid ancestors. Section names
retain TC_PROFILER_MAX_NAME_LEN storage (64 bytes including the terminator).
The short history retains 120 frames; independent captures choose their own
frame capacity. These are separate contracts from the removed 256-node ceiling.

Remote transport retains its packet byte budget and negotiated receiver limits,
and rejects a complete frame that cannot fit. It does not truncate a frame's
sections. See [remote profiler](../../../engine/termin-profiler-remote/docs/index.md).
