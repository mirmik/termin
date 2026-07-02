# termin-csharp

`termin-csharp` contains C# bindings/runtime packaging for Termin native
libraries.

Related documents:

- [Examples README](../examples/README.md)
- [Build system](../../docs/build-system.md)
- [2D plot customization](tcplot-customization.md)
- [3D plot customization](tcplot-3d-customization.md)

## Main Areas

- Native bridge project in `Termin.Native/`.
- Test project in `Termin.Test/`.
- CMake build integration in `CMakeLists.txt`.
- Examples in `examples/`.

## Public API

C# project: `Termin.Native`.

The SDK build path is handled by `build-sdk-csharp.sh` / `build-sdk-csharp.ps1`. For WPF plot consumers such as Alliance, use the plot-only D3D11 profile:

```powershell
.\build-sdk-csharp.ps1 --plot-d3d11 --no-sdl --no-vulkan --no-opengl
```

That profile generates only the tcplot C# bridge plus `Termin.Wpf`, copies the minimal native runtime (`termin.dll`, `tcplot.dll`, `termin_base.dll`, `termin_mesh.dll`, `termin_graphics*.dll`), and packages only D3D11 shader artifacts required by plots. The default `full` profile keeps the broader scene/render/component bindings for development.
`Termin.Wpf` is Windows-only and multitargets `netcoreapp3.1` plus `net8.0-windows` through the WindowsDesktop SDK. The Windows SDK drop writes framework-specific managed assemblies under `sdk/csharp/lib/<tfm>/`; flat `sdk/csharp/lib/*.dll` copies are kept for legacy consumers and use the `netcoreapp3.1` WPF assembly. The Linux `build-sdk-csharp.sh` stage builds and packages `Termin.Native` plus Linux native `.so` runtime artifacts, but intentionally does not build `Termin.Wpf`.

Plot customization docs are source-of-truth here and are copied into consumer
SDK drops by `VdegNexus/TerminSdk/update-sdk.ps1`.
