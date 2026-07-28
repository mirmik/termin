# Backend-neutral MRT Contract

Date: 2026-07-28.

Status: accepted and partially implemented.

Board:

- umbrella #992 `[graphics/render] Backend-neutral MRT foundation`;
- #1026 `RenderContext2` and pipeline identity;
- #1027 OpenGL draw and clear semantics;
- #1028 Vulkan load/store semantics;
- #1029 framegraph attachment composition;
- #1030 cross-backend smoke.

This contract is the MRT foundation assumed by
[`2026-07-28-extensible-material-surface-contracts.md`](2026-07-28-extensible-material-surface-contracts.md).

## Decision

Multiple render targets are a pass-local ordered attachment set assembled from
independent framegraph texture resources.

```text
named framegraph textures
        |
        v
pass-local ordered color attachment set + optional depth
        |
        v
RenderContext2 -> graphics pipeline identity -> backend command list
```

Color attachment index is semantic:

```text
color attachment 0 <-> SV_Target0
color attachment 1 <-> SV_Target1
...
color attachment N <-> SV_TargetN
```

The framegraph does not represent a G-buffer as one persistent multi-color FBO
object. Its planes remain independently named textures with independent
lifetime, aliasing, sampling, and debugger capture.

## Existing descriptor

The low-level `tgfx::RenderPassDesc` remains the owning render-pass descriptor:

```cpp
struct RenderPassDesc {
    std::vector<ColorAttachmentDesc> colors;
    DepthAttachmentDesc depth;
    bool has_depth;
};
```

Each color descriptor carries texture, load operation, store operation, and
clear color. `RenderContext2::begin_pass(const RenderPassDesc&)` validates the
complete set and opens the backend pass. The older
`begin_pass(color, depth, ...)` overload constructs a one-color descriptor and
delegates to the same path.

The owning vector is not copied into the per-draw pipeline lookup. Ordered
color formats use a bounded array plus count in mutable render state and the
pipeline cache key.

## Limits

Termin defines a portable engine maximum of eight color attachments:

```text
TGFX2_MAX_COLOR_ATTACHMENTS = 8
```

The effective limit is:

```text
min(TGFX2_MAX_COLOR_ATTACHMENTS,
    BackendCapabilities::max_color_attachments)
```

The prototype G-buffer uses three attachments and is therefore within the
minimum guarantees of the target backends.

## Validation

`RenderContext2` rejects the attachment set before calling the backend when:

- the color count exceeds an engine or backend limit;
- no color or depth attachment exists;
- a required texture handle is null or unknown;
- a texture lacks the appropriate color/depth attachment usage;
- one texture occurs in more than one attachment slot;
- width, height, or sample count differ;
- a format, dimension, or sample count is invalid;
- `has_depth` and the depth texture disagree.

A rejected descriptor produces an error log and does not partially open a
render pass.

Backend implementations may add native capability and completeness checks.
They must not silently remove invalid attachment entries, because doing so
would renumber later `SV_TargetN` outputs.

## Pipeline identity

Graphics pipeline identity includes:

- color attachment count;
- the ordered color format sequence;
- optional depth format;
- sample count;
- the existing shaders, vertex layouts, and fixed-function state.

Changing attachment order creates a different pipeline even when the set of
formats is otherwise identical. Entries beyond `color_format_count` have no
semantic effect.

The first contract applies one blend state and one color mask uniformly to all
color attachments. This is sufficient for the opaque G-buffer. Independent
per-target blending can be introduced later as an explicit pipeline-state
extension; it is not implicit in MRT.

## Load, store, and clear

Every attachment owns its load/store operations. A backend must preserve:

- `Load`: retain previous contents;
- `Clear`: initialize that attachment with its own clear value;
- `DontCare`: previous or resulting contents are not required;
- `Store`: contents remain available after the pass.

OpenGL must select all draw buffers and use per-attachment clear operations.
Vulkan render-pass identity must include the ordered attachment operations.
D3D11 binds the ordered RTV array and clears individual RTVs.

The first deferred pipeline is single-sample, but the common contract validates
and carries sample count rather than hard-coding single-sample rendering.

## Framegraph composition

A pass declares its outputs as independent resources and owns a stable ordered
list of their names. Execution resolves those names through `ExecuteContext`
and constructs `RenderPassDesc` in declaration order.

Iteration order of `Tex2Map` or another associative container is never used as
attachment order.

The legacy `FboComposition { color, depth }` remains a compatibility mechanism
for existing one-color passes. It is not expanded into a backend-like
multi-color framebuffer resource.

## Verification

The portable smoke scenario writes distinct values to `SV_Target0..2`, uses a
shared depth attachment, and reads every output in a later pass.

It must verify:

- attachment ordering;
- different color formats;
- independent clear values;
- load preservation;
- common depth;
- invalid extent/sample/count diagnostics;
- Vulkan, OpenGL, and D3D11 parity.

Platform-specific smoke may run separately, but all backends implement the
same semantic scenario.
