"""ProjectOperations — UI-agnostic file operations for the project browser.

Wraps directory / file creation, deletion, FBX/GLB extraction, and the
set of "new asset" templates (material / shader / component / pipeline /
prefab). Dialogs go through :class:`DialogService`; both Qt and tcgui
project browsers delegate here.

``sync_stdlib`` lives at module scope because it's a pure filesystem
operation called at open-project time from both editors.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from tcbase import log

from termin.editor_core.dialog_service import DialogService


# ======================================================================
# Templates for "new ..." text assets
# ======================================================================

_MATERIAL_TEMPLATE = '''{
    "shader": "DefaultShader",
    "uniforms": {
    },
    "textures": {
    }
}
'''

_SHADER_TEMPLATE = '''@program NewShader

@phase opaque

@stage vertex
#version 330 core

void main() {}

@stage fragment
#version 330 core

out vec4 frag_color;
void main() { frag_color = vec4(1.0); }
'''

_COMPONENT_TEMPLATE = '''"""
MyComponent component.
"""

from __future__ import annotations

from termin.visualization.core.python_component import PythonComponent


class MyComponent(PythonComponent):
    """
    Custom component.

    Attributes:
        speed: Movement speed.
    """

    def __init__(self, speed: float = 1.0):
        super().__init__()
        self.speed = speed

    def start(self) -> None:
        """Called when the component is first activated."""
        super().start()

    def update(self, dt: float) -> None:
        """Called every frame.

        Args:
            dt: Delta time in seconds.
        """
        pass
'''

_PIPELINE_TEMPLATE = '''{
  "name": "NewPipeline",
  "passes": [],
  "resource_specs": []
}
'''


# ======================================================================
# Module-level helpers
# ======================================================================

def sync_stdlib(project_root: Path) -> None:
    """Sync the built-in stdlib (materials, shaders, glsl) into
    ``project_root / stdlib``. Called on project open by both editors."""
    import termin

    stdlib_src = Path(termin.__path__[0]) / "resources" / "stdlib"
    stdlib_dst = project_root / "stdlib"

    if not stdlib_src.exists():
        return

    created = not stdlib_dst.exists()
    updated = 0

    for src_file in stdlib_src.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(stdlib_src)
        dst_file = stdlib_dst / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        need_update = (not dst_file.exists()) or (dst_file.stat().st_size != src_file.stat().st_size)
        if need_update:
            shutil.copy2(src_file, dst_file)
            updated += 1

    if created:
        log.info(f"[stdlib] deployed: {updated} file(s)")
    elif updated > 0:
        log.info(f"[stdlib] synced: {updated} file(s) updated")


# ======================================================================
# ProjectOperations
# ======================================================================

class ProjectOperations:
    """File operations with DialogService-backed confirm/input flows.

    Each operation accepts an ``on_refresh`` callback so the view can
    re-scan the filesystem after a mutation. ``on_navigate`` (optional)
    is used by extract_fbx / extract_glb to jump into the extracted
    directory.
    """

    def __init__(self, dialog_service: DialogService):
        self._dialog = dialog_service

    # ------------------------------------------------------------------
    # Directory / file mutations
    # ------------------------------------------------------------------

    def create_directory(self, base_dir: Path | None, on_refresh: Callable[[], None]) -> None:
        if base_dir is None:
            return
        self._dialog.show_input(
            title="Create Directory",
            message="Directory name:",
            default="",
            on_result=lambda name: self._apply_create_directory(base_dir, name, on_refresh),
        )

    def _apply_create_directory(
        self,
        base_dir: Path,
        name: str | None,
        on_refresh: Callable[[], None],
    ) -> None:
        if not name:
            return
        clean = name.strip()
        if not clean:
            return
        target = base_dir / clean
        try:
            target.mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            self._dialog.show_error("Error", f"Directory '{clean}' already exists.")
            return
        except OSError as e:
            self._dialog.show_error("Error", f"Failed to create directory: {e}")
            return
        on_refresh()

    def delete_item(self, path: Path, on_refresh: Callable[[], None]) -> None:
        if path.is_file():
            message = f"Delete file '{path.name}'?"
        else:
            message = f"Delete directory '{path.name}' and all its contents?"
        self._dialog.show_choice(
            title="Confirm Delete",
            message=message,
            choices=["Yes", "No"],
            default="No",
            cancel="No",
            on_result=lambda choice: self._apply_delete(path, choice, on_refresh),
        )

    def _apply_delete(
        self,
        path: Path,
        choice: str | None,
        on_refresh: Callable[[], None],
    ) -> None:
        if choice != "Yes":
            return
        try:
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
        except OSError as e:
            self._dialog.show_error("Error", f"Failed to delete: {e}")
            return
        on_refresh()

    # ------------------------------------------------------------------
    # Extractors (FBX / GLB)
    # ------------------------------------------------------------------

    def extract_fbx(
        self,
        fbx_path: Path,
        on_refresh: Callable[[], None],
        on_navigate: Callable[[Path], None] | None = None,
    ) -> None:
        output_dir = fbx_path.parent / fbx_path.stem
        if output_dir.exists():
            self._dialog.show_choice(
                title="Directory Exists",
                message=f"Directory '{output_dir.name}' already exists.\nOverwrite contents?",
                choices=["Yes", "No"],
                default="No",
                cancel="No",
                on_result=lambda c: self._do_extract_fbx(fbx_path, output_dir, c, on_refresh, on_navigate),
            )
        else:
            self._do_extract_fbx(fbx_path, output_dir, "Yes", on_refresh, on_navigate)

    def _do_extract_fbx(
        self,
        fbx_path: Path,
        output_dir: Path,
        choice: str | None,
        on_refresh: Callable[[], None],
        on_navigate: Callable[[Path], None] | None,
    ) -> None:
        if choice != "Yes":
            return
        from termin.loaders.fbx_extractor import extract_fbx
        try:
            output_dir, _created = extract_fbx(fbx_path, output_dir)
        except Exception as e:
            log.error(f"[ProjectOperations] extract FBX failed: {e}")
            self._dialog.show_error("Extract Failed", f"Failed to extract FBX:\n{e}")
            return
        on_refresh()
        if on_navigate is not None:
            on_navigate(output_dir)

    def extract_glb(
        self,
        glb_path: Path,
        on_refresh: Callable[[], None],
        on_navigate: Callable[[Path], None] | None = None,
    ) -> None:
        output_dir = glb_path.parent / glb_path.stem
        if output_dir.exists():
            self._dialog.show_choice(
                title="Directory Exists",
                message=f"Directory '{output_dir.name}' already exists.\nOverwrite contents?",
                choices=["Yes", "No"],
                default="No",
                cancel="No",
                on_result=lambda c: self._do_extract_glb(glb_path, output_dir, c, on_refresh, on_navigate),
            )
        else:
            self._do_extract_glb(glb_path, output_dir, "Yes", on_refresh, on_navigate)

    def _do_extract_glb(
        self,
        glb_path: Path,
        output_dir: Path,
        choice: str | None,
        on_refresh: Callable[[], None],
        on_navigate: Callable[[Path], None] | None,
    ) -> None:
        if choice != "Yes":
            return
        from termin.loaders.glb_extractor import extract_glb
        try:
            output_dir, _created = extract_glb(glb_path, output_dir)
        except Exception as e:
            log.error(f"[ProjectOperations] extract GLB failed: {e}")
            self._dialog.show_error("Extract Failed", f"Failed to extract GLB:\n{e}")
            return
        on_refresh()
        if on_navigate is not None:
            on_navigate(output_dir)

    # ------------------------------------------------------------------
    # New asset templates
    # ------------------------------------------------------------------

    def create_text_file(
        self,
        base_dir: Path | None,
        title: str,
        message: str,
        default: str,
        suffix: str,
        template: str,
        on_refresh: Callable[[], None],
    ) -> None:
        if base_dir is None:
            return
        self._dialog.show_input(
            title=title,
            message=message,
            default=default,
            on_result=lambda name: self._apply_create_text_file(
                base_dir, name, suffix, template, on_refresh
            ),
        )

    def _apply_create_text_file(
        self,
        base_dir: Path,
        name: str | None,
        suffix: str,
        template: str,
        on_refresh: Callable[[], None],
    ) -> None:
        if not name:
            return
        clean = name.strip()
        if not clean:
            return
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]
        file_path = base_dir / f"{clean}{suffix}"
        if file_path.exists():
            self._dialog.show_error("Error", f"File '{file_path.name}' already exists.")
            return
        try:
            file_path.write_text(template, encoding="utf-8")
        except OSError as e:
            self._dialog.show_error("Error", f"Failed to create file: {e}")
            return
        on_refresh()

    def create_material(self, base_dir: Path | None, on_refresh: Callable[[], None]) -> None:
        self.create_text_file(
            base_dir,
            title="Create Material",
            message="Material name:",
            default="NewMaterial",
            suffix=".material",
            template=_MATERIAL_TEMPLATE,
            on_refresh=on_refresh,
        )

    def create_shader(self, base_dir: Path | None, on_refresh: Callable[[], None]) -> None:
        self.create_text_file(
            base_dir,
            title="Create Shader",
            message="Shader name:",
            default="NewShader",
            suffix=".shader",
            template=_SHADER_TEMPLATE,
            on_refresh=on_refresh,
        )

    def create_component(self, base_dir: Path | None, on_refresh: Callable[[], None]) -> None:
        self.create_text_file(
            base_dir,
            title="Create Component",
            message="File name:",
            default="my_component",
            suffix=".py",
            template=_COMPONENT_TEMPLATE,
            on_refresh=on_refresh,
        )

    def create_pipeline(self, base_dir: Path | None, on_refresh: Callable[[], None]) -> None:
        self.create_text_file(
            base_dir,
            title="Create Render Pipeline",
            message="Pipeline name:",
            default="NewPipeline",
            suffix=".pipeline",
            template=_PIPELINE_TEMPLATE,
            on_refresh=on_refresh,
        )

    def create_prefab(self, base_dir: Path | None, on_refresh: Callable[[], None]) -> None:
        if base_dir is None:
            return
        self._dialog.show_input(
            title="Create Prefab",
            message="Prefab name:",
            default="NewPrefab",
            on_result=lambda name: self._apply_create_prefab(base_dir, name, on_refresh),
        )

    def _apply_create_prefab(
        self,
        base_dir: Path,
        name: str | None,
        on_refresh: Callable[[], None],
    ) -> None:
        if not name:
            return
        clean = name.strip()
        if not clean:
            return
        file_path = base_dir / f"{clean}.prefab"
        if file_path.exists():
            self._dialog.show_error("Error", f"File '{file_path.name}' already exists.")
            return
        try:
            from termin.editor.prefab_persistence import PrefabPersistence
            from termin.visualization.core.resources import ResourceManager
            PrefabPersistence(ResourceManager.instance()).create_empty(file_path, name=clean)
        except Exception as e:
            log.error(f"[ProjectOperations] create prefab failed: {e}")
            self._dialog.show_error("Error", f"Failed to create prefab: {e}")
            return
        on_refresh()
