# D3D11 Backend Inspection Notes

Date: 2026-07-02

## Scope

Inspected the current `tgfx2` Direct3D 11 backend around device/resource
creation, command-list execution, swapchain/D3DImage presentation, readback,
resource binding placement, and smoke coverage.

The backend is no longer a placeholder: it has a real device/context path,
shader bytecode loading, pipeline creation, input-layout reflection, bound
resource-set placement, tc resource materialization, readback, color MSAA
resolve, SDL swapchain presentation, and WPF `D3DImage` interop.

## Fixed In This Pass

- `D3D11RenderDevice::create_texture()` now treats requested SRV/RTV/DSV
  creation failure as texture creation failure instead of returning a handle
  with missing native views.
- `D3D11RenderDevice::register_external_texture()` now follows the same rule
  for external D3D11 textures.
- `D3D11RenderDevice::upload_buffer()` now validates upload ranges before both
  dynamic-map and default-buffer update paths.
- `D3D11RenderDevice::read_buffer()` now validates read ranges before staging
  copy/map.

## Findings

### Partial Native Texture Handles

Before this pass, texture allocation could succeed, a requested native view
could fail, and the backend would still return a non-zero `TextureHandle`. That
made later render-pass, sampling, blit, or readback failures look like unrelated
state bugs. Storage buffers already returned `{}` when SRV creation failed, so
textures now follow the same policy.

Remaining follow-up: add explicit regression coverage for invalid view
combinations once there is a convenient D3D11-only negative test harness.

### Storage Texture / UAV Boundary Is Not Explicit Enough

The public model and shader tooling can describe storage textures and D3D11
`u#` placement. The D3D11 runtime, however, does not create UAVs for textures,
does not expose `BoundResourceKind::StorageTexture`, does not bind graphics or
compute UAVs, and has no real compute pipeline path. `supports_compute=false`
is correct, but storage texture requests can still progress too far before
becoming inert.

Recommendation: reject storage textures for D3D11 at shader/runtime binding
plan creation until the runtime owns a real UAV policy. Storage buffers are a
separate SRV-backed read-only path today and should not be conflated with UAV
storage.

### `RGB8_UNorm` Is Ambiguous On D3D11

D3D11 has no ordinary 24-bit RGB texture format. The backend maps
`PixelFormat::RGB8_UNorm` to `DXGI_FORMAT_R8G8B8A8_UNORM`, and its byte-size
helper reports 4 bytes per pixel. Vulkan/OpenGL treat RGB8 as 3 bytes per
pixel. The tc texture path normalizes `TC_TEXTURE_RGB8` to RGBA8 before upload,
but public `create_texture(RGB8_UNorm)` plus `upload_texture()` remains a trap.

Recommendation: either reject public RGB8 on D3D11 with a clear log, or make
D3D11 normalize RGB8 descriptors to RGBA8 at creation/upload boundaries and
reflect that in `texture_desc()`.

### Dynamic Buffer Upload Semantics Are Still Loose

This pass added bounds checks, but `cpu_visible` buffers still use
`D3D11_MAP_WRITE_DISCARD` for every upload. That is safe for full rewrites, but
partial updates can invalidate untouched bytes. The current callers mostly use
full uploads or per-draw temporary buffers, so this is not an immediate breakage,
but the contract should be tightened.

Recommendation: either document `cpu_visible` D3D11 uploads as full-buffer
rewrites, or add a separate update strategy for partial dynamic uploads.

### `blit_to_texture()` Leaves Immediate Context State Dirty

D3D11 `blit_to_texture()` binds its own shaders, constant buffer, sampler, RTV,
viewport, raster/depth/blend state, and only clears part of that state after the
draw. `RenderContext2::begin_pass()` resets enough cached state for the common
engine path, and the WPF `D3DImage` bridge explicitly calls `reset_state()` after
presentation. The SDL swapchain path does not currently do the same.

Recommendation: make blit state restoration a D3D11 backend responsibility, or
call `reset_state()` consistently after presentation blits. The former is
cleaner because `blit_to_texture()` is a public backend API.

### Coverage Gaps

Existing D3D11 smoke coverage is useful and covers clear, draw, tc resources,
bound resource sets, RenderContext2, push constants, Canvas2D/Text2D, MSAA color
readback, and window presentation. It is still mostly happy-path coverage.

Useful next tests:

- invalid texture view creation returns an empty handle;
- buffer upload/readback out-of-range logs and does not crash;
- RGB8 public upload behavior is rejected or normalized;
- D3D11 storage texture / UAV requests fail explicitly;
- `blit_to_texture()` does not leak state into the next low-level command-list
  user.

## Follow-up Fixes

- D3D11 storage texture/UAV paths now fail explicitly: storage textures are
  rejected by the D3D11 binding-plan builder, `TextureUsage::Storage` texture
  descriptors are rejected at creation/registration, and D3D11 resource-set
  creation refuses planned or legacy `u#` placements.
- Public D3D11 `RGB8_UNorm` texture descriptors are rejected with a clear log.
  The tc texture bridge still normalizes `TC_TEXTURE_RGB8` to RGBA8 before
  upload.
- D3D11 texture uploads now validate mip, region bounds, format byte size, and
  minimum payload size before `UpdateSubresource`.
- The shader `blit_to_texture()` path now clears D3D11 immediate-context state
  via `reset_state()` after the draw.
- Regression coverage now includes D3D11 binding-plan rejection for storage
  textures and D3D11 smoke checks for public RGB8, storage texture creation, and
  storage texture resource-set creation.

## Remaining Suggested Next Fixes

1. Add focused negative tests for invalid native texture view creation once a
   convenient D3D11-only negative test harness exists.
2. Add coverage for buffer upload/readback out-of-range logging and texture
   upload range rejection.
3. Tighten or document partial upload semantics for `cpu_visible` D3D11 buffers.
