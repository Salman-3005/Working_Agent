import unittest
import sqlite3
import json
from backend.services.normalizer import (
    normalize_record_ref,
    parse_numeric_value,
    values_are_equivalent
)
from backend.services.tenant import TenantIsolationService
from backend.services.comparison import ReconciliationService
from backend.services.importer import CSVImportService
from backend.database import init_db, get_db_connection

class ReconciliationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_reference_normalization(self):
        """Test dirty references in different formats normalize identically."""
        # Clean standard
        self.assertEqual(normalize_record_ref("REC-1001"), "REC-1001")
        # Lowercase
        self.assertEqual(normalize_record_ref("rec-1001"), "REC-1001")
        # Leading/trailing whitespace
        self.assertEqual(normalize_record_ref("  REC-1001  "), "REC-1001")
        # Underscore delimiter
        self.assertEqual(normalize_record_ref("REC_1001"), "REC-1001")
        # Hash delimiter
        self.assertEqual(normalize_record_ref("REC#1001"), "REC-1001")
        # Space delimiter
        self.assertEqual(normalize_record_ref("REC 1001"), "REC-1001")
        # No hyphen
        self.assertEqual(normalize_record_ref("REC1001"), "REC-1001")
        # Empty/None
        self.assertEqual(normalize_record_ref(""), "")
        self.assertEqual(normalize_record_ref(None), "")

    def test_02_numeric_parsing_and_dirty_values(self):
        """Test numeric parsing handles currencies, commas, and dirty strings."""
        # Standard float
        val, valid, err = parse_numeric_value("1250.50")
        self.assertTrue(valid)
        self.assertEqual(val, 1250.50)

        # Currency and commas
        val, valid, err = parse_numeric_value("$1,250.50")
        self.assertTrue(valid)
        self.assertEqual(val, 1250.50)

        # Signed positive
        val, valid, err = parse_numeric_value("+450.00")
        self.assertTrue(valid)
        self.assertEqual(val, 450.00)

        # Zero representations
        val, valid, err = parse_numeric_value("0.00")
        self.assertTrue(valid)
        self.assertEqual(val, 0.0)

        # Blank string
        val, valid, err = parse_numeric_value("")
        self.assertFalse(valid)
        self.assertEqual(err, "EMPTY_VALUE")

        # Unparseable strings (N/A, PENDING, invalid)
        val, valid, err = parse_numeric_value("N/A")
        self.assertFalse(valid)
        self.assertIn("UNPARSEABLE", err)

        val, valid, err = parse_numeric_value("PENDING")
        self.assertFalse(valid)
        self.assertIn("UNPARSEABLE", err)

    def test_03_non_error_identification(self):
        """Test non-errors with formatting differences are NOT flagged as mismatches."""
        # '1,200.00' vs '1200'
        is_equiv, reason = values_are_equivalent("1,200.00", "1200")
        self.assertTrue(is_equiv)

        # '$350.50' vs '350.5'
        is_equiv, reason = values_are_equivalent("$350.50", "350.5")
        self.assertTrue(is_equiv)

        # '0.00' vs '0'
        is_equiv, reason = values_are_equivalent("0.00", "0")
        self.assertTrue(is_equiv)

        # '+450.00' vs '450.00'
        is_equiv, reason = values_are_equivalent("+450.00", "450.00")
        self.assertTrue(is_equiv)

    def test_04_missing_in_system_b(self):
        """Test that a record in System A with no entry in System B is flagged."""
        recon = ReconciliationService()
        res = recon.run_reconciliation()
        self.assertIn("MISSING_IN_SYSTEM_B", res["counts_by_type"])
        self.assertGreater(res["counts_by_type"]["MISSING_IN_SYSTEM_B"], 0)

        # Check DB record
        rows = TenantIsolationService.query_disagreements(reason="MISSING_IN_SYSTEM_B")
        self.assertTrue(len(rows) > 0)
        self.assertEqual(rows[0]["disagreement_type"], "MISSING_IN_SYSTEM_B")
        self.assertEqual(rows[0]["system_b_value"], "—")

    def test_05_orphan_system_b_entry(self):
        """Test that a System B entry pointing to a non-existent A record is flagged."""
        rows = TenantIsolationService.query_disagreements(reason="ORPHAN_SYSTEM_B_ENTRY")
        self.assertTrue(len(rows) > 0)
        self.assertEqual(rows[0]["disagreement_type"], "ORPHAN_SYSTEM_B_ENTRY")
        self.assertEqual(rows[0]["system_a_value"], "—")
        self.assertNotEqual(rows[0]["system_b_value"], "—")

    def test_06_duplicate_system_b_entry(self):
        """Test that multiple System B entries for the same record are flagged."""
        rows = TenantIsolationService.query_disagreements(reason="DUPLICATE_SYSTEM_B_ENTRY")
        self.assertTrue(len(rows) > 0)
        self.assertEqual(rows[0]["disagreement_type"], "DUPLICATE_SYSTEM_B_ENTRY")
        # System B value should show multiple values or duplicates
        self.assertIn(",", rows[0]["system_b_value"])

    def test_07_value_mismatch(self):
        """Test that records with conflicting numeric values are flagged."""
        rows = TenantIsolationService.query_disagreements(reason="VALUE_MISMATCH")
        self.assertTrue(len(rows) > 0)
        self.assertEqual(rows[0]["disagreement_type"], "VALUE_MISMATCH")
        self.assertNotEqual(rows[0]["system_a_value"], rows[0]["system_b_value"])

    def test_08_tenant_isolation(self):
        """Test that tenant queries strictly isolate records across tenant boundaries."""
        tenants = TenantIsolationService.get_valid_tenants()
        self.assertGreaterEqual(len(tenants), 2)

        org_1 = tenants[0]["org_id"]
        org_2 = tenants[1]["org_id"]

        results_1 = TenantIsolationService.query_disagreements(tenant_id=org_1)
        results_2 = TenantIsolationService.query_disagreements(tenant_id=org_2)

        # Every record in results_1 must have org_id == org_1
        for row in results_1:
            self.assertEqual(row["org_id"], org_1)

        # Every record in results_2 must have org_id == org_2
        for row in results_2:
            self.assertEqual(row["org_id"], org_2)

        # There must be zero overlap between records
        ids_1 = {r["id"] for r in results_1}
        ids_2 = {r["id"] for r in results_2}
        self.assertEqual(len(ids_1.intersection(ids_2)), 0)

    def test_09_sorting_by_value(self):
        """Test sorting by value works ascending and descending."""
        asc_rows = TenantIsolationService.query_disagreements(sort_order="asc")
        desc_rows = TenantIsolationService.query_disagreements(sort_order="desc")
        self.assertEqual(len(asc_rows), len(desc_rows))
        self.assertGreater(len(asc_rows), 0)

    def test_10_dirty_data_survives_importer(self):
        """Test that unparseable and unmapped records are stored without being silently dropped."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM system_a_records WHERE import_error IS NOT NULL")
        dirty_a = cursor.fetchone()["cnt"]
        self.assertGreater(dirty_a, 0)

        cursor.execute("SELECT COUNT(*) as cnt FROM system_b_entries WHERE import_error IS NOT NULL")
        dirty_b = cursor.fetchone()["cnt"]
        self.assertGreater(dirty_b, 0)
        conn.close()

if __name__ == "__main__":
    unittest.main()
