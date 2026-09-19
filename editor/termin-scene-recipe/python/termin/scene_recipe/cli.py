"""Preview and update a scene recipe in an explicitly selected Termin editor."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from termin.mcp.client import McpClientError, call, load_session


_RESULT_PREFIX = "TERMIN_SCENE_RECIPE_RESULT:"


def _project_directory(path: Path) -> str:
    path = path.expanduser().resolve()
    if path.suffix.lower() == ".terminproj":
        path = path.parent
    return os.path.normcase(str(path))


def _script(args: argparse.Namespace, recipe: object, resolutions: object) -> str:
    return (
        "import json, os\n"
        "from pathlib import Path\n"
        "if project_path is None:\n"
        "    raise RuntimeError('No editor project is open')\n"
        "_recipe_project = Path(project_path).expanduser().resolve()\n"
        "if _recipe_project.suffix.lower() == '.terminproj':\n"
        "    _recipe_project = _recipe_project.parent\n"
        f"if os.path.normcase(str(_recipe_project)) != {_project_directory(args.project)!r}:\n"
        "    raise RuntimeError('Wrong editor project')\n"
        f"_recipe_result = scene_recipe.run({args.action!r}, {recipe!r}, "
        f"{resolutions!r}, {args.selector!r}, {args.prefab!r})\n"
        f"print({_RESULT_PREFIX!r} + json.dumps(_recipe_result, ensure_ascii=False))\n"
    )


def _recipe_result(response: dict) -> dict:
    if "error" in response:
        raise McpClientError(f"Editor RPC failed: {json.dumps(response['error'], ensure_ascii=False)}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise McpClientError("Editor returned an invalid tool result")
    execution = result.get("structuredContent")
    if not isinstance(execution, dict):
        raise McpClientError("Editor returned no execution result")
    if result.get("isError") or not execution.get("ok"):
        raise McpClientError(str(execution.get("error") or "Editor script failed"))
    output = execution.get("output", "")
    if not isinstance(output, str):
        raise McpClientError("Editor returned invalid script output")
    for line in reversed(output.splitlines()):
        if line.startswith(_RESULT_PREFIX):
            value = json.loads(line[len(_RESULT_PREFIX):])
            if not isinstance(value, dict):
                raise McpClientError("Editor returned an invalid recipe result")
            return value
    raise McpClientError("Editor returned no recipe result")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "plan", "sync", "replace", "reset-transform"))
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--resolutions", type=Path)
    parser.add_argument("--id", dest="selector", help="Stable ID or unique current name")
    parser.add_argument("--prefab", help="Replacement prefab resource UUID")
    args = parser.parse_args(argv)
    if args.action == "replace" and (not args.selector or not args.prefab):
        parser.error("replace requires --id and --prefab")
    if args.action == "reset-transform" and not args.selector:
        parser.error("reset-transform requires --id")
    if args.action != "sync" and args.resolutions:
        parser.error("--resolutions is only valid with sync")

    session = None
    try:
        recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
        resolutions = (
            json.loads(args.resolutions.read_text(encoding="utf-8"))
            if args.resolutions else None
        )
        session = load_session(args.session.expanduser().resolve())
        response = call(session, "tools/call", {
            "name": "execute_python_script",
            "arguments": {"script": _script(args, recipe, resolutions), "timeout": 30.0},
        })
        result = _recipe_result(response)
    except (McpClientError, OSError, UnicodeError, ValueError) as exc:
        message = str(exc)
        if session is not None:
            message = message.replace(session["token"], "[redacted]")
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.action != "list" and (result.get("conflicts") or result.get("error")) else 0
