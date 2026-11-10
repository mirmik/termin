# Velocity-only kinematics — 2026-11-10

Follow-up #3765 to the [CRBA optimization](2026-11-10-crba.md). Endpoint velocity iterations and velocity projections now update local velocities using the existing configuration transforms. Configuration changes and rollback still rebuild all kinematics; public setters retain their full-update contract. Finite checks, solver tolerances and integration are preserved.

## Reproduction and provenance

AMD Ryzen AI MAX+ 395, Linux x86-64, CPU 0, Release (`-O3 -DNDEBUG`). Baseline source is `b60df0bc7`, with SDK library hashes identical to the verified CRBA build. After is that revision plus the velocity-kinematics patch. Benchmark native source hashes match. Only robotics and physics-qopt library hashes changed; base and QOpt are identical.

Each trial contains 1000 steps at dt=0.001 s, starting from the same initial state. This pair uses **100 warmup trials and 11 measured trials**. Preliminary shorter warmups showed CPU frequency ramp effects on 2 DOF, so both final measurements use the longer warmup. All sample ranges below belong to this final pair.

```sh
TERMIN_PYTHON_RUNTIME_OFFLINE=1 task build
task benchmark:physics-small -- --cpu 0 --warmups 100 --repeats 11 --sdk-build-cache build/Release/CMakeCache.txt --output build/benchmarks/physics-small/results.json
task test -- --no-python
```

Raw evidence: [before](2026-11-10-velocity-before.json), [after](2026-11-10-velocity-after.json). These include SDK/compiler metadata, hashes, raw samples, numerical arrays, counters and the separate instrumented profile.

## Results

Times are microseconds; ranges are measured min–max. The velocity-stage times come from the separate instrumented trial, not from the throughput trials.

| DOF | Step before | Step after | Time reduction | Velocity stage before → after |
| --- | ---: | ---: | ---: | ---: |
| 2 | 6.152 [6.120–6.199] | 5.367 [5.355–5.395] | 12.8% | 1.224 → 0.304 |
| 6 | 17.724 [17.689–17.850] | 14.866 [14.840–15.079] | 16.1% | 3.689 → 0.699 |
| 12 | 39.695 [39.641–39.781] | 33.772 [33.678–33.852] | 14.9% | 7.389 → 1.306 |
| 24 | 104.408 [104.238–104.616] | 92.007 [91.892–92.581] | 11.9% | 15.183 → 2.353 |

All saved final coordinates/velocities, initial mass/bias arrays, assembly counters and endpoint factorization/reuse counters match exactly between builds. The contact solver output also matches exactly; its median changes from 11.746 to 11.760 µs. No contact-solver speedup is claimed.

At 24 DOF, the instrumented total is 92.46 µs: assembly with mass rebuild 19.77 µs, cached-mass assembly 13.74 µs, velocity update 2.35 µs and configuration update 1.95 µs. The residual ~54.65 µs still groups QP work, validation, other lifecycle work and instrumentation. Controller/collision queries and full contact-dynamics profiling remain outside this benchmark; see #3764.

## Verification

- `task test -- --no-python`: **271/271 CTest registrations passed**, including robotics, conservation, contact/friction, rollback and FEM. As in the preceding pass, tests ran with loopback sockets allowed.
- Full offline `task build` passed, including native ABI and SDK import checks. Python test suites and Windows execution were not run.
- New adapter-vs-full-update tests cover fixed/floating/base-only models, branched revolute/prismatic units, point/frame velocity and bias/Jacobians, unchanged poses, repeated velocity projections, later configuration/base-pose changes, trial configurations, rollback and NaN/Inf rejection with rollback recovery.
- Production review verified that every current coordinate/base-pose mutation and rollback still calls the full update. No extra state/cache invalidation flags or public setters were introduced.
