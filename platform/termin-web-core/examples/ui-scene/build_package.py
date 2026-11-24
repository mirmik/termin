"""Add a packaged screen-space HUD to the web render fixture."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    example = Path(__file__).resolve().parent
    blob_writer = example.parents[3] / "editor/termin-project-build/python/termin/project_build/runtime_package_blob.py"

    with tempfile.TemporaryDirectory(prefix="termin-web-ui-") as temporary:
        root = Path(temporary)
        shutil.copytree(args.fixture, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.trpkg", "*.stamp"))
        ui_path = "ui/hud.ui-document.json"
        (root / "ui").mkdir(exist_ok=True)
        shutil.copyfile(example / "hud.ui-document.json", root / ui_path)
        hud = read(root / ui_path)
        manifest = read(root / "manifest.json")
        manifest["resources"].append({"type": "ui_document", "uuid": hud["uuid"], "path": ui_path})
        write(root / "manifest.json", manifest)

        entry_scene = next(item for item in manifest["scenes"] if item["identity"] == manifest["entry_scene"])
        scene_path = root / entry_scene["path"]
        scene = read(scene_path)
        scene["entities"].append({
            "name": "Screen HUD",
            "uuid": "web-scene-hud-entity",
            "components": [{
                "type": "UIComponent",
                "source_id": "web-scene-hud-component",
                "data": {
                    "ui_layout": {
                        "type": "uuid", "kind": "ui_document", "role": "ui_document",
                        "uuid": hud["uuid"], "name": hud["name"],
                    },
                },
            }],
        })
        write(scene_path, scene)
        subprocess.run([sys.executable, blob_writer, root, args.output], check=True)


if __name__ == "__main__":
    main()
