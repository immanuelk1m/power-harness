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
from audit_run_provenance import audit, compare_values, fingerprint  # noqa: E402


class AuditTests(unittest.TestCase):
    def test_distinct_seed_audit_is_opt_in_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run_id, seed in (("P1", 0), ("P2", 0), ("P3", None)):
                folder = root / run_id
                folder.mkdir()
                (folder / "config.json").write_text(json.dumps({"seed": seed}), encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
                (folder / "predictions.parquet").write_bytes(run_id.encode())
                (folder / "model.pt").write_bytes(run_id.encode())

            self.assertEqual(audit(root, ["P1", "P2", "P3"])["consistency_status"], "no_flags")
            duplicate = audit(root, ["P1", "P2"], distinct_seeds=True)
            self.assertEqual(duplicate["duplicate_seeds"], {"0": ["P1", "P2"]})
            self.assertEqual(duplicate["consistency_status"], "review_required")
            self.assertEqual(duplicate["artifact_status"], "present")
            incomplete = audit(root, ["P1", "P2", "P3"], distinct_seeds=True)
            self.assertEqual(incomplete["missing_seeds"], ["P3"])
            self.assertEqual(incomplete["artifact_status"], "incomplete")

            (root / "P2" / "config.json").write_text('{"seed": 1}', encoding="utf-8")
            (root / "P3" / "config.json").write_text('{"seed": 2}', encoding="utf-8")
            valid = audit(root, ["P1", "P2", "P3"], distinct_seeds=True)
            self.assertEqual(valid["missing_seeds"], [])
            self.assertEqual(valid["duplicate_seeds"], {})
            self.assertEqual(valid["artifact_status"], "present")
            self.assertEqual(valid["consistency_status"], "no_flags")

    def test_distinct_seeds_with_shared_artifacts_require_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for run_id, seed in (("P1", 0), ("P2", 1)):
                folder = root / run_id
                folder.mkdir()
                (folder / "config.json").write_text(json.dumps({"seed": seed}), encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
                (folder / "predictions.parquet").write_bytes(b"same predictions")
                (folder / "model.pt").write_bytes(b"same model")

            self.assertEqual(audit(root, ["P1", "P2"])["consistency_status"], "no_flags")
            shared = audit(root, ["P1", "P2"], distinct_seeds=True)
            self.assertIn("warning", shared["pairs"]["P1/P2"])
            self.assertEqual(shared["consistency_status"], "review_required")
            self.assertEqual(shared["artifact_status"], "present")

            (root / "P2" / "predictions.parquet").write_bytes(b"different predictions")
            model_only = audit(root, ["P1", "P2"], distinct_seeds=True)
            self.assertIn("warning", model_only["pairs"]["P1/P2"])

            (root / "P2" / "model.pt").write_bytes(b"different model")
            independent = audit(root, ["P1", "P2"], distinct_seeds=True)
            self.assertNotIn("warning", independent["pairs"]["P1/P2"])
            self.assertEqual(independent["consistency_status"], "no_flags")

            (root / "P2" / "model.pt").write_bytes(b"same model")
            (root / "P2" / "config.json").write_text('{"seed": 0}', encoding="utf-8")
            paired = audit(root, ["P1", "P2"], distinct_seeds=True)
            self.assertNotIn("warning", paired["pairs"]["P1/P2"])
            self.assertEqual(paired["duplicate_seeds"], {"0": ["P1", "P2"]})

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


    def test_json_changed_after_fingerprint_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "P1"
            folder.mkdir()
            for name, content in (
                ("config.json", "{}"),
                ("manifest.json", "{}"),
                ("result.json", '{"metrics": {"W": 100}}'),
            ):
                (folder / name).write_text(content, encoding="utf-8")
            (folder / "predictions.parquet").write_bytes(b"predictions")
            (folder / "model.pt").write_bytes(b"model")

            read_text = Path.read_text

            def rewrite_after_read(path, *args, **kwargs):
                content = read_text(path, *args, **kwargs)
                if path.name == "result.json":
                    path.write_text('{"metrics": {"W": 120}}', encoding="utf-8")
                return content

            with patch.object(Path, "read_text", rewrite_after_read):
                report = audit(root, ["P1"])

            self.assertEqual(report["artifact_status"], "incomplete")
            self.assertEqual(report["unreadable_artifacts"], {"P1": ["result.json"]})
            self.assertIsNone(report["runs"]["P1"]["W"])

    def test_conflicting_seed_metadata_requires_review(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "P1"
            folder.mkdir()
            for name, seed in (("config.json", 0), ("manifest.json", 1), ("result.json", 0)):
                data = {"seed": seed, "metrics": {"W": 100}} if name == "result.json" else {"seed": seed}
                (folder / name).write_text(json.dumps(data), encoding="utf-8")
            (folder / "predictions.parquet").write_bytes(b"predictions")
            (folder / "model.pt").write_bytes(b"model")

            report = audit(Path(temp), ["P1"])
            self.assertEqual(report["runs"]["P1"]["seed_conflict"], {
                "config.json": 0, "manifest.json": 1, "result.json": 0,
            })
            self.assertEqual(report["artifact_status"], "present")
            self.assertEqual(report["consistency_status"], "review_required")
            self.assertEqual(report["consistency_warnings"], ["P1"])

    def test_conflicting_parent_metadata_requires_review(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "P1"
            folder.mkdir()
            for name, parent in (
                ("config.json", "P-base"),
                ("manifest.json", "P-other"),
                ("result.json", "P-base"),
            ):
                data = {"seed": 0, "parent": parent}
                if name == "result.json":
                    data["metrics"] = {"W": 100}
                (folder / name).write_text(json.dumps(data), encoding="utf-8")
            (folder / "predictions.parquet").write_bytes(b"predictions")
            (folder / "model.pt").write_bytes(b"model")

            report = audit(Path(temp), ["P1"])
            self.assertEqual(report["runs"]["P1"]["parent_conflict"], {
                "config.json": "P-base",
                "manifest.json": "P-other",
                "result.json": "P-base",
            })
            self.assertEqual(report["artifact_status"], "present")
            self.assertEqual(report["consistency_status"], "review_required")
            self.assertEqual(report["consistency_warnings"], ["P1"])

            (folder / "manifest.json").write_text(
                json.dumps({"seed": 0, "parent": "P-base"}), encoding="utf-8",
            )
            consistent = audit(Path(temp), ["P1"])
            self.assertNotIn("parent_conflict", consistent["runs"]["P1"])
            self.assertEqual(consistent["consistency_status"], "no_flags")

    def test_conflicting_hash_metadata_within_run_requires_review(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "P1"
            folder.mkdir()
            metadata = {
                "config.json": {"seed": 0, "source_hash": "source-a", "cache_hash": "cache-a"},
                "manifest.json": {"seed": 0, "source_hash": "source-b"},
                "result.json": {"metrics": {"W": 100}, "source_hash": "source-a"},
            }
            for name, data in metadata.items():
                (folder / name).write_text(json.dumps(data), encoding="utf-8")
            (folder / "predictions.parquet").write_bytes(b"predictions")
            (folder / "model.pt").write_bytes(b"model")

            report = audit(Path(temp), ["P1"])
            self.assertEqual(report["runs"]["P1"]["provenance_conflicts"], {
                "source_hash": {
                    "config.json": "source-a",
                    "manifest.json": "source-b",
                    "result.json": "source-a",
                },
            })
            self.assertEqual(report["artifact_status"], "present")
            self.assertEqual(report["consistency_status"], "review_required")
            self.assertEqual(report["consistency_warnings"], ["P1"])

            metadata["manifest.json"]["source_hash"] = "source-a"
            (folder / "manifest.json").write_text(
                json.dumps(metadata["manifest.json"]), encoding="utf-8",
            )
            consistent = audit(Path(temp), ["P1"])
            self.assertNotIn("provenance_conflicts", consistent["runs"]["P1"])
            self.assertEqual(consistent["consistency_status"], "no_flags")

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

    def test_unreadable_artifact_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "P1"
            folder.mkdir()
            for name in ("config.json", "manifest.json"):
                (folder / name).write_text("{}", encoding="utf-8")
            (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
            (folder / "predictions.parquet").write_bytes(b"predictions")
            (folder / "model.pt").write_bytes(b"model")

            with patch("pathlib.Path.open", side_effect=PermissionError("denied")):
                self.assertEqual(fingerprint(folder / "model.pt"), {"unreadable": "denied"})

            with patch("audit_run_provenance.fingerprint", side_effect=lambda path: (
                {"unreadable": "denied"} if path.name == "model.pt" else fingerprint(path)
            )):
                report = audit(root, ["P1"])

            self.assertEqual(report["artifact_status"], "incomplete")
            self.assertEqual(report["unreadable_artifacts"], {"P1": ["model.pt"]})
            self.assertEqual(report["missing_scores"], [])


    def test_modified_artifact_during_hash_is_unreadable(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / "model.pt"
            artifact.write_bytes(b"original")
            with patch("audit_run_provenance.hashlib.sha256") as digest:
                digest.return_value.update.side_effect = lambda _: artifact.write_bytes(b"modified content")
                self.assertEqual(fingerprint(artifact), {"unreadable": "Artifact changed during hashing"})


    def test_empty_prediction_artifact_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "P1"
            folder.mkdir()
            (folder / "config.json").write_text("{}", encoding="utf-8")
            (folder / "manifest.json").write_text("{}", encoding="utf-8")
            (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
            (folder / "model.pt").write_bytes(b"model")
            (folder / "predictions.parquet").touch()

            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                 temp, "P1"],
                capture_output=True, text=True, check=False,
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(report["artifact_status"], "incomplete")
            self.assertEqual(report["empty_artifacts"], {"P1": ["predictions.parquet"]})
            self.assertEqual(report["missing_scores"], [])

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


    def test_negative_settlement_scores_are_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "P1"
            folder.mkdir()
            for name in ("config.json", "manifest.json"):
                (folder / name).write_text("{}", encoding="utf-8")
            (folder / "model.pt").write_bytes(b"model")
            (folder / "predictions.parquet").write_bytes(b"predictions")

            for total, g1, missing, invalid in (
                (-1, 40, ["P1"], {}),
                (100, -1, [], {"P1": ["G1"]}),
            ):
                with self.subTest(total=total, g1=g1):
                    (folder / "result.json").write_text(
                        json.dumps({"metrics": {"W": total, "group_metrics": {
                            "G1": {"W": g1}, "G2": {"W": 60},
                        }}}), encoding="utf-8",
                    )
                    report = audit(Path(temp), ["P1"])
                    self.assertEqual(report["artifact_status"], "incomplete")
                    self.assertEqual(report["missing_scores"], missing)
                    self.assertEqual(report["invalid_group_scores"], invalid)

    def test_overflowing_integer_w_is_invalid(self):
        from audit_run_provenance import w_value
        self.assertIsNone(w_value(10 ** 400))

    def test_malformed_group_scores_require_incomplete_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "P1"
            folder.mkdir()
            (folder / "config.json").write_text("{}", encoding="utf-8")
            (folder / "manifest.json").write_text("{}", encoding="utf-8")
            (folder / "model.pt").write_bytes(b"model")
            (folder / "predictions.parquet").write_bytes(b"predictions")

            for groups in ({"G1": {"W": 40}, "G2": {"W": float("nan")}}, {"G1": {"W": 40}}):
                with self.subTest(groups=groups):
                    (folder / "result.json").write_text(
                        json.dumps({"metrics": {"W": 100, "group_metrics": groups}}), encoding="utf-8",
                    )
                    result = subprocess.run(
                        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                         temp, "P1"],
                        capture_output=True, text=True, check=False,
                    )
                    report = json.loads(result.stdout)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(report["artifact_status"], "incomplete")
                    self.assertEqual(report["missing_scores"], [])
                    self.assertEqual(report["invalid_group_scores"], {"P1": ["G2"]})


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

    def test_identical_corrupt_parquet_cannot_pass_value_check(self):
        with tempfile.TemporaryDirectory() as temp:
            for run_id in ("P1", "P2"):
                folder = Path(temp) / run_id
                folder.mkdir()
                (folder / "config.json").write_text("{}", encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
                (folder / "model.pt").write_bytes(b"model")
                (folder / "predictions.parquet").write_bytes(b"invalid parquet")

            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                 temp, "P1", "P2", "--compare-values"],
                capture_output=True, text=True, check=False,
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(report["pairs"]["P1/P2"]["prediction_bytes_equal"])
            self.assertEqual(report["comparison_status"], "incomplete")
            self.assertEqual(report["unverified_value_pairs"], ["P1/P2"])


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


    def test_empty_valid_parquet_values_do_not_complete_comparison(self):
        try:
            import pandas as pd
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("Optional parquet dependencies are unavailable")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            empty = pd.DataFrame({
                "site_id": pd.Series(dtype="int64"),
                "ts": pd.Series(dtype="datetime64[ns]"),
                "forecast": pd.Series(dtype="float64"),
            })
            for run_id, seed in (("P1", 0), ("P2", 1)):
                folder = root / run_id
                folder.mkdir()
                (folder / "config.json").write_text(json.dumps({"seed": seed}), encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
                (folder / "model.pt").write_bytes(b"model")
                empty.to_parquet(folder / "predictions.parquet", index=False)

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
            comparison = report["pairs"]["P1/P2"]["prediction_values"]
            self.assertEqual(comparison["rows"], [0, 0])
            self.assertIsNone(comparison["equal"])
            self.assertIn("Empty prediction grid", comparison["unavailable"])

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


    def test_equal_row_count_with_different_grid_is_incomplete(self):
        try:
            import pandas as pd
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("Optional parquet dependencies are unavailable")

        with tempfile.TemporaryDirectory() as temp:
            for run_id, site_ids in (("P1", [1, 2]), ("P2", [1, 3])):
                folder = Path(temp) / run_id
                folder.mkdir()
                (folder / "config.json").write_text("{}", encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
                (folder / "model.pt").write_bytes(b"model")
                pd.DataFrame({"site_id": site_ids, "ts": [1, 1], "forecast": [2.0, 3.0]}).to_parquet(
                    folder / "predictions.parquet", index=False,
                )

            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                 temp, "P1", "P2", "--compare-values", "--expected-rows", "2"],
                capture_output=True, text=True, check=False,
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(report["comparison_status"], "incomplete")
            self.assertEqual(report["unverified_value_pairs"], ["P1/P2"])
            self.assertIsNone(report["pairs"]["P1/P2"]["prediction_values"]["equal"])
            self.assertIn("Different site_id/ts grids", report["pairs"]["P1/P2"]["prediction_values"]["unavailable"])


    def test_expected_rows_rejects_partial_prediction_grid(self):
        try:
            import pandas as pd
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("Optional parquet dependencies are unavailable")

        with tempfile.TemporaryDirectory() as temp:
            for run_id in ("P1", "P2"):
                folder = Path(temp) / run_id
                folder.mkdir()
                (folder / "config.json").write_text("{}", encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
                (folder / "model.pt").write_bytes(b"model")
                pd.DataFrame({"site_id": [1], "ts": [1], "forecast": [2.0]}).to_parquet(
                    folder / "predictions.parquet", index=False,
                )

            command = [
                sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                temp, "P1", "P2", "--compare-values", "--expected-rows",
            ]
            partial = subprocess.run([*command, "916872"], capture_output=True, text=True, check=False)
            report = json.loads(partial.stdout)
            self.assertEqual(partial.returncode, 2)
            self.assertEqual(report["comparison_status"], "incomplete")
            self.assertEqual(report["pairs"]["P1/P2"]["prediction_values"]["rows"], [1, 1])
            self.assertIn("Expected 916872", report["pairs"]["P1/P2"]["prediction_values"]["unavailable"])

            complete = subprocess.run([*command, "1"], capture_output=True, text=True, check=False)
            self.assertEqual(complete.returncode, 0)
            self.assertEqual(json.loads(complete.stdout)["comparison_status"], "complete")


    def test_expected_grid_requires_complete_site_hour_rectangle(self):
        try:
            import pandas as pd
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("Optional parquet dependencies are unavailable")

        with tempfile.TemporaryDirectory() as temp:
            for run_id in ("P1", "P2"):
                folder = Path(temp) / run_id
                folder.mkdir()
                (folder / "config.json").write_text("{}", encoding="utf-8")
                (folder / "manifest.json").write_text("{}", encoding="utf-8")
                (folder / "result.json").write_text('{"metrics": {"W": 100}}', encoding="utf-8")
                (folder / "model.pt").write_bytes(b"model")
                pd.DataFrame({"site_id": [1, 1, 1, 2], "ts": [1, 2, 3, 1], "forecast": [1, 2, 3, 4]}).to_parquet(
                    folder / "predictions.parquet", index=False,
                )

            command = [
                sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "audit_run_provenance.py"),
                temp, "P1", "P2", "--compare-values", "--expected-rows", "4", "--expected-grid", "2", "2",
            ]
            partial = subprocess.run(command, capture_output=True, text=True, check=False)
            report = json.loads(partial.stdout)
            self.assertEqual(partial.returncode, 2)
            self.assertEqual(report["comparison_status"], "incomplete")
            self.assertEqual(report["pairs"]["P1/P2"]["prediction_values"]["grid_dimensions"], [[2, 3], [2, 3]])

            for run_id in ("P1", "P2"):
                pd.DataFrame({"site_id": [1, 1, 2, 2], "ts": [1, 2, 1, 2], "forecast": [1, 2, 3, 4]}).to_parquet(
                    Path(temp) / run_id / "predictions.parquet", index=False,
                )
            complete = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(complete.returncode, 0)
            self.assertEqual(json.loads(complete.stdout)["comparison_status"], "complete")

            invalid = subprocess.run(command[:5] + ["--expected-grid", "2", "2"], capture_output=True, text=True, check=False)
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("requires --compare-values", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
