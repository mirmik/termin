# Quest Vulkan follow-up changes

Date: 2026-08-06

Status: observations preserved; implementation reverted pending focused review.

## Context

Several Vulkan correctness and compatibility changes were made while enabling
validation and diagnosing square tile corruption in the Quest OpenXR showcase.
They were mixed with intrusive capture experiments, scene edits and a rejected
render-pass workaround. None of them should be accepted merely because that
combined tree built and ran.

The changes below were therefore reverted. Reapply them as small coherent
patches, verify the relevant contract, and keep them separate from the tile
artifact investigation described in
`docs/analysis/2026-08-06-quest-adreno-tile-artifacts.md`.
The broader stereo render-path redesign is described in
`docs/analysis/2026-08-06-quest-openxr-render-path.md`.

## Candidate changes

### Vulkan/OpenXR API and shader target

The Android backend previously defaulted to Vulkan 1.0 while GLSL and Slang
compilation emitted Vulkan 1.2 / SPIR-V 1.5 output. The diagnostic branch:

- queried `xrGetVulkanGraphicsRequirementsKHR`;
- selected at least Vulkan 1.1 within the runtime's reported range;
- requested that version from `VulkanRenderDevice`;
- changed both runtime shaderc and `termin_shaderc` to Vulkan 1.1 / SPIR-V 1.3;
- bumped the runtime SPIR-V cache version.

Before reapplying, define the engine-wide Vulkan/SPIR-V baseline rather than
silently changing Android only. Test cached and offline-compiled GLSL and Slang
assets on desktop Vulkan and Quest.

### Instance extension dependency

The Quest OpenXR runtime supplied
`VK_KHR_surface_protected_capabilities`. That extension requires
`VK_KHR_get_surface_capabilities2`, which was not present in the returned list
and had to be added explicitly before instance creation.

Reapply this as dependency normalization for requested instance extensions,
with a focused test where practical. Confirm the dependency against the Vulkan
extension specification and do not assume core promotion replaces an extension
name required by another extension.

### VMA dispatch on Android

After moving the device to Vulkan 1.1, VMA attempted to use promoted memory
entry points through a loader/layer combination that was not usable on the
Quest diagnostic setup. The experiment configured VMA with explicit
`vkGetInstanceProcAddr` / `vkGetDeviceProcAddr` dispatch and kept VMA's Android
memory path on Vulkan 1.0 while the device itself remained Vulkan 1.1.

Reapply only after checking the exact VMA configuration contract and the
active Android loader. Prefer a general capability-based choice over a
Quest-specific hard-coded exception if it is reliable on the affected loader.

### Render-pass initial layouts

`VulkanCommandList` explicitly transitions attachments to
`COLOR_ATTACHMENT_OPTIMAL` or `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` before
`vkCmdBeginRenderPass`. Render-pass descriptions nevertheless declared
`initialLayout = UNDEFINED` for clear operations. The diagnostic change made
the declared initial layout agree with the explicit transition for both clear
and load operations.

Reapply as a standalone validation fix. Verify clear, load and discard cases,
including external OpenXR images and framegraph-aliased textures.

### Attachment dependency access masks

The diagnostic branch added:

- `LATE_FRAGMENT_TESTS` alongside early fragment tests;
- color attachment reads;
- depth/stencil attachment reads;
- matching read access in image-layout transitions.

The motivation is that blending, attachment loads and depth testing read
existing attachment contents. Reconstruct the precise producer/consumer
hazards and use the narrowest correct stages and access masks. Test with Vulkan
synchronization validation enabled.

### Texture-copy layout restoration

`copy_texture` previously left both images in
`SHADER_READ_ONLY_OPTIMAL`. This is invalid for a non-sampled external image,
including an OpenXR swapchain image created only for color attachment and
transfer usage. The diagnostic implementation restored the source's previous
layout and selected the destination's final layout according to whether it was
sampled.

Reapply with focused tests for:

- sampled source and destination;
- non-sampled external source;
- failed/incompatible copies;
- previously undefined layouts;
- depth/stencil aspects.

The ownership rule for `current_layout` should be explicit; avoid encoding a
capture-specific assumption in the generic copy operation.

### Sampled-image descriptor handling

The resource-set path accepted combined image samplers but did not handle a
separate `VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE` case. It also allowed an explicitly
provided null texture to replace the default texture, producing an invalid
lookup/write path. The diagnostic change used the default texture for null
sampled bindings and added the separate sampled-image descriptor case.

Reapply with resource-layout/reflection tests covering combined samplers,
separate sampled images and samplers, absent bindings and explicit null
bindings.

### OpenXR swapchain completion

The current OpenXR path submits Vulkan commands and releases acquired
swapchain images without an explicit per-submission completion contract at the
release site. A diagnostic `render_device->wait_idle()` made completion
unambiguous but stalls the entire queue and did not remove the tile artifact.

Do not restore the global idle wait as the final fix. Define how the OpenXR
runtime waits for the submission that writes each released image. If the active
OpenXR extension set cannot import a Vulkan synchronization primitive, wait on
a narrowly scoped submission fence before `xrReleaseSwapchainImage` and make
that cost visible in timing telemetry.

## Acceptance

- Each concern above is landed as a focused, reviewable patch or explicitly
  rejected with its contract documented.
- Linux SDK and central tests pass.
- Android SDK and Quest showcase APK build.
- Vulkan core and synchronization validation run without new diagnostics.
- A Quest device smoke covers both eyes, several minutes of movement and
  grabbing, and repeated application restart.
- The OpenXR swapchain completion path has no unconditional device/queue idle
  in steady-state code unless separately justified and measured.
