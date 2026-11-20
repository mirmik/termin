# Termin Graphics for .NET

Termin Graphics provides the focused C# bindings and native runtime used by
Termin's retained 2D/3D charts, native nodegraph and UI documents on Windows.

The native runtime uses D3D11 on Windows x64. The `Termin.Graphics` package
provides its managed bindings for `netstandard2.1`, so compatible non-WPF
hosts can reference it directly. `Termin.Graphics.Wpf` supplies separate WPF
assemblies for `netcoreapp3.1` and `net8.0-windows7.0`.

The native binaries use the dynamic Microsoft C++ runtime. Install the latest
[Microsoft Visual C++ v14 Redistributable for x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)
on the target machine. For a framework-dependent WPF application, install the
x64 Windows Desktop Runtime for the application's target framework.

Use the base runtime directly for non-WPF hosts:

```xml
<PackageReference Include="Termin.Graphics" Version="{{TERMIN_VERSION}}" />
```

WPF applications should reference the adapter package, which brings the exact
same version of the base runtime transitively:

```xml
<PackageReference Include="Termin.Graphics.Wpf" Version="{{TERMIN_VERSION}}" />
```

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
