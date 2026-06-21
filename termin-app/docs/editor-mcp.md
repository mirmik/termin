# Editor MCP diagnostics

The editor can expose a local MCP-compatible JSON-RPC endpoint for live
diagnostics. It is disabled by default because it can execute arbitrary Python
inside the running editor process.

## Enable

The server can be enabled in `Settings` with
`Enable local editor MCP server on startup`. The setting is used only when the
environment variable below is not defined.

To override the setting for one launch, start the editor with:

```bash
TERMIN_EDITOR_MCP=1 ./run-termin.sh
```

Use `TERMIN_EDITOR_MCP=0` to force-disable the server even when the editor
setting is enabled.

By default the server listens on `127.0.0.1:8765` and writes a session file to:

```text
/tmp/termin-editor-mcp.json
```

The session file contains the endpoint URL and a generated bearer token. It is
written with `0600` permissions.

Optional settings:

- `TERMIN_EDITOR_MCP_HOST`: bind host, default `127.0.0.1`.
- `TERMIN_EDITOR_MCP_PORT`: bind port, default `8765`. Use `0` for an OS-picked port.
- `TERMIN_EDITOR_MCP_TOKEN`: fixed bearer token. If omitted, a random token is generated.
- `TERMIN_EDITOR_MCP_SESSION_FILE`: session file path.

## CLI client

The repository includes a small local client:

```bash
scripts/termin-editor-mcp tools-list
scripts/termin-editor-mcp exec 'print(project_path)'
scripts/termin-editor-mcp exec-file /tmp/probe_editor.py
scripts/termin-editor-mcp screenshot --path /tmp/editor.png
scripts/termin-editor-mcp framegraph
```

On Windows PowerShell use the wrapper:

```powershell
./scripts/termin-editor-mcp.ps1 tools-list
./scripts/termin-editor-mcp.ps1 exec 'print(project_path)'
./scripts/termin-editor-mcp.ps1 exec-file C:\tmp\probe_editor.py
./scripts/termin-editor-mcp.ps1 screenshot --path C:\tmp\editor.png
./scripts/termin-editor-mcp.ps1 framegraph
```

The Python namespace contains:

- `editor`: the live `EditorWindowTcgui`.
- `scene`: the current editor scene.
- `scene_name` / `editor_scene_name`: current editor scene name.
- `current_scene` / `current_scene_name`: aliases for the current editor scene.
- `scene_manager`: the engine scene manager.
- `selected` / `selected_entity`: currently selected editor entity or `None`.
- `framegraph_debugger`: headless framegraph debugger inspection service.
- `project_path`: current project path or `None`.
- `rm` / `resource_manager`: `ResourceManager.instance()`.
- `Vec3`, `Vec4`, `Quat`, `Pose3`, `GeneralPose3`, `GeneralTransform3`:
  common geometry and transform types for scene-control scripts.
- `request_render_update()` / `refresh_editor()`: request an editor viewport
  redraw after scripts mutate scene state.
- `termin`: the `termin` package.

Scripts are queued from the MCP server thread and executed by the editor loop on
the main editor thread.

## Tools

`execute_python_script` executes Python inside the editor namespace. It is meant
for diagnostics and automation while the editor is running.

`capture_editor_screenshot` captures the editor viewport FBO as a PNG file. It
accepts:

- `path`: optional output path. Defaults to `/tmp/termin-editor-screenshots/`.
- `include_image`: when true, returns the PNG as MCP image content.
- `timeout`: seconds to wait for the editor thread to complete the capture.

`inspect_framegraph` returns a JSON snapshot from the headless framegraph
debugger service. It does not require the Framegraph Debugger dialog to be open
and is intended for automation/debugging. It accepts:

- `target_index`: optional target index from a previous snapshot.
- `include_pass_json`: include serialized pass data where available.
- `include_debugger_pass`: include the debugger pass in pass and schedule lists.
- `timeout`: seconds to wait for the editor thread to inspect the framegraph.
