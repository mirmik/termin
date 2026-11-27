"""Analytic first-contact probes for the optional MuJoCo 3.15 sweep/step library.

From the Termin root, after building the experimental shared library:

    ../twister-capper/.venv/bin/python benchmarks/physics-small/predict_contact_cases.py \
        --library /tmp/termin-predict/step.so --output /tmp/termin-predict/primitives.json

Run with --baseline-only to exercise the independent reference without the C++ library.
"""
import argparse
import ctypes as ct
import json
import math
from contextlib import contextmanager
from pathlib import Path

import mujoco as mj
import numpy as np


DT = .001
GRAVITY = 9.81
RADIUS = .025


class Predictor:
    def __init__(self, library):
        self.lib = ct.CDLL(str(library.resolve()))
        ptr = ct.c_void_p
        self.lib.predict_contact_create.argtypes = [ptr]
        self.lib.predict_contact_create.restype = ptr
        self.lib.predict_contact_destroy.argtypes = [ptr]
        self.lib.predict_contact_destroy.restype = None
        self.lib.predict_contact_step.argtypes = [ptr, ptr]
        self.lib.predict_contact_step.restype = ct.c_int
        self.lib.predict_contact_hits.argtypes = [ptr]
        self.lib.predict_contact_hits.restype = ct.c_int
        self.lib.predict_contact_fraction.argtypes = [ptr, ct.c_int]
        self.lib.predict_contact_fraction.restype = ct.c_double


@contextmanager
def stepper(model, predictor):
    if predictor is None:
        def native_step(data):
            mj.mj_step(model, data)
            return []

        yield native_step
        return

    lib = predictor.lib
    work = lib.predict_contact_create(model._address)
    if not work:
        raise RuntimeError("Cannot create sweep workspace")
    try:
        def predicted_step(data):
            if lib.predict_contact_step(work, data._address):
                raise RuntimeError("Predictive step failed")
            return [lib.predict_contact_fraction(work, i) for i in range(lib.predict_contact_hits(work))]

        yield predicted_step
    finally:
        lib.predict_contact_destroy(work)


def scene(world, gravity):
    return mj.MjModel.from_xml_string(f"""
        <mujoco>
          <option timestep="{DT}" gravity="0 0 {-gravity}" integrator="Euler" solver="Newton"
                  cone="elliptic" noslip_iterations="10"/>
          <default><geom solref=".002 1" friction=".7 0 0" condim="3"/></default>
          <worldbody>{world}</worldbody>
        </mujoco>
    """)


def impulse(model, data):
    wrench = np.zeros(6)
    total = 0.
    for i in range(data.ncon):
        mj.mj_contactForce(model, data, i, wrench)
        total += wrench[0] * DT
    if not np.isfinite(total) or np.any(data.warning.number):
        raise RuntimeError(f"Invalid contact result at {data.time}s")
    return total


def sphere(predictor, phase, velocity=None):
    """Position a sphere so the discrete free step crosses at the requested phase."""
    free_steps = 100
    falling = velocity is None
    gravity = GRAVITY if falling else 0.
    free_speed = gravity * (free_steps + 1) * DT
    height = .0001
    if falling:
        height = gravity * DT**2 * free_steps * (free_steps + 1) / 2 + phase * DT * free_speed
    model = scene(f"""
        <geom type="plane" size="1 1 .05"/>
        <body pos="0 0 {RADIUS+height:.17g}"><freejoint/>
          <geom type="sphere" size="{RADIUS}" mass="1"/>
        </body>""", gravity)
    data = mj.MjData(model)
    if not falling:
        data.qvel[:3] = velocity
    mj.mj_forward(model, data)
    force_intervals = []
    predictions = []
    min_gap = height
    peak_up = 0.
    crossing_gap = None
    crossing_end = None
    impulses = []
    with stepper(model, predictor) as advance:
        for k in range(250 if falling else 10):
            before = float(data.qpos[2] - RADIUS)
            fractions = advance(data)
            after = float(data.qpos[2] - RADIUS)
            value = impulse(model, data)
            impulses.append(value)
            if fractions:
                predictions.append((k, fractions))
            if value > 1e-10:
                force_intervals.append(k)
            if k == free_steps:
                crossing_gap, crossing_end = before, after
            min_gap = min(min_gap, after)
            if falling and k >= free_steps:
                peak_up = max(peak_up, float(data.qvel[2]))
    first = force_intervals[0] if force_intervals else None
    result = dict(
        first_loaded_interval_start_ms=first,
        first_loaded_interval_impulse_Ns=impulses[first] if first is not None else 0.,
        total_impulse_Ns=sum(impulses),
        max_accepted_penetration_mm=-1000. * min(0., min_gap),
        max_upward_velocity_after_crossing_m_s=peak_up if falling else None,
        number_of_forecast_intervals=len(predictions),
        first_forecast_interval_and_fractions=predictions[0] if predictions else None,
    )
    if falling:
        result.update(
            initial_gap_mm=1000. * height,
            ballistic_touch_ms=1000. * math.sqrt(2 * height / gravity),
            free_euler_touch_ms=(free_steps + phase) * DT * 1000.,
            gap_at_crossing_interval_start_mm=1000. * crossing_gap,
            gap_at_crossing_interval_end_mm=1000. * crossing_end,
            crossing_interval_impulse_Ns=impulses[free_steps],
        )
        if predictor is not None:
            if (first != free_steps or not predictions
                    or abs(predictions[0][1][0] - phase) > 1e-6):
                raise AssertionError("Missed the analytic sphere crossing")
    elif predictions or force_intervals:
        raise AssertionError("A sphere moving away from or parallel to the plane acquired contact")
    return result


def sphere_pair(predictor, boost):
    """The separation and impulse are invariant under a shared translation."""
    model = scene("""
        <body pos="-.0251 0 0"><freejoint/><geom type="sphere" size=".025" mass="1"/></body>
        <body pos=" .0251 0 0"><freejoint/><geom type="sphere" size=".025" mass="3"/></body>""", 0.)
    data = mj.MjData(model)
    data.qvel[0] = .3 + boost
    data.qvel[6] = -.1 + boost
    mj.mj_forward(model, data)
    with stepper(model, predictor) as advance:
        fractions = advance(data)
    applied = impulse(model, data)
    momentum_error = float(data.qvel[0] + 3 * data.qvel[6] - 4 * boost)
    if abs(momentum_error) > 1e-11:
        raise AssertionError("Two-body contact changed total momentum")
    if predictor is not None and (len(fractions) != 1 or abs(fractions[0] - .5) > 1e-6 or applied <= 0):
        raise AssertionError("Two moving spheres missed their halfway crossing")
    return dict(boost_m_s=boost, reported_fractions=fractions, impulse_Ns=applied,
                final_gap_mm=float(data.qpos[7] - data.qpos[0] - .05) * 1000.,
                momentum_error_kg_m_s=momentum_error)


# Rotation about Y reduces 3D OBB intersection to planar SAT: the Y intervals
# always overlap. The four face normals of the two rectangles suffice.
A, B = .100, .020
LEDGE_X, LEDGE_Z = .006, .006
PEAK = math.atan2(B, A)
START_ANGLE, STEP_ANGLE = PEAK - .080, .160


def rectangle_separation(angle, center_x, center_z):
    c, s = math.cos(angle), math.sin(angle)
    ac, ass = abs(c), abs(s)
    return max(
        abs(center_x) - LEDGE_X - A * ac - B * ass,
        abs(center_z) - LEDGE_Z - A * ass - B * ac,
        abs(center_x * c - center_z * s) - A - LEDGE_X * ac - LEDGE_Z * ass,
        abs(center_x * s + center_z * c) - B - LEDGE_X * ass - LEDGE_Z * ac,
    )


def edge(predictor, offset, *, hinged=False):
    center_x = math.hypot(A, B) + offset + LEDGE_X
    center_z = .002 - LEDGE_Z

    def gap(theta):
        return rectangle_separation(theta, center_x, center_z)

    midgap = gap(PEAK)
    start_gap, end_gap = gap(START_ANGLE), gap(START_ANGLE + STEP_ANGLE)
    if not start_gap > 0 or not end_gap > 0:
        raise AssertionError("Both free-motion endpoint boxes should be separated")
    oracle_fraction = None
    if offset < 0:
        if midgap >= 0:
            raise AssertionError("The rotated box should intersect the ledge inside the step")
        # Near this first root the ledge's top left corner touches the moving
        # face with normal (cos(theta), -sin(theta)). Find the first transition.
        lo, hi = 0., .5
        for _ in range(55):
            f = (lo + hi) / 2
            if gap(START_ANGLE + f * STEP_ANGLE) > 0:
                lo = f
            else:
                hi = f
        oracle_fraction = hi
    elif not midgap > 0:
        raise AssertionError("The positive-offset ledge must miss the rotation's bounding cylinder")
    slides = "" if hinged else '<joint type="slide" axis="1 0 0"/><joint type="slide" axis="0 0 1"/>'
    model = scene(f"""
        <geom type="box" pos="{center_x} 0 {center_z}" size="{LEDGE_X} .015 {LEDGE_Z}"/>
        <body>{slides}<joint type="hinge" axis="0 1 0"/>
          <geom type="box" size="{A} .01 {B}" mass="1"/>
        </body>""", 0.)
    data = mj.MjData(model)
    data.qpos[-1], data.qvel[-1] = START_ANGLE, STEP_ANGLE / DT
    mj.mj_forward(model, data)
    peak_inside, peak_endpoint, total = 0., 0., 0.
    first_fraction = None
    replay = None

    def committed_gap(pose):
        if hinged:
            return gap(pose[0])
        x, z, angle = pose
        return rectangle_separation(angle, center_x - x, center_z - z)

    with stepper(model, predictor) as advance:
        for k in range(8):
            before = data.qpos.copy()
            if hinged:
                # Hold enough state to replay any outlier with ordinary mj_step.
                old_data = mj.MjData(model)
                mj.mj_copyData(old_data, model, data)
            fractions = advance(data)
            after = data.qpos.copy()
            value = impulse(model, data)
            total += value
            if hinged and value > 1e6 and replay is None:
                mj.mj_step(model, old_data)
                replay = dict(interval=k, predicted_rows=len(fractions), contacts=data.ncon,
                              impulse_Ns=value, native_from_same_state_Ns=impulse(model, old_data))
            # Euler traverses each accepted (translation, hinge-angle) interval
            # at its constant end-step speed. Check between the accepted poses.
            sampled_gap = min(committed_gap(before + f * (after - before)) for f in np.linspace(0., 1., 257))
            peak_inside = max(peak_inside, -sampled_gap)
            peak_endpoint = max(peak_endpoint, -committed_gap(after))
            if k == 0:
                first_fraction = fractions[0] if fractions else None
                first_impulse, first_omega = value, float(data.qvel[-1])
    if offset > 0 and (first_fraction is not None or abs(total) > 1e-10):
        raise AssertionError("The positive-clearance near miss produced a contact response")
    if offset < 0 and predictor is not None:
        if first_fraction is None or abs(first_fraction - oracle_fraction) > 1e-5 or first_impulse <= 0:
            raise AssertionError("Missed the independently located transient box crossing")
    return dict(
        free_SAT_start_mm=1000. * start_gap,
        free_SAT_mid_mm=1000. * midgap,
        free_SAT_end_mm=1000. * end_gap,
        oracle_first_fraction=oracle_fraction,
        reported_first_fraction=first_fraction,
        first_step_impulse_Ns=first_impulse,
        total_impulse_Ns=total,
        first_step_end_angular_speed_rad_s=first_omega,
        max_endpoint_overlap_mm=1000. * peak_endpoint,
        max_sampled_within_step_overlap_mm=1000. * peak_inside,
        extreme_load_replay=replay,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--library", type=Path)
    mode.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    variants = {"native": None}
    if args.library:
        variants["predictive"] = Predictor(args.library)
    results = {}
    for name, predictor in variants.items():
        spheres = [sphere_pair(predictor, boost) for boost in (0., -2., 7.)]
        np.testing.assert_allclose([r["impulse_Ns"] for r in spheres], spheres[0]["impulse_Ns"], atol=1e-10, rtol=0)
        results[name] = {
            "drop": [sphere(predictor, p) for p in (.10, .45, .90)],
            "separating": sphere(predictor, 0., velocity=(0., 0., .25)),
            "parallel": sphere(predictor, 0., velocity=(1., 0., 0.)),
            "two_spheres": spheres,
            "rotating_hit": edge(predictor, -.0001),
            "rotating_miss": edge(predictor, .0001),
            "hinged_hit_stress": edge(predictor, -.0001, hinged=True),
        }
    output = json.dumps(results, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(output + "\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
