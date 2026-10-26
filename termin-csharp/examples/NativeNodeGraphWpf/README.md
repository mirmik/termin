# Native nodegraph binding sample

This .NET 8 WPF sample embeds the complete native nodegraph document through
`NativeDocumentHost`. Node layout, selection, pan/zoom, connections and typed
parameter editors run in native code. C# receives copied parameter values and
stable node/parameter IDs. There is no SignalCore adapter or calculation engine.

The neutral `../../fixtures/pws.json` fixture uses the 24 node IDs and 31
connections from `SignalCore.Graphs.PwsRecipe`. All outputs allow fan-out and all
inputs accept one connection. The `enabled` and `shape` parameters are explicitly
marked as sample-only metadata; they exercise boolean and enum editor bindings.
They do not define computation semantics.

From a checkout, build the Graphics SDK, then run:

```powershell
task build:graphics -- --no-sdl --no-vulkan --no-opengl
dotnet run --project termin-csharp/examples/NativeNodeGraphWpf -p:TerminSdkRoot=C:\TerminGraphicsSdk
```

`TerminSdkRoot` must refer to a built, installed SDK. The sample copies both
managed assemblies, the native runtime closure and SDK resources from that root.
It can consume a relocated SDK without a neighboring application checkout.
Without `TerminSdkRoot`, it references the source binding projects instead.

Left drag selects/moves nodes, middle drag pans, wheel zooms, and right click
emits a managed context event. Fit graph shows all connections; zoom in to edit
the native parameter widgets. Русский/English changes presentation labels while
keeping endpoint IDs and edited parameter values. Technical event logs are in
English on stdout.

Language changes use copied typed snapshots through `GetSnapshot()` / `Replace()`.
Parameter types and exact Int64/double values survive presentation changes.

Pass `--smoke` after `--` for the automatic render/lifecycle check:

```powershell
dotnet run --project termin-csharp/examples/NativeNodeGraphWpf -p:TerminSdkRoot=C:\TerminGraphicsSdk -- --smoke
```

The smoke checks fixture dimensions, a native header drag, native keyboard/text
editing with a copied UTF-8 parameter callback after GC, rendered frames, resize,
repeated RU/EN changes preserving `Number(2.0)` and `Integer(9007199254740993)`,
language rebuild, hide/show and renderer detach/attach. Clipboard, interactive
pan/zoom and per-monitor DPI changes also require the interactive Windows/D3D11
acceptance pass.
