# Predicting the first contact within a step

The same opt-in predictor detected an incoming sphere, a rotating box hitting
a ledge between two clear endpoint poses, and a six-foot spider landing. At a
1 ms step it made the spider's peak geometric penetration much less dependent
on release height. It also changed the effective impact response of the soft
contact material. Peak force and low-friction trajectories need separate
acceptance criteria before using this path in the engine.

## What the experiment changes

The control is the [previous closed-loop hybrid](2026-11-27-spider-mujoco-transfer.md)
using Termin mass, bias and sphere/box geometry and MuJoCo 3.15 Newton,
elliptic friction, NoSlip 10 and semi-implicit Euler. All materials in the
landing comparisons use a 2 ms contact time constant. The predictor operates
on model collision masks, geometry and generalized motion. The controlled
joint and foot names occur in the spider recorder only.

1. Compute the free end-step velocity. Sweep both geometries along the
   kinematic trajectory obtained by holding that velocity fixed. For a new
   pair use signed distance, relative travel bounds and a separating axis to
   search for an intersection inside the step. The search also considers
   intervals with two clear endpoints. The return value includes a fraction
   of the step, the contact normal and the impact witnesses mapped back to
   the current pose.
2. At the first confirmed crossing add a normal-only row to the same Newton
   solve as the other constraints. For straight closing motion the target
   normal velocity is the negative starting gap divided by the step time.
   For rotation the implementation uses the time fraction times the free
   normal velocity at the contact. This approximates the response over the
   whole step. No internal integration step occurs at the reported hit time.
3. If the same pair crosses again on the next step, use its ordinary surface
   parameters including friction. Contacts already returned by discrete
   collision keep their usual rows. A separating pair drops out. In a
   discarded variant repeated normal-only rows starved loaded feet of
   friction. They moved about 175 mm before the first second of nominal hold.

## Geometry and impulse controls

| Case at 1 ms | Result |
| --- | --- |
| 1 kg sphere dropped onto a plane, crossing at 10%, 45%, 90% of the free step | Peak overlap over the landing was 0.892 / 0.545 / 0.129 mm in the control and 0.006 / 0.024 / 0.048 mm with prediction. Peak upward speeds fell from 0.221 / 0.108 / 0.027 to 0.0004 / 0.0040 / 0.0085 m/s. |
| Sphere separating from or moving parallel to the plane | Zero forecast contacts and zero impulse. |
| Two free spheres of masses 1 and 3 kg closing with a 0.2 mm gap | Hit halfway through the step with impulse 0.149985 N·s. Adding the same −2 or +7 m/s velocity to both bodies preserved the time fraction and impulse. Total linear momentum error was below 4e-15 kg·m/s. |
| Rotating box free to translate in its plane, ledge hit | The free endpoints had positive separating-axis gaps of 0.945 and 0.226 mm, while the middle configuration overlapped by 0.100 mm. Independent rectangular separating-axis tests gave first crossing at 0.35242724 of the step, the predictor 0.35242720. First impulse 2.027 N·s. On the accepted trajectory no overlap was found at the 257 sampled angles per step. |
| Same rotation, ledge shifted outwards by 0.2 mm | Minimum clearance 0.100 mm, zero reported hits and zero impulse. |

The ball oracle above checks the discrete Euler drift. Ballistic flight from
the same height gives first touch about half a millisecond later on these
three drops. The predictor changes contact activation and leaves the free
integrator's timing error in place. A hinge-only version of the box also
passed. An earlier handoff variant reached nearly redundant contact rows and
a spurious sum of normal impulses above 1e12 N·s. Replaying that state with
ordinary MuJoCo reproduced the anomaly. The final handoff avoided that state
in the eight-step hinge test.

## Landing the spider

All rows use the same solver and materials on the same robot. Only initial
height and the predictor switch change. For each height the first predicted
load is in the interval ending at 101 ms, one step earlier than the control.
All six feet enter together. Vertical impulse is summed from release through
150 ms. No unsupported whole-robot rebound was observed in these holds.

| Initial foot clearance, mm | Peak overlap, control → predicted (mm) | Peak vertical force, control → predicted (kN) | Total impulse, control → predicted (N·s) |
| ---: | ---: | ---: | ---: |
| 49.6 | 0.931 → 0.085 | 4.865 → 3.570 | 21.883 → 21.877 |
| 50.0 | 0.531 → 0.091 | 4.342 → 2.350 | 21.871 → 21.868 |
| 50.4 | 0.169 → 0.097 | 3.833 → 3.373 | 21.860 → 21.859 |

**A small geometric overlap is a different target from reproducing a
compliant impact.** An independent control integrated the same stock MuJoCo
material at 12.5 and 6.25 µs per step. At nominal height the latter produced
0.769 mm, 3.710 kN and 21.843 N·s (at 12.5 µs, 0.767 mm, 3.712 kN and
21.844 N·s). Across all three heights at 6.25 µs, peaks ranged from 0.765
to 0.774 mm and 3.69 to 3.73 kN. These are numerical controls for the soft
model, not measurements from a physical robot. The predictive impulse spreads
the effect of the first collision over the enclosing 1 ms interval.

## Standing, sliding and liftoff

Between 1 and 4 s the maximum horizontal foot-centre displacement in hold was
0.000442 mm in the control and 0.000443 mm with prediction. During the 5° hip
sweep it was 0.14136 and 0.14132 mm. At low friction (μ = 0.15) it changed
from 56.30 to 35.04 mm, while the maximum displacement between first loading
and 1 s increased from 74.79 to 92.80 mm. The predictor changed when the
feet moved. The negative hip ramp also changed the maximum foot excursion
over seconds 1–4 from 134.7 to 156.0 mm.

On the positive ramp the middle left foot crossed 10 µm clearance at 1.078
and 1.075 s. On the negative ramp the rear and front left first crossings
changed by 1 ms. The right rear also crossed the threshold earlier, reaching
only 0.030 mm peak clearance (control 0.016 mm). This threshold is sensitive
to small changes in gap.

## Cost and scope

Seven alternating trials of the native combined backend ran on CPU 6 of the
same Ryzen AI MAX+ 395. The impact figure is the mean per step over the four
steps from 99 to 103 ms, taking the median of 31 fresh falls in each trial.
Loaded and standing times cover 1–4 s of the hip sweep and the following
second. Target updates and endpoint kinematics are included.

| Phase | Control µs/step | Predicted µs/step |
| --- | ---: | ---: |
| Four-step window around first touchdown | 21.97 | 103.88 |
| Loaded hip sweep | 20.72 | 21.16 |
| Subsequent standing | 20.71 | 21.17 |

In the landing window the predictor queries intermediate poses of multiple
incoming feet and rebuilds the constraint system when it inserts rows.
Profiling the individual costs would be necessary to apportion that increase.
Ordinary standing took about 2% longer. These numbers cover the optional native
benchmark, with the regular Termin scene synchronization outside the timer.

The prototype supports zero-margin rigid convex primitives and stationary
planes in the tested MuJoCo setup. The pair list is prepared once for a fixed
topology. The sweep models free motion with a frozen generalized velocity.
Forces on other constraints during the same solve can alter that motion.
Time subdivision ends at 2⁻²⁵ of a step; a tangency or shorter interior visit
may escape detection. An exhausted distance-query budget is reported as an
error. The experiment covers specific shapes and trajectories, not a general
continuous-collision guarantee. A next comparison should apply the same hit
detector with a material-consistent response for the remaining fraction of
the step, using peak force, force history and impulse alongside overlap.

## Reproduction

From the Termin root use the Release SDK, the sibling projects and the MuJoCo
environment listed in the [hybrid experiment](2026-11-27-spider-mujoco-transfer.md).
The targets are optional and the SDK has no added runtime dependency.

```sh
py=../twister-capper/.venv/bin/python
mjpkg=$("$py" -c 'import mujoco; print(mujoco.__path__[0])')
out=build/benchmarks/predict-contacts
cmake -S benchmarks/physics-small -B "$out" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$PWD/sdk" -DTERMIN_BENCHMARK_MUJOCO_DIR="$mjpkg"
cmake --build "$out" --target predict_contact predict_geometry -j 4
"$py" benchmarks/physics-small/predict_contact_cases.py \
    --library "$out/libpredict_contact.so" --output "$out/primitives.json"
"$py" benchmarks/physics-small/predict_contact_spider.py \
    --library "$out/libpredict_contact.so" --geometry "$out/libpredict_geometry.so" quality "$out/quality"
taskset -c 6 "$py" benchmarks/physics-small/predict_contact_spider.py \
    --library "$out/libpredict_contact.so" --geometry "$out/libpredict_geometry.so" time
```

The fine-step control can be reproduced for the nominal height with the same
recorder, shortening the recording to the first 150 ms.

```python
import sys
from types import SimpleNamespace
sys.path[:0] = ["benchmarks/physics-small", "../twister-capper/scripts/spider"]
import run
from spider_mujoco_contacts import record

settings = SimpleNamespace(DURATION=.150, FEET=run.FEET, HIP=run.HIP)
for h in (1.25e-5, 6.25e-6):
    d = record(settings, run.MODEL, "hold", h, contact_time_constant=.002)
    print(h, -1000*d["contact_gap"].min(), d["normal_force"].sum(axis=1).max(),
          d["normal_impulse"].sum())
```
