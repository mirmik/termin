---
name: termin-editor-mcp
description: Control a running Termin editor through its project-scoped MCP server. Use when an agent should execute Python in the editor process, inspect or mutate the live scene, capture editor or framegraph images, inspect framegraph state, configure the Termin stdio MCP broker, launch an MCP-enabled editor, or fall back to the engine's local CLI client when native MCP tools are unavailable.
---

# Termin Editor MCP

Prefer the configured `termin_editor` MCP server and call its native tools
directly. Treat `scripts/termin-editor-mcp` primarily as the stdio transport
used by the MCP host; use its CLI commands only as a fallback when the current
host has not loaded the server.

Resolve these roots before launching or configuring anything:

- `PROJECT_ROOT`: the Termin project checkout and its `.terminproj`;
- `TERMIN_ROOT`: the matching Termin engine checkout containing
  `sdk/bin/termin_editor` and `scripts/termin-editor-mcp`.

These names are notation, not persistent environment variables. Read repository
instructions first. Prefer a declared engine path, then an unambiguous sibling
checkout such as `../termin`; ask if the engine checkout remains ambiguous.

## Native MCP workflow

Tool catalogs may be lazy or deferred. Absence from the initially rendered
tool declarations does not mean that `termin_editor` was not loaded. In Codex
hosts that expose `functions.exec`, inspect `ALL_TOOLS` for the exact
`mcp__termin_editor__` prefix and call the matching method on `tools` inside the
exec script. With another host, use its complete or deferred tool-discovery
mechanism before deciding that native tools are unavailable.

1. Check the host's complete tool catalog for the `termin_editor` MCP tools
   listed below. If it exposes them, call them natively and do not shell out to
   the CLI helper. Do not infer that they are absent from a shortened top-level
   tool list.
2. Treat the broker's SDK-scoped registry as the attachment point for
   user-owned editors. The broker itself may start first and selects an editor
   by canonical project path when a tool is called.
3. Call the narrowest native tool for the task. Use
   `execute_python_script` only when a purpose-built tool is insufficient.
4. Read back changed scene state or capture a screenshot when verification is
   useful.

The server currently exposes:

- `execute_python_script`: run Python inside the live editor namespace;
- `capture_editor_screenshot`: capture the editor UI or viewport;
- `inspect_framegraph`: list targets, passes, resources, schedules, duplicate
  pass names, internal symbols, and optional serialized pass data;
- `capture_framegraph_resource`: export a selected framegraph resource as PNG;
- `capture_framegraph_pass_symbol`: capture framebuffer state after an internal
  symbol draw. Prefer `pass_index` over `pass_name`, and use `symbol_index` when
  symbol names are duplicated.

Follow the live MCP input schemas rather than assuming optional arguments. Keep
captures inside the project checkout or the OS temporary directory unless the
user explicitly selects another location.

Before calling `inspect_framegraph` on ChronoSquad, check the Termin repository
or task board for issue `#565`. As of 2026-07-18 it is Backlog and records that
this call can terminate the editor. While it remains unresolved, warn the user,
ensure work is saved, and obtain explicit acceptance before testing it. The CLI
`framegraph` command reaches the same editor functionality and is not a known
workaround.

## Launch the editor

Without `--session`, the broker and user-opened editors compute the same
registry path from the canonical SDK root. Each editor publishes a unique
instance descriptor. Use `scripts/termin-editor-mcp registry-path` to inspect
the registry location and `scripts/termin-editor-mcp sessions` to list safe
metadata without bearer tokens. The MCP client and its stdio broker may start
before the editor; tool discovery does not require a registered instance.

The broker selects the editor whose canonical `project_path` contains its
project selector (the current working directory by default). If only one user
editor is registered, it is an unambiguous fallback. If multiple live editors
match the same project, never guess: inspect `sessions` and use
`--instance INSTANCE_ID`, or use an explicit agent session file.

Never publish an agent-owned editor into the user registry. Give every
agent-owned editor a unique temporary directory, port `0`, and an explicit
session file; address it through the CLI helper or a separate broker. Only stop
and clean up editor processes and temporary directories created by the current
agent. If the editor binary is absent, build or install the Termin SDK using
that engine checkout's repository instructions before continuing.

```bash
agent_mcp_dir="$(mktemp -d /tmp/termin-editor-agent.XXXXXX)"
TERMIN_EDITOR_MCP=1 \
TERMIN_EDITOR_MCP_PORT=0 \
TERMIN_EDITOR_MCP_SESSION_FILE="$agent_mcp_dir/session.json" \
"$TERMIN_ROOT/sdk/bin/termin_editor" "$PROJECT_ROOT/Project.terminproj"
```

```powershell
$AgentMcpDir = Join-Path ([System.IO.Path]::GetTempPath()) `
  ("termin-editor-agent-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $AgentMcpDir | Out-Null
$env:TERMIN_EDITOR_MCP = "1"
$env:TERMIN_EDITOR_MCP_PORT = "0"
$env:TERMIN_EDITOR_MCP_SESSION_FILE = Join-Path $AgentMcpDir "session.json"
& "$TerminRoot/sdk/bin/termin_editor.exe" "$ProjectRoot/Project.terminproj"
```

The editor writes a loopback endpoint, generated bearer token, instance id, and
project metadata to its descriptor. The stdio broker serves tool schemas
locally and rescans discovery state for every call. While no applicable editor
is running, calls return `Termin Editor is unavailable`; starting or restarting
one on a new port requires no broker or MCP client restart. A clean editor
shutdown removes only its owned descriptor. Stale descriptors are ignored when
one live match remains and are visible as unreachable in `sessions`.

## Configure an MCP client

Register `scripts/termin-editor-mcp serve` as a project-scoped local stdio MCP
server. Give every checkout its own server name when several project configs
can be active together. User-editor brokers use registry discovery; agent-owned
editors use explicit unique session files outside that registry. Configuration
and trust syntax is client-specific.

For Codex, use a project-scoped `.codex/config.toml` with absolute,
machine-adapted paths:

```toml
[mcp_servers.termin_editor]
command = "/absolute/path/to/termin/scripts/termin-editor-mcp"
args = ["serve"]
startup_timeout_sec = 10
tool_timeout_sec = 60
default_tools_approval_mode = "approve"
```

The broker uses the MCP process working directory as its project selector. If
the host does not preserve the workspace directory, configure it explicitly:

```toml
args = ["--project", "/absolute/path/to/project", "serve"]
```

On Windows use `pwsh` as `command` and pass `-NoProfile`, `-File`, the absolute
path to `termin-editor-mcp.ps1`, and `serve` in `args`. Restart Codex after
changing MCP configuration, but not after editor restarts, and inspect `/mcp`
in the TUI. Keep this server project-scoped and set its default approval mode to
`approve`: this deliberately trusts all editor tools, including arbitrary
Python execution, so unattended agents do not stop for an MCP prompt. Do not
copy this trust policy to unrelated or remote MCP servers.

## Editor Python namespace

Useful names include:

- `editor`, `scene`, `scene_manager`, `selected` / `selected_entity`;
- `scene_edit`: undo-aware local transform editing; prefer it over direct
  transform mutation;
- `framegraph_debugger`, `project_path`, `rm` / `resource_manager`;
- `Vec3`, `Vec4`, `Quat`, `Pose3`, `GeneralPose3`, `GeneralTransform3`;
- `request_render_update()` / `refresh_editor()` and the `termin` package.

After direct scene mutation, request a viewport update. Prefer `scene_edit`
where available because it records undo state and refreshes the viewport.

## CLI fallback

If native MCP tools are absent because the host has not loaded its MCP config,
use the helper from `TERMIN_ROOT` until restarting the host is practical. CLI
commands still require a running editor and resolve it through the registry or
an authenticated explicit session file; do not replace them with raw HTTP.

```bash
"$TERMIN_ROOT/scripts/termin-editor-mcp" sessions
"$TERMIN_ROOT/scripts/termin-editor-mcp" --project "$PROJECT_ROOT" exec 'print(project_path)'
"$TERMIN_ROOT/scripts/termin-editor-mcp" --instance INSTANCE_ID exec 'print(project_path)'
"$TERMIN_ROOT/scripts/termin-editor-mcp" --session /tmp/termin-editor-mcp-project.json tools-list
"$TERMIN_ROOT/scripts/termin-editor-mcp" --session /tmp/termin-editor-mcp-project.json exec 'print(project_path)'
"$TERMIN_ROOT/scripts/termin-editor-mcp" --session /tmp/termin-editor-mcp-project.json screenshot --path /tmp/editor.png
"$TERMIN_ROOT/scripts/termin-editor-mcp" --session /tmp/termin-editor-mcp-project.json framegraph --include-pass-json
"$TERMIN_ROOT/scripts/termin-editor-mcp" --session /tmp/termin-editor-mcp-project.json framegraph-capture --target-index 0 --resource OUTPUT --path /tmp/output.png
"$TERMIN_ROOT/scripts/termin-editor-mcp" --session /tmp/termin-editor-mcp-project.json framegraph-pass-capture --target-index 0 --pass-index 0 --symbol-index 0 --path /tmp/pass-symbol.png
```

On Windows invoke the adjacent `termin-editor-mcp.ps1` wrapper with the same
arguments. Use `exec-file` instead of `exec` for a substantial script.
