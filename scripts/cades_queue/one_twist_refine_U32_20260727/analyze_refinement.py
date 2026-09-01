#!/usr/bin/env python3
"""Analyze the one-twist U=32 midpoint and halve its transition bracket."""

from __future__ import print_function

import csv
import os
import sys


RESULT = (
    "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/"
    "L4x4Nup8Ndn8U32V8.015tp0f2x8Q0x0_obs.dat"
)
HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.join(HERE, "analysis")


def parse_result(path):
    values = {}
    complete = False
    with open(path) as handle:
        for line in handle:
            fields = line.strip().split()
            if len(fields) >= 2:
                values[fields[0]] = fields[1]
            if fields == ["status", "COMPLETE"]:
                complete = True
    if not complete:
        raise RuntimeError("Result does not contain standalone status COMPLETE.")
    return values


def write_csv(path, rows, fields):
    with open(path, "w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not os.path.isfile(RESULT):
        print("Missing result: {}".format(RESULT), file=sys.stderr)
        return 2
    values = parse_result(RESULT)
    D = float(values["<ni_upni_dn>"])
    phase = "charge" if D > 0.25 else "Mott"
    if phase == "Mott":
        v_mott, v_charge = 8.015, 8.020
    else:
        v_mott, v_charge = 8.010, 8.015

    midpoint = 0.5 * (v_mott + v_charge)
    halfwidth = 0.5 * (v_charge - v_mott)
    observable = {
        "U": 32,
        "V": 8.015,
        "kx": 2,
        "ky": 8,
        "double_occupancy": D,
        "mCDW2_pipi": float(values["<mCDW2_pipi>"]),
        "C1_NN": float(values["<C1_NN>"]),
        "nn_NN": float(values["<nn_NN>"]),
        "kinetic_per_site": float(values["<Kinetic_per_site>"]),
        "phase": phase,
        "status": "COMPLETE",
        "result": RESULT,
    }
    bracket = {
        "U": 32,
        "V_Mott": v_mott,
        "V_charge": v_charge,
        "V_c_midpoint": midpoint,
        "V_c_halfwidth": halfwidth,
        "V_c_over_U": midpoint / 32.0,
        "V_c_over_U_halfwidth": halfwidth / 32.0,
        "bracket_width": v_charge - v_mott,
        "midpoint_phase": phase,
        "twists_at_midpoint": 1,
        "status": "bracketed",
    }

    if not os.path.isdir(ANALYSIS):
        os.makedirs(ANALYSIS)
    write_csv(
        os.path.join(ANALYSIS, "one_twist_U32_refinement_observable.csv"),
        [observable],
        list(observable.keys()),
    )
    write_csv(
        os.path.join(ANALYSIS, "one_twist_U32_refined_bracket.csv"),
        [bracket],
        list(bracket.keys()),
    )
    print(
        "U=32 V=8.015 phase={} D={:.9f}; refined bracket "
        "[{:.3f},{:.3f}], Vc={:.4f}+/-{:.4f}, (V/U)c={:.8f}+/-{:.8f}".format(
            phase,
            D,
            v_mott,
            v_charge,
            midpoint,
            halfwidth,
            midpoint / 32.0,
            halfwidth / 32.0,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
