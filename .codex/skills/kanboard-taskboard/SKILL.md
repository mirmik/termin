---
name: kanboard-taskboard
description: Use when Codex should inspect or update the user's Kanboard task board for the Termin project, including reading cards, creating tasks, adding comments, closing completed work, or moving cards through workflow columns via the local scripts/taskboard helper.
---

# Kanboard Taskboard

Use the Termin repository helper `scripts/taskboard` for normal Kanboard work. It reads `~/.config/termin/kanboard-codex.env`, uses the `codex` API token, defaults to project `termin` (`project_id=1`), supports dry-run for risky operations, and verifies important writes.

Use lower-level `scripts/kanboard-api` only as an escape hatch for uncommon Kanboard JSON-RPC methods not covered by `scripts/taskboard`.

## Rules

- Prefer `scripts/taskboard` for reading, exporting, creating, commenting, moving, and closing tasks.
- Prefer `scripts/kanboard-api` over raw `curl`, direct database reads, or printing credentials when a raw JSON-RPC method is needed.
- Do not use `--raw` unless the user explicitly needs an unredacted API response.
- If the sandbox blocks network access, rerun the same helper command with escalation and the prefix rule `['scripts/taskboard']` or `['scripts/kanboard-api']`, matching the command used.
- Treat Kanboard as task state, not as the source of truth for code. Verify code locally before moving or closing cards.
- When modifying cards, keep titles short and put technical detail in the description or comments.
- Use `--dry-run` before mass close/move/create operations.
- Do not leave completed cards open "just in case"; close them after verification. If new scope remains, create or keep a separate card for that scope.
- Prefer updating a stale task description with current state/remaining/verification over burying the real status in more comments.

## Quick Commands

Run commands from `/home/mirmik/project/termin` unless using absolute paths. On Windows, use the matching PowerShell wrappers: `scripts/taskboard.ps1` and `scripts/kanboard-api.ps1`.

```bash
scripts/taskboard list
scripts/taskboard list --tags
scripts/taskboard list --column "On Test" --tags
scripts/taskboard show 119
scripts/taskboard export --comments --tags --output /tmp/termin-board.json
scripts/taskboard close 28 29 41 --dry-run
scripts/taskboard close 28 29 41 --comment "Implemented and verified."
scripts/taskboard move 13 "On Test" --dry-run
scripts/taskboard create "[bug] Short title" --description "Context..."
scripts/taskboard create "[bug] Short title" --description "Context..." --tags bug size:S
# Windows:
scripts/taskboard.ps1 list
```

Known current project:

- `termin`: `project_id=1`

## Workflow

1. Start by reading active tasks with `scripts/taskboard list`, or use `scripts/taskboard export --comments` for audits.
2. If a user asks about status, summarize task id, title, column/status, and any useful description/comment context.
3. If a user asks to create or update task state, make the Kanboard change only after the intended title/description/action is clear from context.
4. For mass changes, run the matching `--dry-run` first.
5. After a write operation, rely on `scripts/taskboard` verification where available, or read the affected task back and report the resulting id/state.

## Common JSON-RPC Methods

The helper is generic: first argument is the Kanboard method, second optional argument is JSON params.

Use `scripts/kanboard-api` for uncommon raw methods. Useful read methods:

```bash
scripts/kanboard-api getMyProjects
scripts/kanboard-api getAllTasks '{"project_id":1,"status_id":1}'
scripts/kanboard-api getTask '{"task_id":1}'
scripts/kanboard-api getColumns '{"project_id":1}'
scripts/kanboard-api getAllComments '{"task_id":1}'
# Windows:
scripts/kanboard-api.ps1 getTask '{"task_id":1}'
```

Common write methods to use carefully:

```bash
scripts/kanboard-api createTask '{"project_id":1,"title":"Short title","description":"Details"}'
scripts/kanboard-api updateTask '{"id":1,"title":"Updated title"}'
scripts/kanboard-api createComment '{"task_id":1,"user_id":2,"content":"Comment text"}'
scripts/kanboard-api closeTask '{"task_id":1}'
```

For moving cards, read columns first and use the Kanboard API method/params that match the installed version. Do not guess column ids.
