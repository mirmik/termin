# Termin Graphics for .NET

Termin Graphics provides the focused C# bindings and native runtime used by
Termin's retained 2D/3D charts, native nodegraph and UI documents on Windows.

The native runtime uses D3D11 on Windows x64. The `Termin.Graphics` package
includes `netstandard2.1` bindings and WPF assemblies for `netcoreapp3.1`
and `net8.0-windows7.0`.

The native binaries use the dynamic Microsoft C++ runtime. Install the latest
[Microsoft Visual C++ v14 Redistributable for x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)
on the target machine. For a framework-dependent WPF application, install the
x64 Windows Desktop Runtime for the application's target framework.

Use the same package reference in WPF and non-WPF projects.

```xml
<PackageReference Include="Termin.Graphics" Version="{{TERMIN_VERSION}}" />
```

When the project sets `<UseWPF>true</UseWPF>`, the package selects the WPF
assembly for the target framework. When upgrading from `Termin.Graphics.Wpf`
0.5.5, replace the old reference with `Termin.Graphics`.

The package supplies the managed assemblies, the `win-x64` native dependency
closure, and the precompiled D3D11 shader resources. Applications do not need a
Termin SDK checkout at runtime.

`NativeNodeGraph` wraps the native authoring graph. `NativeNodeGraphView` embeds
its typed parameter widgets in `NativeUiDocument`; WPF uses the reusable
`NativeDocumentHost` with the same D3D11 `GpuHost` as charts. Graph execution and
application domain rules remain the application's responsibility.

The managed API currently keeps the established `Termin.Native` namespace and
assembly name. Package naming describes the public product and does not imply
an assembly or namespace rename.
