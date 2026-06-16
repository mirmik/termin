# Termin CLI

`termin` is the central SDK command hub installed into `sdk/bin`.
It is intentionally small: it resolves a subcommand and delegates to a
dedicated executable.

## Commands

```bash
termin editor [project]
termin launcher
termin shaderc ...
termin profiles [--project path/to/project]
termin profile PROFILE [--project path/to/project]
termin build PROFILE [--project path/to/project] [--dry-run]
termin builder ...
```

Unknown commands are resolved in a git-like form:

1. `termin_<command>` next to the `termin` executable;
2. `termin-<command>` next to the `termin` executable;
3. the same names in `PATH`.

`termin build PROFILE` currently delegates to:

```bash
termin_builder build PROFILE
```

## Build Profiles

Build profiles are project data. The default location is:

```text
project_settings/build_profiles.json
```

Initial schema:

```json
{
  "profiles": {
    "dev": {
      "target": "desktop",
      "entry_scene": "Main.scene",
      "output_dir": "dist/dev"
    },
    "quest": {
      "target": "quest_openxr",
      "entry_scene": "Main.scene",
      "output_dir": "dist/quest"
    }
  }
}
```

`termin_builder` validates and displays profiles, but build execution is not
wired yet. Use `--dry-run` to check profile loading without failing the command.
