# Small-system native physics benchmark

Recorded experiment: [CRBA before/after, 2026-11-10](results/2026-11-10-crba.md).

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
revision and dirty status, CPU/affinity, and the benchmark CMake cache. Checkout
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
- The contact case is one three-DOF sliding contact with identity mass, incoming
  tangential velocity 1, normal impulse 1 and friction coefficient 0.5. It measures
  `solve_contact_friction` only and checks the analytic outgoing velocity 0.5 and
  negative friction work. It does **not** measure collision queries, full contact
  dynamics steps, or controllers; these remain separate benchmark extensions.

The benchmark checks all solver return statuses and deterministic trajectories
across repetitions. Compare final arrays and initial mass/bias between versions;
performance results alone do not establish physical accuracy. Run regression,
oracle, conservation, contact/friction and rollback tests through `task test` for
runtime changes. Wall-clock measurements remain sensitive to CPU frequency,
thermal state and concurrent workload even with affinity fixed.
