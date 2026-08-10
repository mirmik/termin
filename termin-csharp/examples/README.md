# Termin C# examples

This directory contains C# sample applications for the `Termin.Native` SDK.

Projects:

- `PlotDemoApp` - WPF/D3D11 D3DImage hosts for 2D, multi-panel 2D, and 3D plot demos.
- `RetainedChartComposition` - platform-neutral construction and customization
  of native `RetainedChart2D` through its thin C# `Chart2D` facade. It replaces
  the standard plot background without adding a layout forwarding method.
- `RetainedChartWpfExample` - renders that retained scene through the generic
  D3D11 WPF scene host, renders chart-owned semantic-series legend entries,
  customizes native chart parts from C#, and anchors a real WPF button to a
  retained scene item. The button callback stays in C#; middle-drag and wheel
  exercise the native chart interaction controller.
- `AllianceStreamingChartsExample` - uses two native `MultiChart2D` instances
  for an Alliance-scale 2x15 streaming layout: 30 independently scaled panels,
  60 native series, two public retained scenes and two offscreen textures.
  `MultiChart2DGroup` coordinates shared X, panel geometry and virtual scroll;
  wheel input in either column and the external WPF scrollbar move both.
  Pause/reset/follow controls remain real WPF portals with C# callbacks. The
  hosts render on demand at the data/interaction cadence and use 2x MSAA;
  styled line appends update only the affected GPU tail. The
  status line separates managed append/shared-X cost from native scene paint,
  draw-list freeze, CPU command submission, D3DImage present and portal update
  averages. Command submission is intentionally labelled as CPU time rather
  than a GPU timestamp.
- `RetainedChart3DWpfExample` - retained surface/scatter items with stable
  handles, transactional data mutation, an independently replaceable grid,
  axis-scale-aware camera fit, on-demand rendering, MSAA, and WPF portals
  whose callbacks stay in C#.
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

`RetainedChartComposition` validates composition and native data ownership
without a window. `RetainedChartWpfExample` is the corresponding rendered
vertical slice for Windows/D3D11:

```powershell
dotnet run --project termin-csharp/examples/RetainedChartWpfExample/RetainedChartWpfExample.csproj
```

Run the Alliance-style multi-panel streaming example with:

```powershell
dotnet run --project termin-csharp/examples/AllianceStreamingChartsExample/AllianceStreamingChartsExample.csproj
```

Run the retained 3D vertical slice with:

```powershell
dotnet run --project termin-csharp/examples/RetainedChart3DWpfExample/RetainedChart3DWpfExample.csproj
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
