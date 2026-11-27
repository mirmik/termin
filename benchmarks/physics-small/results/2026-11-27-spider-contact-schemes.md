# One contact configuration per spider step

The reference is tagged `physics-contact-baseline-2026-11-27` at
`60e07c872d92c709e4d5194f2bec50e5bceab2af`. The scene and controller are
`termin-spider-control@b2ccb29` and `twister-capper@227a485`. The new mode
is opt-in. It did **not** maintain standing foot positions accurately enough
to replace the reference on this robot.

## Experiment

Both Termin modes integrate free motion, predict the endpoint, project its
position against the normal constraints, and solve the endpoint velocities
and contact impulses. The default mode applies a half-step correction to the
configuration from the friction-induced velocity change, then solves on that
geometry. The experimental mode accepts the projected predicted position and
the post-contact velocity together. It has one normal velocity projection
and one coupled friction solve per loaded step. The six-sided friction
polygon, solver tolerances, controller and time step are shared.

The tagged SDK and the default mode of the experimental SDK produced
byte-identical recorded arrays in all eight scenarios, including committed
per-foot contact telemetry. At 1 ms the ordinary four-second sweep had
3,899 contact steps, with 7,798 friction passes in the reference and 3,899
in the experiment. The two modes also matched bit for bit through the first
80 ms of free fall.

## Stance, landing and liftoff

Drift below is the maximum horizontal displacement of any spherical foot
centre from its position at 1 s, over the following three seconds. It includes
rolling. The landing penetration is a separate geometric measurement of the
sphere against the ground at accepted poses, including poses before the solver
first reports a contact. MuJoCo 3.15.0 uses the same robot with NoSlip 10.

| Measurement, 1 ms | Corrected endpoint | Predicted endpoint | MuJoCo |
| --- | ---: | ---: | ---: |
| Drift in hold, mm | 0.0020 | 72.899 | 0.0368 |
| Drift with the 5° hip sweep, mm | 0.1421 | 79.083 | 0.1363 |
| Drift in the sweep at μ = 0.15, mm | 61.645 | 53.150 | 58.757 |
| Maximum penetration during landing, mm | 0.03591 | 0.03591 | 7.777 |
| Peak total normal force during landing, N | 3,968.65 | 3,967.47 | 690.92 |
| Final body height in hold, m | 1.32891 | 1.29591 | 1.32798 |
| Positive ramp, middle left liftoff, s | 1.081 | 1.085 | 1.092 |
| Negative ramp, rear left liftoff, s | 1.137 | 1.153 | 1.151 |
| Negative ramp, front left liftoff, s | 1.154 | 1.176 | 1.166 |

The first interval with load ended at 0.102 s in all three 1 ms runs. Liftoff
uses a geometric clearance of 10 µm after 1 s. The impulse from the final
accepted contact solve divided by the step duration gives the Termin normal
force. MuJoCo forces are projected onto the upward ground normal. Mean loads
over (1, 4] s in the hip sweep, in newtons, are shown below.

| Foot | Corrected endpoint | Predicted endpoint | MuJoCo |
| --- | ---: | ---: | ---: |
| Front left | 29.679 | 29.406 | 29.623 |
| Front right | 27.667 | 27.592 | 27.670 |
| Middle left | 21.436 | 21.695 | 21.527 |
| Middle right | 24.764 | 24.795 | 24.771 |
| Rear left | 24.409 | 24.368 | 24.356 |
| Rear right | 22.348 | 22.454 | 22.343 |

The RMS difference between the two Termin load histories over all feet and
samples was 0.081 N in hold and 0.198 N in the sweep. Thus a close vertical
load history can coexist with centimetres of horizontal drift.

## Why the feet move

In hold, both Termin modes reported zero sliding flags. For the experimental
mode the time integral of post-solve tangential speed for each loaded contact
was below 0.00027 mm between 1 and 4 s. This velocity is evaluated after
the impulse. The position already includes a tangential displacement from
the free-motion predictor.

To separate slip from foot rolling, the probe follows the same material
points on the foot and ground from the start to the end of each loaded step.
It projects their relative displacement onto the tangent plane and sums its
length over (1, 4] s. In hold, the six sums range from 0.00125 to 0.00196 mm
in the reference and from 56.452 to 74.620 mm in the experiment. In the hip
sweep the ranges are 0.00139–0.00247 mm and 57.866–80.936 mm respectively.

A 1 kg body on a plane isolates that effect. Starting from rest, a horizontal
force of 1 N is below the static friction capacity (μ = 0.5, g = 9.81 m/s²).
The predicted position advances by ½ a h² per step while the solved tangent
velocity is zero. After one physical second the measured displacement was
0.25, 0.50 and 1.00 mm for steps of 0.5, 1 and 2 ms respectively. The
corrected scheme gave zero in each case. This check isolates a translation
without foot rolling.

## Time per step and per second of simulated motion

On a Ryzen AI MAX+ 395 (Linux, CPU 2, Release SDK), each fresh process ran the
hip sweep for one second of warm-up and three timed seconds. The timer includes
setting the target and advancing the scene, including forward kinematics on
the MuJoCo side. State sampling every 100 steps and the contact probe are
outside the timing. The table reports medians from seven runs per Termin mode,
alternating their order, and three runs with MuJoCo NoSlip 10.

| Solver | Step, ms | Time/step, µs | Wall ms/simulated s | Sweep foot-centre drift, mm |
| --- | ---: | ---: | ---: | ---: |
| Corrected | 0.5 | 165.82 | 331.65 | 0.142 |
| Predicted | 0.5 | 107.76 | 215.52 | 49.279 |
| Corrected | 1 | 172.00 | 172.00 | 0.142 |
| Predicted | 1 | 107.98 | 107.98 | 79.083 |
| MuJoCo | 1 | 13.42 | 13.42 | 0.136 |
| Corrected | 2 | 177.08 | 88.54 | 0.147 |
| Predicted | 2 | 113.60 | 56.80 | 100.556 |

At 1 ms the single-pass scheme saves 37.2% of wall time. The observed ranges
were 171.53–172.36 µs for corrected, 107.50–108.93 µs for predicted and
13.41–13.43 µs for MuJoCo. Halving the experimental time step costs 25.3%
more per simulated second than the 1 ms reference while still allowing
49 mm of foot-centre drift. In a separate 5 ms stress run the robot tumbled
in both Termin modes, ending with the body at 0.311 and 0.321 m respectively.

The reference remains the production choice for stance. The next experiment
can include the last accepted tangential reaction of a persistent contact in
the position predictor. Check detachment and the transition to sliding as well
as sticking before interpreting a speedup.

## Reproduction

Build each Termin checkout with `task build`. Keep the two robot checkouts
alongside Termin at the revisions above. The Termin runner's module docstring
contains the Linux probe build and recording commands. Use the probe in
quality runs only, compile it against the SDK under test, and select a CPU
available on the machine for timing. Use `--case hold`, `sweep`, `slide`,
`plus` or `minus` for the 1 ms recordings and repeat `sweep` at 0.5, 2 and
5 ms. The native contact test includes the constant-force case.

- [Termin quality and timing runner](../spider_contact_schemes.py)
- [Material-point contact probe](../spider_contact_observer.cpp)
- [MuJoCo force and gap recorder](../spider_mujoco_contacts.py)
