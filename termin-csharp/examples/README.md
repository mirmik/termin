# Termin C# examples

This directory contains C# sample applications for the `Termin.Native` SDK.

Projects:

- `NativeNodeGraphWpf` - complete native nodegraph document, safe managed graph
  values/events and native parameter editors through a reusable WPF document host.
  Includes a neutral PWS-shaped 24-node/31-edge fixture and installed SDK mode.
- `PlotDemoApp` - WPF/D3D11 D3DImage hosts for 2D, multi-panel 2D, and 3D plot demos.
  Its retained heatmap example combines a 180×240 uniform scalar grid, transparent
  missing cells, a line overlay, palette/reversal/range/interpolation controls, a GPU-rendered
  color scale, and cell-value inspection under the pointer.
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

Open the heatmap directly (or select it from the PlotDemoApp menu):

```powershell
dotnet run --project termin-csharp/examples/PlotDemoApp/PlotDemoApp.csproj -- --heatmap2d
```

The data array is row-major, with row zero at the lower Y edge and column zero
at the lower X edge. Bounds describe the outer edges of all cells. Middle-drag
pans, the wheel zooms, Ctrl+wheel zooms X only, and Fit restores the data bounds.
The color scale is a separate retained scalar item using the same palette and
effective scalar range as the field; it is not a WPF imitation of the palette.
The Bilinear checkbox enables smooth interpolation between cell centers before
the palette is applied; Nearest remains the default. Missing neighbors contribute
no scalar value and reduce coverage, giving transparent edges around NaN holes.
Pointer inspection always reports the original cell value in either mode.

Run the D3D11 presentation check with:

```powershell
$env:TERMIN_PLOT_DEMO_CAPTURE_DIR = "$PWD/build/heatmap-captures"
dotnet run --project termin-csharp/examples/PlotDemoApp/PlotDemoApp.csproj -- --smoke-heatmap2d
```

The smoke checks actual WPF pixels for grid orientation, grayscale colors,
transparent NaN cells, palette reversal, data replacement, resize/fit,
and legend label ink alignment with its swatch and containment in the legend
background before and after resize. Legend checks locate the scene parts and
measure the captured text pixels; they do not trust declared text layout bounds.
Optional captures include `heatmap-legend-initial.png` and
`heatmap-legend-resized.png`. It also checks
automatic scalar range, pan/zoom, and a fixed color-range change without replacing
the field data. Additional stages verify an intermediate bilinear pixel and
restoration of nearest sampling without replacing the matrix. The dark-gradient
regression samples a 0–16 sRGB-byte ramp with default 4x MSAA, requires at least
15 distinct levels and at most one byte of error per channel, then repeats after
resize. This detects premature quantization into an 8-bit linear intermediate.
Optional captures include `heatmap-dark-gradient.png` and
`heatmap-dark-gradient-resized.png`. It writes
`HEATMAP_SMOKE_OK` and closes on success;
failures return a nonzero process exit code. Captures are optional.

`-m:1` keeps the solution build serial. The individual projects build normally,
but the parallel solution build can fail on Windows without useful diagnostics
while WPF temporary projects are being generated.

Build the native/C# SDK for the supported WPF scene profile and run its
deterministic presentation smoke:

```powershell
task build -- --no-sdl --no-vulkan --no-opengl
dotnet run --project termin-csharp/examples/SceneApp/SceneApp.csproj -- --smoke
```

`Tgfx2D3D11ImageHost.BindDisplay` borrows a generation handle. Dispose or
unbind the host first, then dispose `D3D11OffscreenDisplay`, and only then release
the `Tgfx2Host` lease. Mouse, wheel, keyboard, and text input are converted
from WPF DIPs to top-left-origin display pixels and dispatched through the
typed display API.
