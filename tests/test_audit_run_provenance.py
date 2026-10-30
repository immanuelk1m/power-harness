"""Small regression checks for the read-only provenance audit."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_run_provenance import audit, compare_values  # noqa: E402


class AuditTests(unittest.TestCase):
    def test_same_predictions_different_scores_are_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run_id, seed, score in (("P1", 0, 100), ("P2", 1, 120)):
                folder = root / run_id
                folder.mkdir()
                (folder / "predictions.parquet").write_bytes(b"same predictions")
                (folder / "model.pt").write_bytes(b"same model")
                (folder / "config.json").write_text(json.dumps({"seed": seed}), encoding="utf-8")
                (folder / "result.json").write_text(json.dumps({"metrics": {"W": score}, "group_metrics": {"G1": {"W": 40}, "G2": {"W": 60}}}), encoding="utf-8")
            report = audit(root, ["P1", "P2"])
            pair = report["pairs"]["P1/P2"]
            self.assertTrue(pair["prediction_bytes_equal"])
            self.assertEqual(pair["W_delta"], 20)
            self.assertIn("warning", pair)
            self.assertEqual(report["runs"]["P1"]["group_sum_delta"], 0)
            self.assertEqual(report["runs"]["P2"]["group_sum_delta"], -20)
            self.assertTrue(report["runs"]["P1"]["group_sum_consistent"])
            self.assertFalse(report["runs"]["P2"]["group_sum_consistent"])
            self.assertIn("warning", report["runs"]["P2"])
            self.assertEqual(report["consistency_status"], "review_required")
            self.assertEqual(report["consistency_warnings"], ["P2", "P1/P2"])
            self.assertTrue(report["runs"]["P1"]["files"]["manifest.json"]["missing"])


    def test_cent_level_rounding_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run_id, score in (("P1", 100), ("P2", 100.005)):
                folder = root / run_id
                folder.mkdir()
                (folder / "predictions.parquet").write_bytes(b"same predictions")
                (folder / "result.json").write_text(
                    json.dumps({"metrics": {"W": score}, "group_metrics": {"G1": {"W": 40}, "G2": {"W": 60}}}),
                    encoding="utf-8",
                )
            report = audit(root, ["P1", "P2"])
            self.assertTrue(report["runs"]["P2"]["group_sum_consistent"])
            self.assertNotIn("warning", report["runs"]["P2"])
            self.assertNotIn("warning", report["pairs"]["P1/P2"])
            self.assertEqual(report["consistency_status"], "no_flags")


    def test_equal_parquet_values_with_different_bytes_and_scores_are_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run_id, predictions, score in (("P1", b"parquet A", 100), ("P2", b"parquet B", 120)):
                folder = root / run_id
                folder.mkdir()
                (folder / "predictions.parquet").write_bytes(predictions)
                (folder / "result.json").write_text(json.dumps({"metrics": {"W": score}}), encoding="utf-8")

            with patch("audit_run_provenance.compare_values", return_value={"equal": True, "rows": [2, 2]}):
                pair = audit(root, ["P1", "P2"], compare_parquet=True)["pairs"]["P1/P2"]

            self.assertFalse(pair["prediction_bytes_equal"])
            self.assertTrue(pair["prediction_values"]["equal"])
            self.assertEqual(pair["W_delta"], 20)
            self.assertIn("warning", pair)


    def test_changed_artifact_provenance_is_reported_without_guessing_missing_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run_id, seed, data_hash in (("P1", 0, "dataset-a"), ("P2", 1, "dataset-b")):
                folder = root / run_id
                folder.mkdir()
                (folder / "config.json").write_text(json.dumps({"seed": seed, "source_hash": "same-code"}), encoding="utf-8")
                (folder / "manifest.json").write_text(
                    json.dumps({"data_hash": data_hash, "protocol_hash": "same-protocol"}),
                    encoding="utf-8",
                )
                (folder / "result.json").write_text(json.dumps({"metrics": {"W": 100}}), encoding="utf-8")

            pair = audit(root, ["P1", "P2"])["pairs"]["P1/P2"]
            self.assertEqual(pair["provenance_differences"], {"manifest.json.data_hash": ["dataset-a", "dataset-b"]})
            self.assertIsNone(pair["prediction_bytes_equal"])
            self.assertNotIn("warning", pair)


    def test_missing_run_artifacts_fail_cli_without_evaluating(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"), temp, "P2235"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertEqual(report["artifact_status"], "incomplete")
            self.assertIn("predictions.parquet", report["missing_artifacts"]["P2235"])
            self.assertEqual(report["missing_scores"], ["P2235"])

    def test_nonfinite_w_requires_incomplete_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "P1"
            folder.mkdir()
            (folder / "config.json").write_text("{}", encoding="utf-8")
            (folder / "manifest.json").write_text("{}", encoding="utf-8")
            (folder / "model.pt").write_bytes(b"model")
            (folder / "predictions.parquet").write_bytes(b"prediction")
            for score in ("1e309", "NaN"):
                with self.subTest(score=score):
                    (folder / "result.json").write_text(
                        '{"metrics": {"W": ' + score + '}}', encoding="utf-8",
                    )
                    result = subprocess.run(
                        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                         temp, "P1"],
                        capture_output=True, text=True, check=False,
                    )
                    report = json.loads(result.stdout)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(report["artifact_status"], "incomplete")
                    self.assertEqual(report["missing_scores"], ["P1"])
                    self.assertIsNone(report["runs"]["P1"]["W"])


    def test_complete_artifacts_with_conflicting_scores_require_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run_id, score in (("P1", 100), ("P2", 120)):
                folder = root / run_id
                folder.mkdir()
                (folder / "config.json").write_text("{}", encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text(json.dumps({"metrics": {"W": score}}), encoding="utf-8")
                (folder / "model.pt").write_bytes(b"same model")
                (folder / "predictions.parquet").write_bytes(b"same predictions")

            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                 temp, "P1", "P2"],
                capture_output=True, text=True, check=False,
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(report["artifact_status"], "present")
            self.assertEqual(report["consistency_status"], "review_required")
            self.assertEqual(report["consistency_warnings"], ["P1/P2"])

    def test_requested_value_comparison_failure_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run_id, prediction in (("P1", b"invalid A"), ("P2", b"invalid B")):
                folder = root / run_id
                folder.mkdir()
                (folder / "config.json").write_text("{}", encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
                (folder / "model.pt").write_bytes(b"model")
                (folder / "predictions.parquet").write_bytes(prediction)

            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                 temp, "P1", "P2", "--compare-values"],
                capture_output=True, text=True, check=False,
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(report["artifact_status"], "present")
            self.assertEqual(report["comparison_status"], "incomplete")
            self.assertEqual(report["unverified_value_pairs"], ["P1/P2"])
            self.assertIn("unavailable", report["pairs"]["P1/P2"]["prediction_values"])

    def test_parquet_value_comparison_requires_unique_site_time_keys(self):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("Optional pandas dependency is unavailable")

        unkeyed = pd.DataFrame({"forecast": [1.0]})
        duplicate = pd.DataFrame({"site_id": [1, 1], "ts": [1, 1], "forecast": [1.0, 2.0]})
        null_key = pd.DataFrame({"site_id": [None], "ts": [1], "forecast": [1.0]})
        keyed = pd.DataFrame({"site_id": [1, 2], "ts": [1, 1], "forecast": [1.0, 2.0]})
        reordered = keyed.iloc[::-1][["forecast", "ts", "site_id"]]

        for left, right, expected in ((unkeyed, unkeyed, None), (duplicate, duplicate, None), (null_key, null_key, None), (keyed, reordered, True)):
            with self.subTest(expected=expected, columns=list(left.columns)):
                with patch("pandas.read_parquet", side_effect=[left, right]):
                    result = compare_values("left.parquet", "right.parquet")
                self.assertIs(result["equal"], expected)
                if expected is None:
                    self.assertIn("unavailable", result)


    def test_parquet_comparison_handles_reordered_rows_and_different_encoding(self):
        try:
            import pandas as pd
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("Optional parquet dependencies are unavailable")

        with tempfile.TemporaryDirectory() as temp:
            left, right = Path(temp) / "left.parquet", Path(temp) / "right.parquet"
            values = pd.DataFrame({"site_id": [1, 2], "ts": [1, 1], "forecast": [3.0, 4.0]})
            values.to_parquet(left, compression="snappy", index=False)
            values.iloc[::-1][["forecast", "ts", "site_id"]].to_parquet(right, compression=None, index=False)

            self.assertNotEqual(left.read_bytes(), right.read_bytes())
            self.assertTrue(compare_values(left, right)["equal"])


if __name__ == "__main__":
    unittest.main()
