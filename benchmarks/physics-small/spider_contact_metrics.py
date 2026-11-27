"""Summarize a four-second spider trajectory from either contact recorder."""

import argparse
import json

import numpy as np


def summarize(trace):
    t = trace["t"]
    feet = trace["feet"]
    gap = trace["contact_gap"]
    force = trace["normal_force"]
    if not all(np.all(np.isfinite(x)) for x in (t, feet, gap, force, trace["body"])):
        raise ValueError("Nonfinite spider trajectory")
    start, = np.flatnonzero(np.isclose(t, 1., atol=1e-10, rtol=0.))
    stance = feet[start:, :, :2] - feet[start, :, :2]
    liftoff = {}
    for index, name in enumerate(trace["foot_names"]):
        clear = np.flatnonzero(gap[start+1:, index] > 1e-5)
        if clear.size:
            liftoff[str(name)] = float(t[start+1+clear[0]])
    return {
        "max_foot_center_drift_mm": float(np.max(np.linalg.norm(stance, axis=2)) * 1000.),
        "peak_landing_penetration_mm": float(-min(0., gap[:start+1].min()) * 1000.),
        "peak_landing_foot_load_N": float(force[:start+1].sum(axis=1).max()),
        "mean_support_N": float(force[start+1:].sum(axis=1).mean()),
        "final_body_height_m": float(trace["body"][-1, 2]),
        "first_clearance_above_10um_after_1s": liftoff,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", nargs="+", help="NPZ files from the Termin or MuJoCo recorder")
    results = {}
    for path in parser.parse_args().traces:
        with np.load(path) as trace:
            results[path] = summarize(trace)
    print(json.dumps(results, indent=2))
