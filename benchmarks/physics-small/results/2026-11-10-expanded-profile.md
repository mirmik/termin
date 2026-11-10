# Expanded small-physics profile — 2026-11-10

Completion of the measurement scope in #3764 after the [CRBA](2026-11-10-crba.md) and [velocity-kinematics](2026-11-10-velocity-kinematics.md) optimizations. This pass changes only the benchmark and runner, not the physics algorithms.

## Reproduction

AMD Ryzen AI MAX+ 395, Linux x86-64, CPU 0; Release. SDK runtime source is `575c194e5`. Core SDK hashes match the preceding verified velocity-kinematics build. The installed collision, inspect and scene libraries are also hashed; `ldd` confirms all Termin libraries resolve from this workspace SDK. All benchmark source files and compiler caches are recorded in [the raw JSON](2026-11-10-expanded.json).

```sh
task benchmark:physics-small -- --cpu 0 --warmups 100 --repeats 11 --sdk-build-cache build/Release/CMakeCache.txt --output build/benchmarks/physics-small/expanded.json
task test -- --no-python
```

1000 steps/operations per trial, 100 warmup trials and 11 measured trials. Solver replay uses one warmup plus 11 measured passes over the already recorded 1000-step trajectory. Timing, recording and allocation counting run separately. Fixtures, analytic checks and limits of interpretation are described in [the README](../README.md).

## Dynamics and controller

Times below are median microseconds; ranges are min–max. The controller holds the state fixed, uses a fully actuated posture task and a primed primal warm start. Its solve includes linearization, M/bias and HQP. It is not a closed-loop dynamics timing.

| DOF | Dynamics step | Controller solve | C++ new requests/step | Requested bytes/step |
| --- | ---: | ---: | ---: | ---: |
| 2 | 5.275 [5.269–5.839] | 4.856 [4.814–4.871] | 31.610 | 3176.04 |
| 6 | 14.955 [14.864–15.482] | 9.933 [9.843–9.983] | 36.090 | 9234.28 |
| 12 | 34.022 [33.895–34.516] | 22.850 [22.723–23.389] | 37.365 | 18381.16 |
| 24 | 91.405 [91.289–91.658] | 63.598 [62.978–64.106] | 38.685 | 37199.08 |

Allocation figures count successful C++ new requests during the step only. Direct malloc, including Eigen matrix buffers, is excluded. These are not total heap traffic, live/peak memory or allocation time. A separate ELF executable verifies SDK symbol interposition and reproduces the same trajectory without hooks in the throughput executable.

## Solver replay

The real evolving M/load pairs are recorded at each acceleration assembly, with the applied initial/final accelerations. Replay follows the public uncached initial solve and constructs a new endpoint cache for every physical step; it verifies exact matrix reuse and the same factorization/reuse counts.

Values are cumulative microseconds **per physical step**, not per solver call. Cold solves include checks, copies and decomposition; reused solves include checks, copies and backsolves. These are not isolated eigensolver or validation timers. Endpoint adapter allocations/validation are excluded because replay gradient/output buffers are preallocated. Recording, residual-oracle checks and JSON output are outside replay timers.

| DOF | Initial public solve | Endpoint cold solve | Endpoint reused solves | Setup + cache lifecycle | Measured subtotal |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 0.592 | 0.548 | 0.700 | 0.117 | 1.959 |
| 6 | 1.978 | 1.941 | 1.637 | 0.140 | 5.698 |
| 12 | 5.738 | 5.702 | 4.288 | 0.168 | 15.895 |
| 24 | 20.491 | 20.323 | 13.952 | 0.224 | 55.053 |

At 24 DOF this resolves the previously unexplained ~55 µs into about 40.8 µs for the two cold solves and 14.0 µs for the 3.937 reused solves per step. Replay changes cache/memory locality and omits some adapter work, so its subtotal is explanatory evidence, not an additive subtraction from the live-step timer. No pure factorization or allocation-time claim follows from this measurement.

Live 24-DOF instrumented stages: total 91.99 µs, assembly with M rebuild 19.53 µs, cached-M assembly 13.76 µs, velocity updates 2.35 µs, configuration updates 1.94 µs. Public QP code still forms an identity nullspace and performs general nullspace matrix products for zero equalities; this is a concrete next optimization candidate, not a demonstrated share of the cold solve time.

## Collision and complete contact step

The fixture is a two-prismatic slider (M=diag(2,1)) with a sphere and floor, gravity -9.81 along Y, μ=0.5 and initial horizontal speed 1.0. It starts with 1e-6 m penetration. Real CollisionWorld queries supply witnesses, and the existing live-pair cache maintains support at exact touching. This exercises sliding then sticking, not contact separation.

- Full query → contact refresh → dynamics pipeline: 40.471 µs [39.699–41.464].
- Fixed-penetration BVH/narrow-phase query: 0.113 µs.
- Separate instrumented evolving pipeline: query 0.107 µs, contact refresh 0.215 µs, dynamics 42.107 µs; total 42.606 µs. Profiling includes clocks and extra energy checks, so it is intentionally distinct from throughput.
- 1000 steps: 407 sliding steps, then sticking; only the initial geometric query produces penetration, with contact persistence handling subsequent touching steps. Final q=(0.20387383, 0.25), v=(0,0). Friction work sum is −1.0 J.
- Analytic speed max(0,1−μgt/2), displacement with O(dt²) discrete-stop tolerance, support height, nonpenetration and energy dissipation all pass.
- The independent one-contact friction solve remains 11.715 µs; it is a different fixture, not a subtractable portion of the pipeline.

## Verification and follow-ups

- All chain final q/v, initial M/bias and solver/assembly counters exactly match the preceding velocity-kinematics result. Recording/profiling/allocation probes reproduce throughput trajectories exactly.
- Replay applied accelerations match exactly; maximum scaled M*a−load residual is 2.33e-14 or less. Controller acceleration oracle errors are zero; maximum absolute RNEA effort difference is 9.1e-13.
- Both the 10-step smoke and full 1000-step extended benchmark pass all embedded oracles. `task test -- --no-python` passes **271/271 CTest registrations**, with loopback sockets allowed. Python runner syntax and `git diff --check` pass.
- SDK runtime was unchanged in this pass; it retains the preceding successful full SDK build and ABI/import verification. Python test suites and Windows execution were not run. Allocation probing is Linux-only.
- #3766 (Ready): remove unnecessary identity-nullspace work from unconstrained equality QPs while preserving spectral classification and diagnostics.
- #3767 (Ready): caller-owned RNEA/CRBA workspace, measured against both allocation traffic and whole-step time. A drop in allocation counts alone is not evidence of a speedup.
- Complete malloc/Eigen allocation counts and pure factorization/check timings remain measurement limitations, not measured results. They are not needed to attribute the dominant current solve cost or to claim the earlier verified speedups.
