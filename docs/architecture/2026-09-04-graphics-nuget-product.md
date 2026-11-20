# Termin Graphics NuGet product contract

The initial contract was accepted on 2026-09-04. The 0.5.4 distribution adds
.NET Standard 2.1 bindings and a .NET Core 3.1 WPF adapter. The preceding
release is available on NuGet.org. [Termin.Graphics 0.5.3](https://www.nuget.org/packages/Termin.Graphics/0.5.3)
and [Termin.Graphics.Wpf 0.5.3](https://www.nuget.org/packages/Termin.Graphics.Wpf/0.5.3).

## Decision

Termin Graphics is published to .NET consumers as two coupled packages:

- `Termin.Graphics` owns `Termin.Native.dll`, the Windows x64 native DLL
  closure, precompiled D3D11 shader resources, and the transitive MSBuild target
  that delivers those resources under `share/termin` in both build and
  publish output;
- `Termin.Graphics.Wpf` owns `Termin.Wpf.dll` and has an exact-version
  dependency on `Termin.Graphics`.

Both packages use the repository-wide public version from
`build-system/version.toml`. The supported combinations are

- Base bindings at `lib/netstandard2.1/Termin.Native.dll` and resource copying
  through `buildTransitive/netstandard2.1/Termin.Graphics.targets`.
- WPF bindings at `lib/netcoreapp3.1/Termin.Wpf.dll` and
  `lib/net8.0-windows7.0/Termin.Wpf.dll`. Each asset group depends on the
  exact same base package version.
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
IDs, TFM/RID, input paths, minimum native closure, forbidden broad-profile
libraries, required shader artifacts, and release licenses. The product builder
rejects inputs that violate that contract and emits an exact manifest containing
the SHA-256 of every archive and archive member.

Every archive part must have a content type in `[Content_Types].xml`, including
explicit overrides for extensionless release-license files. Candidate validation
rejects missing declarations before upload. Both packages pair their file license
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
   external temporary feed, and compiles a `netstandard2.1` library referencing
   only the base package. For both WPF target frameworks it verifies managed
   assemblies, native libraries, and resources in build and publish output,
   then runs the D3D11 chart and node graph from each publish directory.
   The machine needs the corresponding targeting packs and x64 Windows Desktop
   runtimes. The gate preserves its report, logs,
   and exact candidate manifest under `build/graphics-nuget-consumer-gate`.
3. `task publish:graphics:nuget` validates the candidate and its passed consumer
   evidence, checks both remote versions, and prints the exact dry-run plan.
   `--upload --confirm-version VERSION` enables the irreversible base-then-WPF
   upload. Publication is bound to the exact package hashes in the passed gate;
   it never rebuilds or substitutes a different candidate.

NuGet.org mutation remains a separate release gate after stages 1 and 2 pass.
The publisher preflights both remote versions before the first mutation. It
downloads every existing or newly visible package and compares every original
archive member with the gated manifest; only NuGet's `.signature.p7s`
repository-signature member may be added. This makes a rerun safe after a
partial base-package publication without relying on `skip duplicate`.

## Publication operations

Run the dry plan on the same machine and workspace that retain the passed
candidate and `build/graphics-nuget-consumer-gate` evidence:

```powershell
task publish:graphics:nuget
```

For upload, create a short-lived NuGet.org API key scoped to push new versions
of only `Termin.Graphics` and `Termin.Graphics.Wpf`. The release owner supplies
it through the process environment; it is never accepted as a command-line
argument or written to evidence:

```powershell
$env:NUGET_API_KEY = '<scoped secret>'
task publish:graphics:nuget -- --upload --confirm-version 0.5.4
Remove-Item Env:NUGET_API_KEY
```

Keep the key in the release owner's secret store. Do not commit it, paste it
into task arguments, or expose it to pull-request workflows. A CI migration
should prefer NuGet.org Trusted Publishing; if a static key is temporarily
needed, place it in a protected release environment available only to trusted
tag/ref workflows.

Uploads are non-transactional. If the base package succeeds and the WPF upload
does not, retain the candidate and evidence unchanged and rerun the same
command. The publisher proves the existing base content and continues with WPF.
Any remote member mismatch stops publication for manual reconciliation.

The publisher polls for package availability for up to 60 attempts with a
15-second interval. NuGet.org indexing can exceed five minutes even after a
successful push. If visibility still times out, retain the candidate and evidence
unchanged and rerun after indexing completes; do not rebuild a replacement.

After both pushes are visible, restore both packages from NuGet.org in a clean
external consumer and repeat the WPF/D3D11 smoke before closing the release.
