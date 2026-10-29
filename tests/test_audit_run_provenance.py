"""Small regression checks for the read-only provenance audit."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_run_provenance import audit  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
