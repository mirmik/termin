# WorldController Scene Cycle

This project is the acceptance case for session-level multi-scene navigation.
It cycles automatically through three runtime scenes:

```text
Alpha -> Beta -> Gamma -> Alpha
```

The scenes use red, green, and blue render backgrounds so every committed
primary scene is visually obvious. `SceneCycleDirector` persists for the whole
RuntimeSession. Each scene owns a `SceneCycleProbe` that requests the next
canonical project-relative identity after two seconds.

After returning to Alpha, the controller verifies that:

- the route and active/inactive lifecycle order are correct;
- the same controller survived every transition;
- every scene component started exactly once;
- Alpha's local update count survived while the scene was inactive;
- the runtime catalog grew as filesystem-backed scenes were elevated.

A successful run stops in Alpha and logs:

```text
[SceneCycleAcceptance] PASS route=Alpha->Beta->Gamma->Alpha; controller and Alpha scene state retained
```

## Editor Play

Open the project directly:

```bash
./sdk/bin/termin_editor \
  test-projects/world-controller-scene-cycle/WorldControllerSceneCycle.terminproj
```

Press **F5** or the Play button. The viewport should remain red for two
seconds, switch to green, then blue, and finally return to red. The Console
must contain the `PASS` line and no `SceneCycleAcceptance` errors. Stop Play
and confirm that only the authoring Alpha scene remains.

Editor Play resolves Beta and Gamma from the project filesystem. It does not
read `build_profiles.json`.

## Source project play

Windowed:

```bash
./sdk/bin/termin play \
  --project test-projects/world-controller-scene-cycle \
  --scene Scenes/Alpha.scene
```

Deterministic headless acceptance:

```bash
./sdk/bin/termin play \
  --project test-projects/world-controller-scene-cycle \
  --scene Scenes/Alpha.scene \
  --headless --frames 500 --dt 0.02
```

This path also resolves scenes from the filesystem and does not require any
build profile. During the first cycle the logged catalog changes from Alpha,
to Alpha+Beta, to Alpha+Beta+Gamma.

## Packaged desktop application

The `linux-dev` profile exports all three scenes because the package cannot
load files that were not included in its export closure:

```bash
./sdk/bin/termin build linux-dev \
  --project test-projects/world-controller-scene-cycle

./sdk/bin/termin run linux-dev \
  --project test-projects/world-controller-scene-cycle
```

The application must show the same color sequence and `PASS` line. The profile
defines what is exported; it does not define the application's navigation
semantics.
