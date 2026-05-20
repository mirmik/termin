# Quest/OpenXR foundation

## Goal

Build a path from the current Android Vulkan smoke app toward a native
OpenXR/Quest 2 application without mixing this work into the regular Android
surface renderer too early.

The immediate milestone is intentionally small:

- keep the current Android Vulkan smoke app working;
- introduce a separate `termin-openxr` module;
- compile against OpenXR headers in the Android SDK build;
- make the APK link/load that module and log the detected OpenXR header setup.

## SDKs and dependencies

Required soon:

- Android SDK + NDK, already used by `build-sdk-android.sh`;
- Khronos OpenXR SDK headers/loader, currently cloned locally into
  `termin-thirdparty/openxr-sdk`;
- Meta OpenXR SDK for Quest-specific samples/extensions:
  <https://github.com/meta-quest/Meta-OpenXR-SDK>

The Khronos SDK is enough for basic API compilation and common OpenXR types.
The Meta SDK should be added before we implement real Quest runtime behavior,
because it contains current Quest native samples and Meta extension headers.

## Current repository state

`termin-openxr` is a placeholder module with a small public API:

- reports whether OpenXR headers were available at build time;
- exposes the detected OpenXR API version;
- exposes the Android and Vulkan extension names we expect to need.

It does not create `XrInstance`, `XrSession`, or XR swapchains yet.

## Planned runtime architecture

The current Android smoke renderer uses:

- `SurfaceView`;
- `ANativeWindow`;
- Vulkan Android surface;
- tgfx2-owned render target;
- compose into a Vulkan swapchain;
- `vkQueuePresentKHR` hidden behind `VulkanSwapchain::compose_and_present`.

The Quest/OpenXR path must instead use:

- OpenXR frame loop: `xrWaitFrame`, `xrBeginFrame`, `xrEndFrame`;
- OpenXR view poses/projections from `xrLocateViews`;
- `XrSwapchain` images as the final render targets;
- no Android window swapchain present for immersive rendering.

The main tgfx2 gap is external Vulkan image wrapping for OpenXR swapchain
images. We need a way to register an `XrSwapchainImageVulkanKHR.image` as a
tgfx2 `TextureHandle` suitable for color/depth attachments.

## Implementation steps

1. Add a Quest/OpenXR manifest flavor or separate Activity.
2. Create a minimal OpenXR bootstrap:
   - Android instance create info;
   - system lookup for HMD form factor;
   - Vulkan graphics requirements;
   - session lifecycle.
3. Create XR swapchains and clear both eyes.
4. Wrap XR swapchain images into tgfx2 textures.
5. Render the current cube in stereo through tgfx2.
6. Replace the cube with a small exported scene/render pipeline path.
7. Add OpenXR action input for Quest controllers.

## Known risks

- The local `openxr-sdk` checkout is not pinned as a submodule yet.
- The current smoke animation is frame-count based; XR must be time/prediction
  based using OpenXR frame timing.
- `VulkanSwapchain::compose_and_present` is not usable for XR final output.
- Quest performance work will matter early: foveation, MSAA, draw call budget,
  and avoiding unnecessary offscreen composition.
