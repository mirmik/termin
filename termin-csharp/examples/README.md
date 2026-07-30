# Termin C# examples

This directory contains C# sample applications for the `Termin.Native` SDK.

Projects:

- `PlotDemoApp` - WPF/D3D11 D3DImage hosts for 2D, multi-panel 2D, and 3D plot demos.
- `RetainedChartComposition` - platform-neutral construction and customization
  of a managed `Chart2D` backed by native retained items. It replaces the
  standard plot background without adding a native layout forwarding method.
- `SceneApp` - WPF scene editor/viewer using a display-owned D3D11 offscreen
  texture and the shared D3D11-to-D3DImage presenter. It has no SDL, Vulkan,
  OpenGL, raw framebuffer, or raw display-pointer dependency.

Build from the repository root:

```powershell
dotnet build termin-csharp/Termin.CSharp.sln -m:1
```

The retained composition example can consume an installed SDK by setting
`TerminSdkRoot`; pass the same SDK root at runtime so it can find the font:

```powershell
dotnet run --project termin-csharp/examples/RetainedChartComposition/RetainedChartComposition.csproj `
  -p:TerminSdkRoot=C:\TerminSdk -- C:\TerminSdk
```

Until the retained WPF host is introduced, this example validates composition
and native data ownership with the null backend. `PlotDemoApp` remains the
rendered transitional example.

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
