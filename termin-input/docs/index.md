# termin-input

`termin-input` содержит input abstractions и bindings для состояний ввода,
используемых engine/editor/display слоями.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-input)
- [termin-base input enums](../../termin-base/docs/index.md)

## Основные области

- Public headers в `include/`.
- C++ implementation в `src/` и `cpp/`.
- Python bindings в `cpp/bindings/`.
- Python package в `python/termin/input`.

## Публичный API

Python package: `termin.input` через пакет `termin-input`.

Базовые enum-значения ввода (`Action`, `MouseButton`, `Mods`, `Key`) экспортируются из `tcbase`.

Viewport-bound event classes (`MouseButtonEvent`, `MouseMoveEvent`,
`ScrollEvent`, `KeyEvent`) are imported from `termin.input` in Python. Their
native registration lives in `termin-display` because these event objects carry
`TcViewport` handles and moving that binding into `termin-input` would create a
C++ dependency cycle.

## Input device registry

`termin-input` owns the common device identity layer:

- `termin::input::InputDeviceId` is represented by a stable string such as `gamepad0` or `xr`.
- `InputDeviceKind` currently distinguishes `gamepad` and `xr_rig`.
- `InputDeviceRegistry` maps a device id to an opaque backend-owned state pointer.

The registry intentionally does not define semantic actions such as `move` or
`select`.

`termin::xr::XrInput` is a typed state view for XR rigs. It is still a physical
input API: components read hands, thumbsticks, and poses from
`XrInput::get_state("xr")`; the OpenXR runtime only writes those values into the
shared state after `xrSyncActions`.

XR coordinate alignment is not part of `XrInput`. OpenXR reference-space axes
are converted by the OpenXR runner into Termin's engine axes, and
`XrOriginComponent` owns any authored alignment policy such as matching the
initial HMD yaw to the scene's `+Y` forward direction.
