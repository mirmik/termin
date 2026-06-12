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
```

The Python namespace contains:

- `editor`: the live `EditorWindowTcgui`.
- `scene`: the current editor scene.
- `scene_name` / `editor_scene_name`: current editor scene name.
- `current_scene` / `current_scene_name`: aliases for the current editor scene.
- `scene_manager`: the engine scene manager.
- `selected` / `selected_entity`: currently selected editor entity or `None`.
- `project_path`: current project path or `None`.
- `rm` / `resource_manager`: `ResourceManager.instance()`.
- `termin`: the `termin` package.

Scripts are queued from the MCP server thread and executed by the editor loop on
the main editor thread.
