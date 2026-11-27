# MuJoCo contacts with Termin spider dynamics

The experimental spider uses Termin to compute its articulated mass matrix,
bias forces and sphere/box contacts on every step. MuJoCo 3.15.0 consumes these
inputs and advances the state. At a 1 ms step the native benchmark took
20.63 µs with this combination and 12.89 µs with MuJoCo alone. Both reproduced
the same foot loads and motion through landing, stance, sliding and liftoff.

This Linux benchmark links the installed SDK and MuJoCo wheel. It constructs
the Termin tree from the exported robot model once. MuJoCo owns the generalized
state, actuator evaluation, broad phase, contact Jacobians, elliptic constraint
assembly, mass factorization, Newton solve, NoSlip post-pass and Euler update.
Both libraries update kinematics. Each new integrated state feeds the next
step. The standing spider has 28 velocity coordinates, six loaded feet and 18
contact rows. The regular Termin scene loop, contact persistence and bilateral
FEM constraints are outside the combined timing.

## A loaded frame from the Termin engine

At 1.500 s in the standard 5° hip sweep, capture the accepted floating-base
pose and twist, 22 joint coordinates and velocities, and the next command from
the corrected-endpoint Termin scene. Map by joint name, express the base
linear velocity in world coordinates and keep the angular velocity in the
base frame. Across the six feet, maximum absolute cross-engine discrepancies
were 6.39e-16 m in centre position, 1.21e-17 m/s in centre velocity and
1.33e-15 in the surface-point translational Jacobians.

All six loaded feet in this frame have small positive gaps (0.15–1.73 nm).
At the authored zero margin MuJoCo creates zero contacts. Giving the ground
a 10 nm margin produces six contacts at the original pose. This margin applies
only to the single-frame replay. The keyframe starts with zero cached
acceleration. It contains no solver history from the preceding Termin step.

| CPU 2 stage on the same frame | Median µs |
| --- | ---: |
| Make constraint rows and form islands | 1.006 |
| Project the constraint matrix | 1.139 |
| Compute constraint velocity and reference acceleration | 0.045 |
| Prepared Newton solve with NoSlip disabled | 3.649 |
| Prepared Newton solve with NoSlip enabled | 4.688 |
| Paired increment for NoSlip and mapping forces back | 1.039 |
| Whole MuJoCo forward dynamics, before integration | 11.358 |

Seven trials replayed the captured frame 3,000 times per arm. Forward dynamics
selected one Newton iteration and three NoSlip iterations (limit ten).
Accelerations, row forces and generalized constraint forces from the split
calls matched ordinary `mj_forward` byte for byte in each mode. At this
fixed pose the six-foot normal load was 133.92 N in MuJoCo versus 150.24 N
averaged over the next accepted Termin interval. Identical kinematics permit
different forces under the two contact models.

## Closed-loop throughput

Medians below are from seven trials per mode on a Ryzen AI MAX+ 395,
logical CPU 6. The native loop includes the target, step and endpoint
kinematics. Each trial warms up for one simulated second and measures the
following three. At 1 ms, µs/step also gives wall milliseconds per simulated
second. The quality runs separately compare the Termin mass matrix and bias
with MuJoCo on every step. The timed runs compute mass and bias once.

| Native path | Original 20 ms contact time constant, µs/step | Stiffer 2 ms, µs/step |
| --- | ---: | ---: |
| MuJoCo | 12.89 | 13.12 |
| Termin articulated dynamics, MuJoCo geometry | 20.54 | 20.74 |
| Termin articulated dynamics and foot geometry | 20.63 | 20.84 |

The maximum absolute difference in the supplied mass coefficients was under
1.6e-13 and in bias forces under 1.5e-13 over the five original scenarios.
The per-foot vertical-force RMS discrepancy after 1 s was below 2.7e-12 N.
The geometry callback returned 23,394 sphere/box contacts in the four-second
sweep. With geometry alone changed, the separate Python-driven matched sweep
took 13.54 µs/step versus 13.56 µs for stock MuJoCo on CPU 2.

The frozen Termin engine measured 172.00 µs/step in the earlier scene-level
sweep. That includes scene updates, component synchronization and its two-pass
contact integrator. A run through the real scene entry point is needed to
price the equivalent integration of the new backend. [Frozen baseline and
timing protocol](2026-11-27-spider-contact-schemes.md)

## Accuracy at 1 ms

The combined backend uses the authored zero margin in all trajectories.
Both MuJoCo columns use damping ratio 1 and NoSlip 10. Drift is the maximum
horizontal foot-centre displacement from 1 s over the next three seconds.
Penetration includes the accepted pose just before the first loaded interval.

| Measurement | Termin reference | Combined, 20 ms | Combined, 2 ms |
| --- | ---: | ---: | ---: |
| Hold drift, mm | 0.0020 | 0.0368 | 0.00044 |
| Hip sweep drift, mm | 0.1421 | 0.1363 | 0.1414 |
| Low-friction sweep drift, mm | 61.645 | 58.757 | 56.301 |
| Peak landing penetration, mm | 0.03591 | 7.777 | 0.5313 |
| Peak total foot load, N | 3,968.65 | 690.91 | 4,341.76 |
| Positive ramp, middle left clearance >10 µm, s | 1.081 | 1.092 | 1.078 |
| Negative ramp, rear left clearance >10 µm, s | 1.137 | 1.151 | 1.131 |
| Negative ramp, front left clearance >10 µm, s | 1.154 | 1.166 | 1.145 |

The stiffer setting also produced 42 samples with right rear clearance above
10 µm on the negative ramp (peak 16.0 µm, first crossing at 1.566 s).
In the intermediate pure-MuJoCo control with a 5 ms time constant, landing
penetration was 1.615 mm and peak load was 1,638.53 N. At the 2 ms setting
the maximum penetration occurred at 0.101 s. The first interval with positive
support force ended at 0.102 s. Stiffer response alone cannot undo the
displacement already accepted before contact detection in this landing.

## Reproduction

Use the Release SDK from `task build`, sibling checkouts
`termin-spider-control@b2ccb29` and `twister-capper@227a485`, and the latter's
MuJoCo 3.15.0 Python environment. Run from the Termin root.

1. Follow the [snapshot runner](../spider_termin_snapshot.py) module docstring
   to compile the native reader, capture `frame.json` and generate
   `build/spider-contacts/keyframe.xml`. Repeat with `--ground-margin 0` to
   verify the activation control.
2. Compile and run the [fixed-frame replay](../spider_mujoco_replay.cpp).
3. Follow the [geometry](../spider_mujoco_hybrid.py) and
   [articulated dynamics](../spider_termin_dynamics_mj.py) runners' docstrings
   to build the two shared libraries. Pass both libraries to the dynamics
   runner for the combined trials. Use `quality` for `hold`, `sweep`, `slide`,
   `plus` and `minus`, then `time` for the native timings. Repeat with
   `--contact-time-constant .002`. The [metrics script](../spider_contact_metrics.py)
   reads the generated NPZ files from either engine.

```sh
mjpkg=$(../twister-capper/.venv/bin/python -c 'import mujoco; print(mujoco.__path__[0])')
c++ -O3 -std=c++17 -I"$mjpkg/include" benchmarks/physics-small/spider_mujoco_replay.cpp \
    "$mjpkg/libmujoco.so.3.15.0" -Wl,-rpath,"$mjpkg" -o build/spider-contacts/replay
taskset -c 2 build/spider-contacts/replay build/spider-contacts/keyframe.xml
```

MuJoCo dispatches the selected constraint solver and NoSlip in
[forward dynamics](https://github.com/google-deepmind/mujoco/blob/3.15.0/src/engine/engine_forward.c).
The implementations are in [engine_solver.c](https://github.com/google-deepmind/mujoco/blob/3.15.0/src/engine/engine_solver.c).
