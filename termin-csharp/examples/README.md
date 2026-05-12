# Termin C# examples

This directory contains C# sample applications for the `Termin.Native` SDK.

Projects:

- `PlotDemoApp` - WPF/OpenTK hosts for 2D, multi-panel 2D, and 3D plot demos.
- `SceneApp` - small WPF scene editor/viewer sample.
- `Termin.WpfTest` - older WPF integration smoke test kept as a manual regression app.

Build from the repository root:

```powershell
dotnet build termin-csharp/Termin.CSharp.sln -m:1
```

`-m:1` keeps the solution build serial. The individual projects build normally,
but the parallel solution build can fail on Windows without useful diagnostics
while WPF temporary projects are being generated.
