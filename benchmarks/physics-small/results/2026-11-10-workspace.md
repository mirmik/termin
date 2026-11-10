# Caller-owned RNEA/CRBA workspace — 2026-11-10

Task #3767 introduces `Articulation3DWorkspace` and makes `Articulation3DDynamicsContribution` reserve and reuse its scratch storage. RNEA overwrites three unit-local screw buffers; CRBA overwrites one composite-inertia buffer. The workspace holds no cached model values and can be reused sequentially across different trees. Existing convenience overloads delegate to the same algorithms with a local workspace. Independent callers use independent workspaces; the const model contains no mutable scratch.

The shared RNEA entry also now rejects invalid models before traversing parent indices, with a logged failure. Previously that entry lacked the model-validity guard already present in CRBA. Invalid dimensions/non-finite input and non-finite effort now produce logs as well.

## Reproduction

AMD Ryzen AI MAX+ 395, Linux x86-64, CPU 0, Release. Before runtime matches the preceding verified unconstrained-QP build. Both runs record checkout `e47be922b`; the after run uses the workspace changes in the working tree and a full rebuilt SDK. Only `libtermin_robotics.so.0.1.0` and `libtermin_physics_qopt.so.0.1.0` changed among tracked SDK libraries.

```sh
task test -- --no-python
TERMIN_PYTHON_RUNTIME_OFFLINE=1 task build
task benchmark:physics-small -- --cpu 0 --warmups 100 --repeats 11 --sdk-build-cache build/Release/CMakeCache.txt --output /tmp/termin-3767-after.json
```

The before benchmark used the same arguments and a separate output path, before modifying the SDK. Each trial has 1000 operations, with 100 warmup trials and 11 measured trials. Replay uses one warmup and 11 measured passes over recorded equations. Raw samples, SDK hashes and compiler configuration: [before](2026-11-10-workspace-before.json), [after](2026-11-10-workspace-after.json).

All throughput benchmark source hashes are identical. Only the separate `allocation_probe.cpp` changed: it retains the positive DSO interposition check through the allocating RNEA wrapper and adds a zero-allocation assertion for 100 RNEA/CRBA pairs using a reserved workspace and preallocated outputs. Counting includes the first call after reserve. The outputs are checked against the convenience overloads.

## Whole-step timing and allocation traffic

Times are median microseconds, with min–max measured ranges. Allocation counts come from a separate executable and never instrument the throughput run.

| DOF | Dynamics before | Dynamics after | Median time reduction | C++ new requests/step before → after | Requested bytes/step before → after |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 4.612 [4.602–4.652] | 4.540 [4.531–4.880] | 1.6% | 31.610 → 16.044 | 3176.040 → 721.704 |
| 6 | 13.300 [13.287–13.341] | 12.856 [12.826–12.865] | 3.3% | 36.090 → 17.836 | 9234.280 → 1097.128 |
| 12 | 29.593 [29.568–29.627] | 28.771 [28.625–28.857] | 2.8% | 37.365 → 18.346 | 18381.160 → 1666.216 |
| 24 | 77.205 [77.046–77.412] | 74.467 [74.408–74.674] | 3.5% | 38.685 → 18.874 | 37199.080 → 2856.808 |

At 24 DOF this removes 51.2% of counted requests and 92.3% of counted requested bytes. The reduction exactly matches three RNEA buffers per bias evaluation and one CRBA buffer per mass evaluation: `3 * 5.937 + 2 = 19.811` requests and `24 * (3 * 48 * 5.937 + 288 * 2) = 34342.272` bytes per physical step. The adapter retains scratch capacity instead of repeatedly allocating it.

The probe counts successful C++ new requests, **not direct malloc/Eigen buffers, peak/live memory or allocation time**. Its positive control observes three requests at every tested size, and each 100-pair workspace check observes zero. Allocation reduction is distinct from the measured 3.5% whole-step reduction. At 2 DOF the timing ranges overlap, so the small median difference is not strong evidence of a speedup. At 6/12/24 DOF the measured ranges do not overlap; these results still describe this machine and these fixtures.

## Other measured paths

The solver replay is a useful unchanged control: its subtotal at 24 DOF is 39.974 → 39.971 µs per physical step, and all sizes change by at most 0.5%. The QOpt binary is unchanged. Initial/cold/reused replay times at 24 DOF are 16.072 → 16.132, 15.970 → 15.910 and 7.651 → 7.611 µs respectively.

The public mass/bias microbenchmarks still call the allocating convenience overloads. At 24 DOF they measure 6.236 → 5.768 and 2.916 → 2.721 µs; these values do not measure the workspace-only path or demonstrate allocation elimination in those wrappers. Controller adoption is outside this change: controller times at 2/6/12/24 DOF are 4.134 → 4.073, 8.538 → 8.464, 18.953 → 18.988 and 50.179 → 49.600 µs. Small changes in these rebuilt paths are not attributed solely to allocation reuse.

The full collision/contact/dynamics pipeline changes from 36.884 to 36.452 µs. Isolated contact solve is 10.823 → 10.761 µs and fixed-penetration collision query is 0.108 → 0.113 µs. These are separate fixtures, not additive components of one timing.

## Correctness and verification

- All common non-timing fields other than the allocation counts/bytes match exactly: chain final q/v, initial M/bias, solver/assembly counters, controller results and oracle errors, contact state/work, allocation-probe final states and replay errors. Replay applied acceleration differences remain zero; maximum scaled equation residual is at most 2.33e-14.
- RNEA/CRBA tests cover fixed/floating/branched/base-only trees, changing state, growing/shrinking workspace use, same-sized models with different topology/inertia, and independent interleaved workspaces. They require exact agreement with convenience overloads and retain the independent `M*a = RNEA(a) - RNEA(0)` and kinetic-energy oracles.
- Invalid RNEA input/model tests preserve output and verify subsequent valid reuse. Invalid-parent and empty-model calls fail before scratch traversal. Prepared workspace calls pass the zero-allocation check with positive SDK interposition controls.
- Final `task test -- --no-python`: **271/271 CTest registrations passed**, with loopback sockets allowed. Full offline `task build` passed, including SDK payload, canonical nanobind ABI and native import verification. The extended benchmark passed every embedded oracle and `git diff --check` passed. Python test suites and Windows execution were not run.

The result supports retaining the caller-owned workspace: it removes the identified scratch traffic and yields a modest measured whole-step improvement without changing the numerical algorithms.
