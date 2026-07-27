# Termin C# examples

This directory contains C# sample applications for the `Termin.Native` SDK.

Projects:

- `PlotDemoApp` - WPF/D3D11 D3DImage hosts for 2D, multi-panel 2D, and 3D plot demos.
- `SceneApp` - WPF scene editor/viewer using a display-owned D3D11 offscreen
  texture and the shared D3D11-to-D3DImage presenter. It has no SDL, Vulkan,
  OpenGL, raw framebuffer, or raw display-pointer dependency.

Build from the repository root:

```powershell
dotnet build termin-csharp/Termin.CSharp.sln -m:1
```

`-m:1` keeps the solution build serial. The individual projects build normally,
but the parallel solution build can fail on Windows without useful diagnostics
while WPF temporary projects are being generated.

Build the native/C# SDK for the supported WPF scene profile and run its
deterministic presentation smoke:

```powershell
.\build-sdk.ps1 --no-sdl --no-vulkan --no-opengl
dotnet run --project termin-csharp/examples/SceneApp/SceneApp.csproj -- --smoke
```

`Tgfx2D3D11ImageHost.BindDisplay` borrows a generation handle. Dispose or
unbind the host first, then dispose `D3D11OffscreenDisplay`, and only then release
the `Tgfx2Host` lease. Mouse, wheel, keyboard, and text input are converted
from WPF DIPs to top-left-origin display pixels and dispatched through the
typed display API.
