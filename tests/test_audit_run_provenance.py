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


if __name__ == "__main__":
    unittest.main()
