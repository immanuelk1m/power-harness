"""Read-only artifact and score consistency audit for local power_forecast runs."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from itertools import combinations
from math import isclose, isfinite
from pathlib import Path

FILES = ("config.json", "result.json", "manifest.json", "predictions.parquet", "model.pt")


def fingerprint(path):
    try:
        if not path.is_file():
            return {"missing": True}
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        stat = path.stat()
        if stat.st_size == 0:
            return {"empty": True, "bytes": 0}
        return {
            "sha256": digest.hexdigest(),
            "bytes": stat.st_size,
            "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }
    except OSError as error:
        return {"unreadable": str(error)}


def w_value(value):
    if isinstance(value, dict):
        value = value.get("W")
    try:
        score = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    except OverflowError:
        return None
    return score if score is not None and isfinite(score) and score >= 0 else None


def inspect_run(root, run_id):
    folder = root / run_id
    files = {name: fingerprint(folder / name) for name in FILES}
    record = {"files": files, "seed": None, "parent": None, "W": None, "group_W": None}
    for name in ("config.json", "manifest.json", "result.json"):
        if files[name].get("missing") or files[name].get("unreadable"):
            continue
        try:
            data = json.loads((folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            record[name + "_error"] = str(error)
            continue
        if not isinstance(data, dict):
            record[name + "_error"] = "JSON root must be an object"
            continue
        record[name + "_provenance"] = {
            key: data[key]
            for key in ("seed", "parent", "source_hash", "cache_hash", "protocol_hash", "data_hash")
            if key in data and isinstance(data[key], (str, int, float))
        }
        if name == "config.json":
            record["seed"] = data.get("seed")
            record["parent"] = data.get("parent")
        if name == "result.json":
            metrics = data.get("metrics", {})
            if not isinstance(metrics, dict):
                metrics = {}
            record["W"] = w_value(metrics.get("W"))
            if "group_metrics" in data or "group_metrics" in metrics:
                groups = data.get("group_metrics", metrics.get("group_metrics"))
                values = {
                    key: w_value(groups.get(key)) if isinstance(groups, dict) else None
                    for key in ("G1", "G2")
                }
                invalid = [key for key, value in values.items() if value is None]
                if invalid:
                    record["invalid_group_scores"] = invalid
                else:
                    record["group_W"] = values
                    if record["W"] is not None:
                        record["group_sum_delta"] = sum(values.values()) - record["W"]
                        record["group_sum_consistent"] = isclose(sum(values.values()), record["W"], rel_tol=0, abs_tol=0.01)
                        if not record["group_sum_consistent"]:
                            record["warning"] = "G1 + G2 does not match W for this run."
    for key in ("seed", "parent", "source_hash", "cache_hash", "protocol_hash", "data_hash"):
        values = {
            name: record[name + "_provenance"][key]
            for name in ("config.json", "manifest.json", "result.json")
            if key in record.get(name + "_provenance", {})
        }
        if len({str(value) for value in values.values()}) > 1:
            if key in ("seed", "parent"):
                record[key + "_conflict"] = values
            else:
                record.setdefault("provenance_conflicts", {})[key] = values
    return record


def compare_values(left, right):
    try:
        import pandas as pd

        a, b = pd.read_parquet(left), pd.read_parquet(right)
        keys = [key for key in ("site_id", "ts") if key in a.columns and key in b.columns]
        duplicates = [int(frame.duplicated(keys).sum()) for frame in (a, b)] if len(keys) == 2 else None
        null_keys = [int(frame[keys].isna().any(axis=1).sum()) for frame in (a, b)] if len(keys) == 2 else None
        result = {"rows": [len(a), len(b)], "key_columns": keys, "duplicate_keys": duplicates, "null_keys": null_keys}
        if len(keys) != 2 or any(duplicates) or any(null_keys):
            reason = ("Missing site_id/ts keys" if len(keys) != 2 else
                      "Duplicate site_id/ts keys" if any(duplicates) else "Null site_id/ts keys")
            return {**result, "equal": None, "unavailable": reason + ": cannot align prediction values reliably."}
        if set(a.columns) == set(b.columns):
            b = b[a.columns]
        a = a.sort_values(keys).reset_index(drop=True)
        b = b.sort_values(keys).reset_index(drop=True)
        return {**result, "equal": a.equals(b)}
    except Exception as error:  # Optional parquet dependencies must not prevent the hash audit.
        return {"unavailable": str(error)}


def audit(root, run_ids, compare_parquet=False):
    runs = {run_id: inspect_run(root, run_id) for run_id in run_ids}
    pairs = {}
    for left, right in combinations(run_ids, 2):
        a, b = runs[left], runs[right]
        pred_a, pred_b = a["files"]["predictions.parquet"], b["files"]["predictions.parquet"]
        same_bytes = pred_a.get("sha256") == pred_b.get("sha256") if "sha256" in pred_a and "sha256" in pred_b else None
        pair = {
            "prediction_bytes_equal": same_bytes,
            "model_bytes_equal": a["files"]["model.pt"].get("sha256") == b["files"]["model.pt"].get("sha256")
            if "sha256" in a["files"]["model.pt"] and "sha256" in b["files"]["model.pt"] else None,
            "W_delta": b["W"] - a["W"] if a["W"] is not None and b["W"] is not None else None,
        }
        differences = {}
        for filename in ("config.json", "manifest.json", "result.json"):
            left_meta = a.get(filename + "_provenance", {})
            right_meta = b.get(filename + "_provenance", {})
            for key in ("source_hash", "cache_hash", "protocol_hash", "data_hash"):
                if key in left_meta and key in right_meta and left_meta[key] != right_meta[key]:
                    differences[filename + "." + key] = [left_meta[key], right_meta[key]]
        if differences:
            pair["provenance_differences"] = differences
        if compare_parquet and same_bytes is not None:
            pair["prediction_values"] = compare_values(root / left / "predictions.parquet", root / right / "predictions.parquet")
        values_equal = pair.get("prediction_values", {}).get("equal") is True
        if (same_bytes or values_equal) and pair["W_delta"] is not None and not isclose(pair["W_delta"], 0, rel_tol=0, abs_tol=0.01):
            pair["warning"] = "Same prediction bytes or values but different W: verify labels, groups, SMP, evaluator and result paths."
        pairs[left + "/" + right] = pair
    missing = {
        run_id: [name for name, info in record["files"].items() if info.get("missing")]
        for run_id, record in runs.items()
    }
    missing = {run_id: names for run_id, names in missing.items() if names}
    unreadable_artifacts = {
        run_id: [name for name, info in record["files"].items() if info.get("unreadable")]
        for run_id, record in runs.items()
    }
    unreadable_artifacts = {run_id: names for run_id, names in unreadable_artifacts.items() if names}
    empty_artifacts = {
        run_id: [name for name, info in record["files"].items() if info.get("empty")]
        for run_id, record in runs.items()
    }
    empty_artifacts = {run_id: names for run_id, names in empty_artifacts.items() if names}
    missing_scores = [run_id for run_id, record in runs.items() if record["W"] is None]
    invalid_group_scores = {
        run_id: record["invalid_group_scores"]
        for run_id, record in runs.items() if "invalid_group_scores" in record
    }
    unreadable = {
        run_id: [key for key in record if key.endswith("_error")]
        for run_id, record in runs.items()
    }
    unreadable = {run_id: keys for run_id, keys in unreadable.items() if keys}
    incomplete = bool(missing or unreadable_artifacts or empty_artifacts or missing_scores or invalid_group_scores or unreadable)
    unverified_pairs = [
        name for name, pair in pairs.items()
        if compare_parquet and pair["prediction_bytes_equal"] is not True
        and not isinstance(pair.get("prediction_values", {}).get("equal"), bool)
    ]
    flagged = [
        name for name, run in runs.items()
        if "warning" in run or "seed_conflict" in run or "parent_conflict" in run or "provenance_conflicts" in run
    ]
    flagged += [name for name, pair in pairs.items() if "warning" in pair]
    return {
        "runs": runs,
        "pairs": pairs,
        "consistency_status": "review_required" if flagged else "no_flags",
        "consistency_warnings": flagged,
        "artifact_status": "incomplete" if incomplete else "present",
        "comparison_status": "incomplete" if unverified_pairs else "complete" if compare_parquet else "not_requested",
        "unverified_value_pairs": unverified_pairs,
        "missing_artifacts": missing,
        "unreadable_artifacts": unreadable_artifacts,
        "empty_artifacts": empty_artifacts,
        "missing_scores": missing_scores,
        "invalid_group_scores": invalid_group_scores,
        "unreadable_json": unreadable,
        "note": "No evaluator was called; no protected score was recomputed. Artifact presence does not prove evaluation-input identity.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs_dir", type=Path)
    parser.add_argument("run_ids", nargs="+", help="Existing run directory names")
    parser.add_argument("--compare-values", action="store_true", help="Compare parquet values when bytes differ (requires pandas parquet engine)")
    args = parser.parse_args()
    if len(args.run_ids) != len(set(args.run_ids)) or any(Path(run_id).name != run_id or run_id in (".", "..") for run_id in args.run_ids):
        parser.error("Run IDs must be distinct directory names")
    report = audit(args.runs_dir, args.run_ids, args.compare_values)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["artifact_status"] == "incomplete" or report["comparison_status"] == "incomplete":
        sys.exit(2)
    if report["consistency_status"] == "review_required":
        sys.exit(3)


if __name__ == "__main__":
    main()
