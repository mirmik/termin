---
name: termin-editor-mcp
description: Use when Codex should interact with a running Termin editor through the local MCP helper, execute Python in the editor process, inspect or manipulate the live scene, capture editor screenshots, or inspect framegraph debugger state via scripts/termin-editor-mcp.
---

# Termin Editor MCP

Use the repository helper from the repository root to talk to a running Termin
editor MCP endpoint. On Linux/macOS use `scripts/termin-editor-mcp`; on Windows
PowerShell use `./scripts/termin-editor-mcp.ps1`. Prefer this helper over raw
HTTP calls; it reads the session file and handles JSON-RPC details.

## Prerequisites

- Start the editor with MCP enabled: `TERMIN_EDITOR_MCP=1 ./sdk/bin/termin_editor`
  or enable the editor setting when the environment variable is not set.
- The helper reads `/tmp/termin-editor-mcp.json` by default. On Windows, the
  PowerShell wrapper also checks `%TEMP%\termin-editor-mcp.json` when `--session`
  was not passed explicitly.
- `./sdk/bin/termin_editor` without a project argument opens the last launched
  project.

## Commands

```bash
scripts/termin-editor-mcp tools-list
scripts/termin-editor-mcp exec 'print(scene, selected)'
scripts/termin-editor-mcp exec-file /tmp/script.py
scripts/termin-editor-mcp screenshot --path /tmp/editor.png
scripts/termin-editor-mcp framegraph --include-pass-json --include-debugger-pass
scripts/termin-editor-mcp framegraph-capture --target-index 0 --resource OUTPUT --path /tmp/output.png
```

```powershell
./scripts/termin-editor-mcp.ps1 tools-list
./scripts/termin-editor-mcp.ps1 exec 'print(scene, selected)'
./scripts/termin-editor-mcp.ps1 exec-file C:\tmp\script.py
./scripts/termin-editor-mcp.ps1 screenshot --path C:\tmp\editor.png
./scripts/termin-editor-mcp.ps1 framegraph --include-pass-json --include-debugger-pass
./scripts/termin-editor-mcp.ps1 framegraph-capture --target-index 0 --resource OUTPUT --path C:\tmp\output.png
```

## Editor Namespace

Python scripts run inside the editor namespace. Useful names include:

- `scene`: currently open editor scene.
- `selected` / `selected_entity`: currently selected entity.
- `framegraph_debugger`: headless framegraph debugger service.

After mutating scene state, request a viewport/render update through the editor
helpers available in the namespace when appropriate.

## Framegraph Notes

Current MCP framegraph support can list targets, passes, resources, schedule,
duplicate pass names, internal symbols, and serialized pass data. It can also
capture a resource image through `framegraph-capture`, which connects the same
FrameDebugger resource-capture pass used by the UI and waits for a render frame
before exporting PNG.

Remaining gaps: pass/internal-symbol capture still uses duplicate-prone
`pass_name` in the debugger model, and full UI parity for every preview mode
still needs explicit MCP surface.
