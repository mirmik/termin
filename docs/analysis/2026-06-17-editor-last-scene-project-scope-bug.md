# Editor lastScenePath leaks across projects

## Summary

During Windows editor startup diagnostics, a manifest-only test project exposed a
project-scoping bug in last-scene restoration. If the current project has no
project-local `project_settings/.editor_state.json` `last_scene`, the editor
falls back to global `Editor/lastScenePath` from `EditorSettings`. That global
path may point to a scene from another project.

Observed log example:

```text
[ERROR] Scene path outside project: scene=C:\Users\sorok\projects\Test\scene.scene project=C:\Users\sorok\project\termin\Testing\termin-win-hang-repro
```

## Reproduction

1. Open a project with a scene and let the editor persist global
   `Editor/lastScenePath`.
2. Create or open a different project that has a `.terminproj` file but no
   project-local `project_settings/.editor_state.json` with a valid `last_scene`.
3. Start `sdk/bin/termin_editor.exe <new-project>.terminproj`.

The editor sets the new current project, then attempts to load the previous
global scene path. `SceneFileController.validate_scene_path()` rejects it because
the scene is outside the current project.

## Affected Code

- `termin-app/termin/editor_tcgui/scene_file_controller.py`
  - `SceneFileController.load_last_scene()` first checks
    `ProjectSettingsManager.instance().get_last_scene()`, then falls back to
    `EditorSettings.instance().get_last_scene_path()`.
- `termin-project/python/termin/project/settings.py`
  - `ProjectSettingsManager.get_last_scene()` reads project-local editor state.
- `termin-app/termin/editor_core/settings.py`
  - `EditorSettings.KEY_LAST_SCENE_PATH` is global editor state, not scoped by
    project.

## Expected Behavior

Last scene restoration after a project is selected should be project-scoped.
Opening project B should not try to load project A's last scene.

Reasonable fix direction:

- Use project-local `ProjectSettingsManager.get_last_scene()` as the authoritative
  restore source once a project is active.
- Avoid global `Editor/lastScenePath` fallback when `current_project_path` is set,
  unless the global path is inside that project.
- If fallback is kept for legacy migration, migrate only when the path validates
  against the current project root, then store it into project-local
  `.editor_state.json`.

## Impact

This is not the cause of the Windows window hang fixed on 2026-06-17, but it
creates noisy startup errors and can leave a newly opened project without its
expected scene state. It also makes startup behavior depend on unrelated editor
history, which is brittle for automated repro projects and smoke tests.
