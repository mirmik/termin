# Small-system native physics benchmark

Recorded experiment: [CRBA before/after, 2026-11-10](results/2026-11-10-crba.md).
Follow-up: [velocity-only kinematics, 2026-11-10](results/2026-11-10-velocity-kinematics.md).
Complete profile: [controller, collision/contact, solver replay and allocations](results/2026-11-10-expanded-profile.md).

Build the SDK with `task build`, then run from the repository root:

```sh
task benchmark:physics-small -- --cpu 0 --sdk-build-cache build/Release/CMakeCache.txt --output build/benchmarks/physics-small/before.json
```

After an SDK rebuild, repeat with the same CPU and arguments and another output
file. `--cpu` is Linux-only; choose a CPU in the process's allowed affinity mask.
On other platforms set affinity externally. The runner itself is Python, but all
measured loops execute in C++ against installed SDK libraries. The default is
1000 operations per trial, one warmup trial and seven measured trials. Model
creation and final-output serialization are outside the timer.

The JSON contains raw samples, median/min/max, full final joint positions and
velocities, initial mass/bias arrays, counters, SDK library SHA-256 hashes, source
revision and dirty status, CPU/affinity, all benchmark C++ source hashes, and the benchmark CMake cache. Checkout
revision is **not** asserted to be the installed SDK revision: build the SDK first
and retain its build log when using the result as evidence. Pass
`--sdk-build-cache` to preserve the SDK compiler/build configuration as well. Library hashes identify
which binaries were measured. This command builds only the benchmark consumer,
not the SDK.

## Cases and interpretation

- Fixed-base serial chains at 2, 6, 12 and 24 DOF. Adjacent joint frames are 0.3 m
  apart, with alternating Y/Z revolute axes. Each link has mass 1 kg, COM
  `(0.15,0,0)` and principal inertia `(0.02,0.025,0.03)`. Initial joint angles
  alternate `0.2/-0.15` radians; initial velocities are zero. Gravity is
  `(0,0,-9.81)` and the time step is 0.001 s. No contacts, joint limits, damping,
  controller, Python callbacks or rendering are included in the chain step.
- `mass_matrix` and `bias` are separate fixed-configuration microbenchmarks. Bias
  uses alternating joint velocities `0.4/-0.3` and zero acceleration. Output
  storage is prewarmed. These measurements are **not additive stage times** for
  the evolving trajectory. The assembly counters measure actual calls during
  the step, while multiplication by kernel times is only an estimate.
- A separate instrumented chain trial forwards calls through a contribution
  wrapper and records assembly with/without mass rebuilding, velocity updates,
  and configuration updates. Assembly with a mass rebuild also includes bias and
  block assembly. The remaining total includes QP solves, checks, other lifecycle
  work and instrumentation overhead; it is not a pure factorization timer.
  Instrumentation is absent from the throughput trials. The wrapper must produce
  exactly the same final trajectory as the uninstrumented run.
- A third, untimed chain pass records the actual mass/load equations. Solver
  replay uses the public uncached initial solve and a fresh endpoint cache for
  every physical step, checking residuals, applied accelerations and cache
  counters. It reports initial solve, cold endpoint solve, reused endpoint
  solves, gradient setup and cache lifecycle separately. Both cold and reused
  solves include validation and copies; these are **not** pure factorization or
  pure validation timings. Endpoint adapter allocations/checks are excluded;
  endpoint gradient/output buffers in replay are preallocated. Replay uses one
  warmup and the requested number of measured trials. All values are accumulated
  per physical step, including the time of every reused solve in that step.
- The contact case is one three-DOF sliding contact with identity mass, incoming
  tangential velocity 1, normal impulse 1 and friction coefficient 0.5. It measures
  `solve_contact_friction` only and checks the analytic outgoing velocity 0.5 and
  negative friction work. It measures only the friction solve; the following
  cases measure the wider pipeline separately.
- The controller case uses `InverseDynamicsHqpController3D` on each 2/6/12/24-DOF
  chain, with a single all-joint posture task, nonzero velocities and gravity.
  It holds the state fixed and primes the primal warm start before each trial.
  The complete `solve` is timed, including task linearization, M/bias and HQP;
  model/task construction is excluded. With full actuation and no bounds, the
  commanded acceleration has an analytic oracle and RNEA independently checks
  the effort. This is a controller microbenchmark, not a closed-loop trajectory.
- The full contact pipeline uses a two-prismatic-DOF slider with M=diag(2,1),
  a sphere of radius 0.25 m and a static floor box. Gravity is -9.81 along Y,
  initial horizontal speed is 1 m/s, and friction coefficient is 0.5. The genuine
  `CollisionWorld` BVH query updates the sphere pose, finds witnesses and supplies
  `ContactSet3DContribution` before each dynamics step. The known sphere/floor
  pair remains live: initial 1e-6 m penetration seeds the contact, and the existing
  contact cache maintains support at exact touching when the geometric query
  emits no penetrating pair. This fixture does not exercise contact separation.
  Throughput covers query + contact refresh + complete dynamics step; a separate
  trial times those stages and must reproduce the same trajectory. Analytic
  horizontal deceleration is μg/2, followed by sticking. Checks cover speed,
  displacement (discrete-stop tolerance), support height, penetration, friction
  work and energy. A separate fixed-penetration query timing always exercises
  narrow phase; it cannot be substituted for the evolving query-stage time.

## Allocation probe

On Linux, the runner also builds and executes `physics_small_allocations` with
ELF symbol interposition. It counts successful C++ `new` requests and requested
bytes only around `DynamicsSystem::step`. Model setup is excluded. The probe is
a separate executable, so its global allocation hooks never affect throughput
timings. It verifies SDK interposition with the current RNEA temporary buffers,
and its final states must match an uncounted run and the throughput executable.

Counts **exclude direct malloc calls, including Eigen's matrix buffers**. They
are neither total heap traffic nor live/peak memory and provide no allocation
timings. If RNEA acquires a workspace, replace the explicit interposition
self-check rather than silently accepting a zero count. Other platforms report
the probe unavailable; native timing cases remain usable there, but have only
been verified on Linux.

The benchmark checks all solver return statuses and deterministic trajectories
across repetitions. Compare final arrays and initial mass/bias between versions;
performance results alone do not establish physical accuracy. Run regression,
oracle, conservation, contact/friction and rollback tests through `task test` for
runtime changes. Wall-clock measurements remain sensitive to CPU frequency,
thermal state and concurrent workload even with affinity fixed.
For small optimizations, use `--warmups 100 --repeats 11`: earlier short warmups
showed frequency-ramp effects in the first 2-DOF case. Match these options between
versions. The extended suite performs additional controller/contact/replay runs,
so it takes longer than the original dynamics-only harness.
