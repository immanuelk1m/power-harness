"""Read-only paired 2024 OOF settlement audit; never calls the 2025 evaluator."""

import argparse
import json
from pathlib import Path

import pandas as pd

COLUMNS = {"site_id", "ts", "seed", "actual", "control", "candidate", "smp", "k", "original_mask"}


def audit(predictions, membership):
    """Compare two arms on identical observed sites; report masks separately."""
    if not COLUMNS <= set(predictions) or not {"site_id", "group"} <= set(membership):
        raise ValueError("Missing required prediction or membership columns")
    if membership.empty or membership["site_id"].isna().any() or membership["site_id"].duplicated().any():
        raise ValueError("Membership must have unique, non-null site_id")
    if set(membership["group"]) != {"G1", "G2"}:
        raise ValueError("Membership must contain G1 and G2")
    if predictions.empty or predictions[list(COLUMNS)].isna().any().any():
        raise ValueError("Prediction rows must be present and non-null")
    if not predictions["ts"].astype(str).str.endswith("+09:00").all():
        raise ValueError("Timestamps must include the +09:00 KST offset")
    timestamps = pd.to_datetime(predictions["ts"], utc=True, errors="raise").dt.tz_convert("Asia/Seoul")
    if not timestamps.between(pd.Timestamp("2024-01-01", tz="Asia/Seoul"), pd.Timestamp("2025-01-01", tz="Asia/Seoul"), inclusive="left").all():
        raise ValueError("Only 2024 OOF timestamps are permitted")
    if predictions.duplicated(["seed", "ts", "site_id"]).any():
        raise ValueError("Duplicate seed/ts/site_id")
    if not predictions["seed"].astype(str).str.fullmatch(r"(?:0|[1-9][0-9]*)").all():
        raise ValueError("Invalid seed")
    if not predictions["original_mask"].isin([0, 1, False, True]).all():
        raise ValueError("original_mask must be 0 or 1")
    numeric = predictions[["actual", "control", "candidate", "smp", "k"]].apply(pd.to_numeric, errors="raise")
    if not numeric.map(lambda value: pd.notna(value) and abs(value) != float("inf")).all().all():
        raise ValueError("Non-finite score inputs")
    if (numeric[["actual", "control", "candidate", "smp"]] < 0).any().any():
        raise ValueError("Negative generation or SMP")
    expected_k = timestamps.dt.hour.between(11, 15).map({True: 3, False: 1})
    if not numeric["k"].eq(expected_k).all():
        raise ValueError("k must follow the 11-15 KST settlement rule")
    rows = predictions.copy()
    rows[["actual", "control", "candidate", "smp", "k"]] = numeric
    rows["ts"] = timestamps
    rows = rows.merge(membership, on="site_id", how="left", validate="many_to_one")
    if rows["group"].isna().any():
        raise ValueError("Unknown site_id")
    if rows.groupby("ts")["smp"].nunique().gt(1).any():
        raise ValueError("Inconsistent SMP at the same timestamp")
    if rows.groupby(["ts", "site_id"])["actual"].nunique().gt(1).any():
        raise ValueError("Inconsistent actual across seeds for the same site-hour")
    keys = ["seed", "ts", "group"]
    grouped = rows.groupby(keys, sort=True)
    if grouped["original_mask"].nunique().gt(1).any():
        raise ValueError("original_mask must be constant within a group-hour")
    aggregates = grouped.agg(
        actual=("actual", "sum"), control=("control", "sum"), candidate=("candidate", "sum"),
        smp=("smp", "first"), k=("k", "first"), observed_sites=("site_id", "nunique"),
        original_mask=("original_mask", "first"),
    ).reset_index()
    expected_sites = membership.groupby("group")["site_id"].size()
    aggregates["complete_mask"] = aggregates["observed_sites"].eq(aggregates["group"].map(expected_sites))
    aggregates["month"] = aggregates["ts"].dt.month
    aggregates["peak"] = aggregates["ts"].dt.hour.between(11, 15)
    aggregates["weight"] = aggregates["smp"] * aggregates["k"]
    for arm in ("control", "candidate"):
        aggregates[arm + "_loss"] = (aggregates[arm] - aggregates["actual"]).abs()
    output = []
    for mask in ("original_mask", "complete_mask"):
        eligible = aggregates.loc[aggregates[mask].astype(bool)]
        for (seed, group, month, peak), subset in eligible.groupby(["seed", "group", "month", "peak"], sort=True):
            control = (subset["control_loss"] * subset["weight"]).sum()
            candidate = (subset["candidate_loss"] * subset["weight"]).sum()
            output.append({
                "mask": mask, "seed": str(seed), "group": group, "month": int(month), "peak": bool(peak),
                "group_hours": len(subset), "site_rows": int(subset["observed_sites"].sum()),
                "weight_sum": float(subset["weight"].sum()),
                "control_W": float(control), "candidate_W": float(candidate),
                "delta_W": float(candidate - control),
                "delta_unweighted": float((subset["candidate_loss"] - subset["control_loss"]).sum()),
            })
    return {"scope": "2024 OOF diagnostic only; provenance and cutoff not verified", "rows": output,
            "mask_group_hours": {mask: int(aggregates[mask].sum()) for mask in ("original_mask", "complete_mask")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path, help="CSV with paired site-level 2024 OOF predictions")
    parser.add_argument("membership", type=Path, help="CSV with site_id,group from the same run")
    args = parser.parse_args()
    try:
        report = audit(pd.read_csv(args.predictions, dtype={"site_id": str, "seed": str, "ts": str}),
                       pd.read_csv(args.membership, dtype={"site_id": str}))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(2, f"Audit incomplete: {error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
