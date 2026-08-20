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
TERMIN_EDITOR_MCP=1 task run --
```

Use `TERMIN_EDITOR_MCP=0` to force-disable the server even when the editor
setting is enabled.

By default the server listens on an OS-picked loopback port. Every editor writes
its own descriptor into an SDK-scoped registry in the system temporary
directory. The registry path is derived from the canonical SDK root, so editors
built by different Termin checkouts do not mix discovery state while multiple
editors from one SDK remain independently addressable. Print the registry path
and inspect its instances with:

```bash
scripts/termin-editor-mcp registry-path
scripts/termin-editor-mcp sessions
```

Each descriptor contains an instance id, process and project metadata, endpoint
URL, and a generated bearer token. It is written with `0600` permissions. The
`sessions` command deliberately omits bearer tokens.

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

The helper selects a registered user editor whose canonical `project_path`
contains the current working directory. Use `--project /path/to/project` when
calling it from elsewhere. If several live editors match the same project, the
helper reports their instance ids instead of choosing one arbitrarily; rerun it
with `--instance INSTANCE_ID` to select one.

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

Without `--session`, the broker discovers user-opened editors in the matching
SDK registry and selects by canonical project path. A sole registered editor is
also accepted as an unambiguous fallback. Agent-owned editor processes must use
explicit unique session files and are not published in the user registry.

The MCP client may start before the editor. Tool discovery succeeds without a
session file, while calls return a structured `Termin Editor is unavailable`
error until an applicable editor starts. The broker rescans descriptors before
every forwarded call, so stopping or restarting editors on new OS-picked ports
does not require restarting the broker or MCP client. A clean editor shutdown
removes only its owned descriptor. Stale descriptors left by crashed processes
are probed and ignored when one live match remains.

## Agent skill

The repository ships `.agents/skills/termin-editor-mcp` using the open Agent
Skills layout. Compatible agents discover the skill directly while working in
this checkout; no user-local copy or deployment manifest is required. The skill
documents editor launch, tool selection, session isolation, and CLI fallback
workflows.

The stdio broker also returns concise server-wide instructions during MCP
initialization, so MCP clients can use its tools even when they do not implement
Agent Skills discovery.

For Codex, add a project-scoped `.codex/config.toml` in a trusted checkout:

```toml
[mcp_servers.termin_editor]
command = "/absolute/path/to/termin/scripts/termin-editor-mcp"
args = ["serve"]
startup_timeout_sec = 10
tool_timeout_sec = 60
default_tools_approval_mode = "approve"
```

The broker uses its current working directory as the project selector. A
project config may make this explicit, which is useful when the MCP host does
not preserve the workspace working directory:

```toml
args = ["--project", "/absolute/path/to/project", "serve"]
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
default_tools_approval_mode = "approve"
```

Restart the Codex host after changing its MCP configuration. In the Codex TUI,
use `/mcp` to inspect the active server. `approve` intentionally trusts every
tool from this project-scoped editor server, including arbitrary Python
execution, so unattended agents do not pause for MCP approval. The broker logs
diagnostics only to stderr; stdout is reserved for newline-delimited MCP
JSON-RPC messages.

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
- `scene_name` / `editor_scene_name`: current project-relative editor scene identity
  (for example `Scenes/Main.scene`); this is not the short UI label.
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
- `request_editor_close()`: request a normal editor shutdown after an automated
  session.
- `termin`: the `termin` package.

Scripts are queued from the MCP server thread and executed by the editor loop on
the main editor thread.

### Safe scene and component traversal

Use the public scene/entity API and `Entity.tc_components` for generic
automation:

```python
for entity in scene.get_all_entities():
    for component in entity.tc_components:
        print(
            entity.name,
            component.type_name,
            component.enabled,
            component.serialize_data(),
        )
```

`tc_components` returns non-owning `TcComponentRef` values for both Python and
native components. It therefore keeps working when a project module contributes
a native component with no concrete Python wrapper class. Do not retain these
references after their entity is removed, the scene is destroyed, or a module
reload replaces the component.

`Entity.components` is a typed-wrapper convenience API, not a generic traversal
API. It may raise when any attached native component has no Python binding.
Use `TcComponentRef.to_python()` only when a typed wrapper is optional; it
returns `None` when one is unavailable.

For inspected fields, `get_field(name)` is the optional lookup and returns
`None` when the field cannot be read. Automation that requires a field should
use `require_field(name)` so a missing or unreadable field is logged and fails
the MCP script explicitly:

```python
mesh_components = []
for entity in scene.get_all_entities():
    for component in entity.tc_components:
        if component.type_name == "MeshRenderer":
            mesh_components.append(
                (entity.uuid, component.require_field("mesh"))
            )
print(mesh_components)
```

Use `scene.get_root_entities()` when only hierarchy roots are needed, then walk
each entity's public `children()` result. Scene mutations made directly
through these objects are immediate; use `scene_edit` for undo-aware transform
changes and call `request_render_update()` after other visual mutations.

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
registry or explicit session file.

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

On headless Linux the script uses the canonical
`scripts/termin-editor-virtual-display` wrapper automatically when no
`DISPLAY`/`WAYLAND_DISPLAY` is available. Install Xvfb, `xauth`, and
`mesa-utils` (`glxinfo`), or run the script in a graphical session. Use
`--keep-temp` to keep the generated project and editor log for debugging.

## Virtual-display editor E2E

Use the virtual-display wrapper when automation must exercise the real SDL
window lifecycle and presentation path on a Linux machine without a physical
display:

```bash
scripts/termin-editor-virtual-display /path/to/Project.terminproj
```

The wrapper always creates a unique Xvfb display, forces Mesa llvmpipe OpenGL,
checks OpenGL 4.6 and GLSL 4.60, verifies the SDK shader compiler, enables the
editor MCP endpoint on port `0`, and prints the unique session descriptor path.
While the editor is running, another terminal can use that path:

```bash
scripts/termin-editor-mcp --session /tmp/termin-editor-virtual-display-XXXX/session.json initialize
scripts/termin-editor-mcp --session /tmp/termin-editor-virtual-display-XXXX/session.json tools-list
scripts/termin-editor-mcp --session /tmp/termin-editor-virtual-display-XXXX/session.json exec \
  "print(project_path, scene)"
scripts/termin-editor-mcp --session /tmp/termin-editor-virtual-display-XXXX/session.json exec \
  "request_editor_close()"
```

Pass `--session-file /explicit/path/session.json` when another process needs a
stable descriptor path. The wrapper removes its generated runtime directory
after editor shutdown; `--keep-runtime` retains Xvfb diagnostics. Missing
dependencies, a non-llvmpipe renderer, insufficient OpenGL/GLSL, a missing
shader compiler, and Xvfb startup failures are reported explicitly.

This is a window-system E2E path. It validates SDL, X11 event polling and
physical presentation through a virtual display. It is separate from the
isolated/offscreen headless GUI architecture, which creates no Xvfb server,
SDL window, or swapchain.

The repeatable acceptance smoke is:

```bash
scripts/smoke-editor-virtual-display
```

## No-display offscreen editor E2E

Use the offscreen MCP smoke when automation needs the production editor
bootstrap, GUI composition and readback without SDL, Xvfb, `DISPLAY` or
`WAYLAND_DISPLAY`:

```bash
scripts/smoke-editor-mcp-offscreen
```

The smoke starts two installed `termin_editor` processes concurrently with
`--headless --offscreen-backend vulkan`, port `0` and separate agent-owned
session files. For each process it performs MCP initialize/tools-list, sends an
editor command and synthetic pointer input, captures a non-empty RGBA8 PNG,
checks that optional window modules were not loaded, requests normal shutdown
and verifies that the owned descriptor was removed. Instance ids and loopback
endpoints must be distinct.

Failures retain the temporary projects, screenshots, descriptors when present,
and editor logs, and print the retained directory. Use `--keep-temp` to retain
a successful run as well. This is the no-window counterpart to the independent
virtual-display E2E above; it does not test SDL presentation.

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
- `timeout`: seconds to wait for the editor thread to inspect the framegraph.
