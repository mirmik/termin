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

By default the server listens on an OS-picked loopback port. It writes a
checkout-scoped session file in the system temporary directory. The path is
derived from the canonical SDK root, so editors built by different Termin
checkouts do not overwrite each other's discovery state. Print the path for
the current checkout with:

```bash
scripts/termin-editor-mcp session-path
```

The session file contains the endpoint URL and a generated bearer token. It is
written with `0600` permissions.

Optional settings:

- `TERMIN_EDITOR_MCP_HOST`: bind host, default `127.0.0.1`.
- `TERMIN_EDITOR_MCP_PORT`: bind port, default `0` for an OS-picked port.
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

## Standard MCP broker

`scripts/termin-editor-mcp serve` is a standard stdio MCP server for Codex,
MCP Inspector, and other local MCP clients. The client launches the broker as a
child process. The broker performs the MCP lifecycle over stdin/stdout and
serves the editor tool schemas locally. It forwards `tools/call` to the
authenticated loopback endpoint inside the editor.

Without `--session`, the broker computes the same checkout-scoped session path
as a user-opened editor from that checkout. This stable default is reserved for
the user-owned editor. Agent-owned editor processes must use explicit unique
session files.

The MCP client may start before the editor. Tool discovery succeeds without a
session file, while calls return a structured `Termin Editor is unavailable`
error until the editor starts. The broker rereads the session file before every
forwarded call, so stopping or restarting the editor on a new OS-picked port
does not require restarting the broker or MCP client. A clean editor shutdown
removes the session file. If a crash leaves stale endpoint data behind, calls
report the same unavailable error until the next editor atomically publishes
its new endpoint and token.

For Codex, add a project-scoped `.codex/config.toml` in a trusted checkout:

```toml
[mcp_servers.termin_editor]
command = "/absolute/path/to/termin/scripts/termin-editor-mcp"
args = ["serve"]
startup_timeout_sec = 10
tool_timeout_sec = 60
default_tools_approval_mode = "prompt"
```

On Windows, point `command` at PowerShell and pass the repository wrapper:

```toml
[mcp_servers.termin_editor]
command = "pwsh"
args = [
  "-File",
  "C:\\absolute\\path\\to\\termin\\scripts\\termin-editor-mcp.ps1",
  "serve",
]
startup_timeout_sec = 10
tool_timeout_sec = 60
default_tools_approval_mode = "prompt"
```

Restart the Codex host after changing its MCP configuration. In the Codex TUI,
use `/mcp` to inspect the active server. The broker logs diagnostics only to
stderr; stdout is reserved for newline-delimited MCP JSON-RPC messages.

When an agent launches another editor, give it an explicit unique session file
and keep using the default broker for the user-owned editor:

```bash
agent_mcp_dir="$(mktemp -d /tmp/termin-editor-agent.XXXXXX)"
TERMIN_EDITOR_MCP=1 \
TERMIN_EDITOR_MCP_PORT=0 \
TERMIN_EDITOR_MCP_SESSION_FILE="$agent_mcp_dir/session.json" \
./sdk/bin/termin_editor /absolute/path/to/Project.terminproj

scripts/termin-editor-mcp \
  --session "$agent_mcp_dir/session.json" \
  exec 'print(project_path)'
```

```powershell
$AgentMcpDir = Join-Path ([System.IO.Path]::GetTempPath()) `
  ("termin-editor-agent-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $AgentMcpDir | Out-Null
$env:TERMIN_EDITOR_MCP = "1"
$env:TERMIN_EDITOR_MCP_PORT = "0"
$env:TERMIN_EDITOR_MCP_SESSION_FILE = Join-Path $AgentMcpDir "session.json"
./sdk/bin/termin_editor.exe C:\\absolute\\path\\to\\Project.terminproj
```

The generated bearer token and endpoint stay in the permission-restricted
session file and are not exposed in MCP client configuration. An agent must
only stop and clean up editor processes and temporary session directories that
it created itself.

The Python namespace contains:

- `editor`: the live `EditorWindowTcgui`.
- `scene`: the current editor scene.
- `scene_name` / `editor_scene_name`: current editor scene name.
- `current_scene` / `current_scene_name`: aliases for the current editor scene.
- `scene_manager`: the engine scene manager.
- `selected` / `selected_entity`: currently selected editor entity or `None`.
- `scene_edit`: public undo-aware local transform editing service. Use
  `scene_edit.set_selected_local_transform(position=(1, 2, 3))` to move the
  selection, or `scene_edit.set_entity_local_transform(entity, scale=Vec3(2, 2, 2))`
  for an explicit entity. `position` and `scale` accept `Vec3` or exactly three
  finite numeric values; `rotation` accepts `Quat` or four finite `x, y, z, w`
  values. All values are local-space, omitted fields are preserved, and
  `merge=True` combines successive edits to the same entity into one Undo entry.
  Each call returns the resulting local state and requests a viewport refresh.
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

- `execute_python_script` executes Python inside the editor namespace for
  diagnostics and automation.
- `capture_editor_screenshot` captures the editor UI or viewport.
- `inspect_framegraph` returns the headless framegraph debugger snapshot.
- `capture_framegraph_resource` exports a selected framegraph resource.
- `capture_framegraph_pass_symbol` captures framebuffer state after an internal
  symbol draw; prefer stable pass and symbol indexes when names are duplicated.

The stdio broker advertises this contract even while the editor is offline.
Each call still requires a running editor registered through the configured
session file.

## Smoke Tests

The repository includes an editor-process smoke test for Python `.pymodule`
explicit reload:

```bash
scripts/smoke-python-module-hot-reload
```

The script creates a temporary project, starts `sdk/bin/termin_editor` with MCP
enabled, changes a Python module package file on disk, and verifies through MCP
that the live editor scene degrades to `UnknownComponent` on a failed explicit
reload and restores the Python component after a successful explicit reload.

On headless Linux the script uses `xvfb-run` automatically when no
`DISPLAY`/`WAYLAND_DISPLAY` is available. Install the `xvfb` package or run the
script in a graphical session. Use `--keep-temp` to keep the generated project
and editor log for debugging.

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
