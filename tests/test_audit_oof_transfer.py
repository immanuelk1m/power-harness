"""Synthetic tests for paired 2024 OOF settlement arithmetic and fail-closed guards."""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_oof_transfer import audit  # noqa: E402


class OofTransferTests(unittest.TestCase):
    def setUp(self):
        self.sites = pd.DataFrame({"site_id": ["a", "b", "c"], "group": ["G1", "G1", "G2"]})
        self.rows = pd.DataFrame([
            {"site_id": site, "ts": "2024-11-01T12:00:00+09:00", "seed": "0", "actual": actual,
             "control": control, "candidate": candidate, "smp": 100, "k": 3, "original_mask": 1}
            for site, actual, control, candidate in [("a", 10, 9, 11), ("b", 10, 9, 10), ("c", 5, 4, 5)]
        ])

    def test_paired_group_loss_and_masks(self):
        report = audit(self.rows, self.sites)
        self.assertEqual(report["mask_group_hours"], {"original_mask": 2, "complete_mask": 2})
        group = next(row for row in report["rows"] if row["group"] == "G1" and row["mask"] == "original_mask")
        self.assertEqual((group["control_W"], group["candidate_W"], group["delta_W"]), (600, 300, -300))
        self.assertEqual(group["delta_unweighted"], -1)

    def test_incomplete_support_does_not_claim_complete_mask(self):
        partial = self.rows.loc[self.rows["site_id"] != "b"]
        report = audit(partial, self.sites)
        self.assertEqual(report["mask_group_hours"], {"original_mask": 2, "complete_mask": 1})
        self.assertFalse(any(row["group"] == "G1" and row["mask"] == "complete_mask" for row in report["rows"]))

    def test_rejects_protected_year_and_duplicate_site(self):
        with self.assertRaisesRegex(ValueError, "Only 2024"):
            audit(self.rows.assign(ts="2025-01-01T12:00:00+09:00"), self.sites)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit(pd.concat([self.rows, self.rows.iloc[:1]]), self.sites)

    def test_first_issuance_cutoff_is_exclusive(self):
        before = self.rows.assign(ts="2024-12-31T16:00:00+09:00", k=1)
        self.assertTrue(audit(before, self.sites)["rows"])
        for ts in ("2024-12-31T17:00:00+09:00", "2024-12-31T23:00:00+09:00"):
            with self.subTest(ts=ts), self.assertRaisesRegex(ValueError, "pre-cutoff"):
                audit(self.rows.assign(ts=ts, k=1), self.sites)

    def test_rejects_duplicate_after_timestamp_normalization(self):
        rows = self.rows.assign(ts="2024-11-01T12:00:00.000+09:00")
        duplicate = rows.iloc[:1].assign(ts="2024-11-01T12:00:00.000000+09:00")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit(pd.concat([rows, duplicate], ignore_index=True), self.sites)

    def test_rejects_conflicting_actual_across_seeds(self):
        paired = pd.concat([self.rows, self.rows.assign(seed="1")], ignore_index=True)
        self.assertEqual(audit(paired, self.sites)["mask_group_hours"]["original_mask"], 4)
        paired.loc[(paired["seed"] == "1") & (paired["site_id"] == "a"), "actual"] = 11
        with self.assertRaisesRegex(ValueError, "Inconsistent actual across seeds"):
            audit(paired, self.sites)

    def test_rejects_seed_support_or_mask_mismatch(self):
        paired = pd.concat([self.rows, self.rows.assign(seed="1")], ignore_index=True)
        missing = paired.loc[~((paired["seed"] == "1") & (paired["site_id"] == "b"))]
        with self.assertRaisesRegex(ValueError, "Site-hour support differs across seeds"):
            audit(missing, self.sites)
        masked = paired.copy()
        masked.loc[(masked["seed"] == "1") & (masked["site_id"] == "c"), "original_mask"] = 0
        with self.assertRaisesRegex(ValueError, "Inconsistent original_mask across seeds"):
            audit(masked, self.sites)

    def test_rejects_inconsistent_mask_and_k(self):
        bad = self.rows.copy()
        bad.loc[0, "original_mask"] = 0
        with self.assertRaisesRegex(ValueError, "constant"):
            audit(bad, self.sites)
        with self.assertRaisesRegex(ValueError, "settlement rule"):
            audit(self.rows.assign(k=1), self.sites)


if __name__ == "__main__":
    unittest.main()
