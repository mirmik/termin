# Portal Walk

`world-controller-scene-cycle` is a tiny playable two-room game demonstrating
session-level scene navigation. Walk through the glowing gate in **Sunset Yard**
to enter **Blue Workshop**, then walk back through its gate to return.

Controls:

- **WASD** or **arrow keys** — move the pawn;
- **F5** / Play — start or stop the game in the editor.

The example deliberately revisits the first scene. A room that loses primary
status becomes inactive and render-detached, but remains loaded and bound to the
same `RuntimeSession`. Returning therefore reactivates the same scene and the
same `PortalWalker` instance. The component keeps its accumulated travel
distance; only the pawn position is explicitly reset to the room entrance so it
does not respawn inside the portal.

After the first round trip the Console logs:

```text
[PortalWalk] PASS round-trip=Sunset Yard->Blue Workshop->Sunset Yard; controller and inactive room state retained
```

## Editor Play

Open the project directly:

```bash
./sdk/bin/termin_editor \
  test-projects/world-controller-scene-cycle/WorldControllerSceneCycle.terminproj
```

Press Play, click the game viewport if it does not already have keyboard focus,
and walk to the portal. Stop Play after returning and confirm that only the
authoring Sunset Yard scene remains.

## Source project play

```bash
./sdk/bin/termin play \
  --project test-projects/world-controller-scene-cycle \
  --scene Scenes/Alpha.scene
```

For a deterministic non-interactive acceptance run, opt into autoplay:

```bash
TERMIN_PORTAL_WALK_AUTOPLAY=1 ./sdk/bin/termin play \
  --project test-projects/world-controller-scene-cycle \
  --scene Scenes/Alpha.scene \
  --headless --frames 500 --dt 0.02
```

The gameplay acceptance passes today, but the headless loader still reports
render-resource errors for renderable scenes; task `#1813` tracks filtering
render-only components and assets from non-rendering runs.

## Packaged desktop application

The `linux-dev` profile exports both rooms:

```bash
./sdk/bin/termin build linux-dev \
  --project test-projects/world-controller-scene-cycle

./sdk/bin/termin run linux-dev \
  --project test-projects/world-controller-scene-cycle
```

The profile controls exported content only. Runtime navigation still goes
through `WorldContext.transition_to()`.
