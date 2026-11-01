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

    def test_rejects_inconsistent_mask_and_k(self):
        bad = self.rows.copy()
        bad.loc[0, "original_mask"] = 0
        with self.assertRaisesRegex(ValueError, "constant"):
            audit(bad, self.sites)
        with self.assertRaisesRegex(ValueError, "settlement rule"):
            audit(self.rows.assign(k=1), self.sites)


if __name__ == "__main__":
    unittest.main()
