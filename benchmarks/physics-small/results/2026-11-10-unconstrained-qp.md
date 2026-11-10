# Unconstrained equality QP — 2026-11-10

Task #3766 removes explicit identity-nullspace operations when an equality QP has zero equality rows. The solver directly decomposes the symmetrized Hessian and transforms the gradient/solution through its eigenvectors. It retains the shared spectral rank, negative-curvature, nullspace-descent and residual checks. The constrained solver and public cache contract remain intact.

## Reproduction

AMD Ryzen AI MAX+ 395, Linux x86-64, CPU 0; Release. Both measurements use checkout `05d37e7d5`, with the QOpt implementation and regression tests modified for the after build. The benchmark sources are identical by SHA-256. Of the tracked SDK libraries, only `libtermin_qopt.so.0.1.0` changed. The before SDK hashes exactly match the preceding verified expanded-profile runtime; the after SDK was rebuilt with the command below.

```sh
task test -- --no-python
TERMIN_PYTHON_RUNTIME_OFFLINE=1 task build
task benchmark:physics-small -- --cpu 0 --warmups 100 --repeats 11 --sdk-build-cache build/Release/CMakeCache.txt --output /tmp/termin-3766-after.json
```

The before run used the same benchmark command with a separate output path, before rebuilding the SDK. Each trial has 1000 operations, with 100 warmup trials and 11 measured trials. Replay uses one warmup and 11 measured passes over the recorded trajectory. Raw samples, build configuration and binary/source hashes: [before](2026-11-10-unconstrained-before.json), [after](2026-11-10-unconstrained-after.json).

## Whole-step and controller timings

Median microseconds; the dynamics range is min–max over measured trials. Controller timing includes task linearization, M/bias and HQP at a fixed state with a primed primal warm start.

| DOF | Dynamics before | Dynamics after | Time reduction | Controller before → after |
| --- | ---: | ---: | ---: | ---: |
| 2 | 5.298 [5.289–5.344] | 4.613 [4.600–4.669] | 12.9% | 4.888 → 4.076 |
| 6 | 14.812 [14.756–14.932] | 13.431 [13.393–13.446] | 9.3% | 10.024 → 8.515 |
| 12 | 33.735 [33.703–33.855] | 29.641 [29.587–29.759] | 12.1% | 22.687 → 18.960 |
| 24 | 91.734 [91.580–92.020] | 77.351 [77.292–77.528] | 15.7% | 62.985 → 50.059 |

The isolated friction solve changes from 11.769 to 10.829 µs; the complete collision/contact/dynamics pipeline changes from 39.936 to 36.748 µs. Fixed-penetration collision query is 0.110 → 0.108 µs. These are distinct fixtures, not additive stages of the same timing.

Unchanged mass/bias kernels serve as controls: bias differs by less than 0.3%, while mass is 0.3–2.9% slower in the after run. This bounds interpretation of small timing differences; the whole-step improvements exceed the observed trial ranges. Results describe this machine and these fixtures.

## Solver replay

Median cumulative microseconds **per physical step**; reused cost includes all endpoint cache hits in that step. These timers include validation/copying and solve work, not just eigendecomposition. The subtotal also includes gradient setup and cache lifecycle.

| DOF | Initial public before → after | Endpoint cold before → after | Endpoint reused before → after | Subtotal before → after |
| --- | ---: | ---: | ---: | ---: |
| 2 | 0.592 → 0.403 | 0.548 → 0.360 | 0.703 → 0.445 | 1.959 → 1.323 |
| 6 | 1.966 → 1.557 | 1.928 → 1.549 | 1.574 → 0.983 | 5.595 → 4.226 |
| 12 | 5.679 → 4.635 | 5.633 → 4.541 | 4.210 → 2.265 | 15.671 → 11.605 |
| 24 | 20.567 → 15.991 | 20.423 → 15.965 | 13.745 → 7.614 | 54.995 → 39.853 |

At 24 DOF, the two cold solves take about 22% less time; reused solves take 44.6% less time and the measured subtotal takes 27.5% less time. Replay changes memory locality and excludes some adapter work, so its subtotal must not be subtracted from the whole-step timer to infer an exact remaining cost.

## Correctness and validation

- All non-timing benchmark values compare exactly before/after: chain final q/v, initial M/bias, solver and assembly counters, controller outputs and oracle errors, contact outputs and friction work, and allocation-probe states/counts. Replay acceleration differences remain zero; the maximum scaled equation residual is 2.33e-14 or less.
- New regression cases compare the zero-row specialization with the general path using a redundant zero equality. They cover SPD, singular PSD with consistent/inconsistent gradients, indefinite and near-threshold spectra, cached/uncached solves, zero variables, strided input/output aliasing and constrained/unconstrained cache transitions with Hessian/tolerance invalidation.
- `task test -- --no-python`: **271/271 CTest registrations passed**, including loopback tests with sockets allowed. Full offline `task build` passed, including SDK payload verification, canonical nanobind ABI and native import checks. `git diff --check` passed. Python test suites and Windows execution were not run.
- C++ new requests and requested bytes are unchanged (24 DOF: 38.685 requests and 37199.08 bytes per step). This probe excludes Eigen/direct malloc, so it cannot quantify the removed Eigen temporaries or total heap traffic.

The measured speedup supports retaining the simpler unconstrained algebra. Caller-owned RNEA/CRBA workspace remains a separate follow-up in #3767.
