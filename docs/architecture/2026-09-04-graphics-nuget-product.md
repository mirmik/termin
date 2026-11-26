# Termin Graphics NuGet product contract

The initial contract was accepted on 2026-09-04. Releases through 0.5.5 use
separate packages for the base bindings and the WPF adapter. Starting with
0.5.6, both are delivered in `Termin.Graphics`.

## Decision

The single `Termin.Graphics` package uses the repository-wide public version
from `build-system/version.toml`. It includes the following assets.

- Base bindings at `lib/netstandard2.1/Termin.Native.dll`.
- WPF bindings at `wpf/netcoreapp3.1/Termin.Wpf.dll` and
  `wpf/net8.0-windows7.0/Termin.Wpf.dll`. The transitive MSBuild target adds
  the reference when `UseWPF=true`, selecting the .NET 8 assembly for .NET 8
  and later and the .NET Core 3.1 assembly for earlier compatible frameworks.
- Precompiled D3D11 shader resources copied to `share/termin` in build and
  publish output by `buildTransitive/netstandard2.1/Termin.Graphics.targets`.
- Windows x64 D3D11 native runtime for all managed targets, built with
  the `plot-d3d11` C# binding profile.

The `windows7.0` TFM suffix identifies the Windows API contract. Framework-
dependent applications need the matching x64 .NET runtime. WPF applications
use its Windows Desktop distribution. The native libraries use the dynamic
MSVC runtime and require the x64 Microsoft Visual C++ v14 Redistributable.

The existing `Termin.Native` managed assembly and namespace are retained. A
package projection does not require a source/API rename.

## Build boundary

NuGet packaging consumes only the installed `sdk-graphics/csharp` projection
created by the canonical root build. It must not pack generated files directly
from `termin-csharp/Termin.Native/runtimes`, `Generated`, or `share`.

The product lock in `build-system/graphics-nuget-lock.json` declares package
ID, TFM/RID, input paths, minimum native closure, forbidden broad-profile
libraries, required shader artifacts, and release licenses. The product builder
rejects inputs that violate that contract and emits an exact manifest containing
the SHA-256 of every archive and archive member.

Graphics and Engine share an MSBuild target that refreshes package files when
the resolved package or output path changes. The target tracks the last copy
in the project's intermediate directory. This keeps incremental build and
publish output current even when two package versions contain files with the
same size and reproducible ZIP timestamp.

Every archive part must have a content type in `[Content_Types].xml`, including
explicit overrides for extensionless release-license files. Candidate validation
rejects missing declarations before upload. The package pairs its file license
with `<licenseUrl>https://aka.ms/deprecateLicenseUrl</licenseUrl>` for older NuGet
clients; candidate validation rejects a missing or different compatibility URL.
The publisher identifies the NuGet.org
push protocol with `X-NuGet-Protocol-Version: 4.1.0`, reports server rejection
details with API keys redacted, and fails immediately on HTTP 400/401/403.

The plot runtime closure is derived from the native binaries rather than only
the direct C# binding targets. It therefore includes the inspect, materials,
render-core, and graphics-binding-policy libraries pulled in transitively by
the retained chart stack. These are part of the focused product; engine,
scene, display, render-pipeline, and component libraries remain forbidden.

## Delivery stages

1. `task package:graphics:nuget` builds the canonical Windows graphics SDK with
   SDL, Vulkan, and OpenGL disabled, then creates an atomic local candidate.
2. `task test:graphics:nuget` rebuilds that candidate, copies it into an
   external temporary feed, and publishes libraries for `netstandard2.1`
   and `net8.0-windows7.0` without WPF, checking that they receive only
   the base assembly. For both WPF target frameworks it verifies managed
   assemblies, native libraries, and resources in build and publish output,
   then runs the D3D11 chart and node graph from each publish directory.
   The temporary consumer workspace selects a stable .NET SDK starting at
   8.0.100 with the `major` roll-forward policy and records the selected
   version in `dotnet-sdk.log`. Offline restore requires the targeting and
   apphost packs expected by that SDK. Running the smokes requires the x64
   Windows Desktop runtimes for .NET Core 3.1 and .NET 8.
   The gate preserves its report, logs,
   and exact candidate manifest under `build/graphics-nuget-consumer-gate`.
3. `task publish:graphics:nuget` validates the candidate and its passed consumer
   evidence, checks the remote package version, and prints the exact dry-run plan.
   `--upload --confirm-version VERSION` enables the upload. Publication is
   bound to the exact package hash in the passed gate;
   it never rebuilds or substitutes a different candidate.

NuGet.org mutation remains a separate release gate after stages 1 and 2 pass.
The publisher downloads an existing or newly visible package and compares
every original archive member with the gated manifest. NuGet may add
its `.signature.p7s` repository signature. Reruns verify an existing matching
package and skip the upload. Any remote member mismatch stops publication.

## Publication operations

Run the dry plan on the same machine and workspace that retain the passed
candidate and `build/graphics-nuget-consumer-gate` evidence:

```powershell
task publish:graphics:nuget
```

For upload, create a short-lived NuGet.org API key scoped to push new versions
of `Termin.Graphics`. The release owner supplies
it through the process environment; it is never accepted as a command-line
argument or written to evidence:

```powershell
$env:NUGET_API_KEY = '<scoped secret>'
task publish:graphics:nuget -- --upload --confirm-version 0.5.6
Remove-Item Env:NUGET_API_KEY
```

Keep the key in the release owner's secret store. Do not commit it, paste it
into task arguments, or expose it to pull-request workflows. A CI migration
should prefer NuGet.org Trusted Publishing; if a static key is temporarily
needed, place it in a protected release environment available only to trusted
tag/ref workflows.

The publisher polls for package availability for up to 60 attempts with a
15-second interval. NuGet.org indexing can exceed five minutes even after a
successful push. If visibility still times out, retain the candidate and evidence
unchanged and rerun after indexing completes; do not rebuild a replacement.

After the push is visible, restore the package from NuGet.org in a clean
external consumer and repeat the WPF/D3D11 smoke before closing the release.
