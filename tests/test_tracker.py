# -*- coding: utf-8 -*-
"""
Automated Tests for Tender Opportunity Scraper & Tracker
Author: Eng. MHD. Shadi AL-Hasan <mhd.shadi.alhasan@gmail.com>
"""

import json
import unittest
from pathlib import Path
import tempfile

from tracker import (
    TenderTracker,
    extract_opportunity_record,
    extract_opportunities,
    filter_opportunities,
    render_new_tender_template,
    render_tenders_digest_template,
    render_deadline_warning_template,
    load_env_file
)

class TestTenderScraperExtractor(unittest.TestCase):
    def test_extract_valid_record(self):
        """Test extraction and normalization of a valid raw tender dictionary."""
        raw = {
            "id": " TND-2026-1001 ",
            "title": "توريد تجهيزات الخوادم ومصفوفات التخزين SAN",
            "entity": "وزارة المالية",
            "deadline": "2026-12-01",
            "category": "Data Center Hardware",
            "status": "open",
            "estimated_budget_usd": "750000.50"
        }
        extracted = extract_opportunity_record(raw)
        self.assertIsNotNone(extracted)
        self.assertEqual(extracted["id"], "TND-2026-1001")
        self.assertEqual(extracted["title"], "توريد تجهيزات الخوادم ومصفوفات التخزين SAN")
        self.assertEqual(extracted["entity"], "وزارة المالية")
        self.assertEqual(extracted["status"], "OPEN")
        self.assertEqual(extracted["estimated_budget_usd"], 750000.50)

    def test_extract_invalid_and_missing_mandatory_fields(self):
        """Test that records missing ID or Title are discarded gracefully."""
        self.assertIsNone(extract_opportunity_record({}))
        self.assertIsNone(extract_opportunity_record({"id": "TND-1"}))  # missing title
        self.assertIsNone(extract_opportunity_record({"title": "Sample"}))  # missing id
        self.assertIsNone(extract_opportunity_record("invalid-not-dict"))

    def test_extract_opportunities_list_and_deduplication(self):
        """Test bulk extraction and deduplication of opportunities by ID."""
        raw_list = [
            {"id": "T1", "title": "First Bid", "category": "IT"},
            {"id": "T2", "title": "Second Bid", "category": "Software"},
            {"id": "T1", "title": "Duplicate Bid", "category": "IT"},
            {"malformed": "entry"}
        ]
        results = extract_opportunities(raw_list)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "T1")
        self.assertEqual(results[1]["id"], "T2")

    def test_extract_from_json_file(self):
        """Test reading and extracting opportunities directly from existing test_tenders.json file."""
        file_path = Path("D:/github/tender-opportunity-tracker/test_tenders.json")
        if file_path.exists():
            tenders = extract_opportunities(file_path)
            self.assertGreaterEqual(len(tenders), 2)
            self.assertTrue(any(t["id"] == "TND-2026-0891" for t in tenders))


class TestJSONFiltering(unittest.TestCase):
    def setUp(self):
        self.sample_tenders = [
            {
                "id": "TND-01",
                "title": "توريد مراكز البيانات السحابية",
                "entity": "وزارة الاتصالات",
                "category": "IT & Cloud Infrastructure",
                "status": "OPEN",
                "estimated_budget_usd": 500000.0
            },
            {
                "id": "TND-02",
                "title": "أتمتة منظومة ERP وتدريب الكوادر",
                "entity": "الصندوق السيادي",
                "category": "Enterprise Software",
                "status": "OPEN",
                "estimated_budget_usd": 300000.0
            },
            {
                "id": "TND-03",
                "title": "صيانة كوابل الألياف البصرية",
                "entity": "الشركة السورية للاتصالات",
                "category": "Telecommunications",
                "status": "CLOSED",
                "estimated_budget_usd": 150000.0
            }
        ]

    def test_filter_by_category(self):
        """Test filtering by category string."""
        filtered = filter_opportunities(self.sample_tenders, category="Cloud")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "TND-01")

    def test_filter_by_status(self):
        """Test filtering by status (OPEN / CLOSED)."""
        open_tenders = filter_opportunities(self.sample_tenders, status="OPEN")
        self.assertEqual(len(open_tenders), 2)

        closed_tenders = filter_opportunities(self.sample_tenders, status="CLOSED")
        self.assertEqual(len(closed_tenders), 1)
        self.assertEqual(closed_tenders[0]["id"], "TND-03")

    def test_filter_by_arabic_keyword(self):
        """Test filtering with Arabic text search across title, entity, and category."""
        # Keyword in title
        res_erp = filter_opportunities(self.sample_tenders, keyword="ERP")
        self.assertEqual(len(res_erp), 1)
        self.assertEqual(res_erp[0]["id"], "TND-02")

        # Keyword in entity (matches both "وزارة الاتصالات" and "للاتصالات")
        res_comm = filter_opportunities(self.sample_tenders, keyword="اتصالات")
        self.assertEqual(len(res_comm), 2)

    def test_filter_by_budget(self):
        """Test filtering opportunities by minimum budget value."""
        high_value = filter_opportunities(self.sample_tenders, min_budget=400000.0)
        self.assertEqual(len(high_value), 1)
        self.assertEqual(high_value[0]["id"], "TND-01")


class TestTelegramTemplates(unittest.TestCase):
    def test_render_new_tender_template(self):
        """Test template formatting for a single tender announcement."""
        tender = {
            "id": "TND-2026-8888",
            "title": "توريد منصة الذكاء الاصطناعي للمؤسسات",
            "entity": "الهيئة العامة للتطوير",
            "deadline": "2026-12-15",
            "category": "Artificial Intelligence",
            "status": "OPEN",
            "estimated_budget_usd": 900000.0
        }
        rendered = render_new_tender_template(tender)
        self.assertIn("NEW TENDER OPPORTUNITY DETECTED", rendered)
        self.assertIn("TND-2026-8888", rendered)
        self.assertIn("توريد منصة الذكاء الاصطناعي للمؤسسات", rendered)
        self.assertIn("$900,000.00 USD", rendered)

    def test_render_digest_template(self):
        """Test summary digest rendering with multiple entries."""
        tenders = [
            {"id": "T1", "title": "Project Alpha", "entity": "Ministry A", "deadline": "2026-11-01", "status": "OPEN"},
            {"id": "T2", "title": "Project Beta", "entity": "Fund B", "deadline": "2026-11-20", "status": "OPEN"}
        ]
        digest = render_tenders_digest_template(tenders)
        self.assertIn("TENDER OPPORTUNITIES SUMMARY DIGEST", digest)
        self.assertIn("Active Matching Tenders", digest)
        self.assertIn("Project Alpha", digest)
        self.assertIn("Project Beta", digest)

    def test_render_deadline_warning(self):
        """Test deadline warning alert rendering."""
        tender = {"id": "T1", "title": "Fast Bid", "entity": "Gov Agency", "deadline": "2026-10-05"}
        warn = render_deadline_warning_template(tender, days_left=3)
        self.assertIn("URGENT: TENDER DEADLINE EXPIRING SOON", warn)
        self.assertIn("`3` Day(s)", warn)


class TestTrackerExecutionAndEnv(unittest.TestCase):
    def test_scan_opportunities_and_save(self):
        """Test full scan cycle and JSON catalog generation."""
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json", encoding="utf-8") as f:
            temp_path = Path(f.name)

        try:
            tracker = TenderTracker(output_file=temp_path)
            results = tracker.scan_opportunities(filter_status="OPEN")
            self.assertGreater(len(results), 0)

            # Verify saved file
            self.assertTrue(temp_path.exists())
            with open(temp_path, "r", encoding="utf-8") as rf:
                saved_data = json.load(rf)
            self.assertEqual(len(saved_data), len(results))
            self.assertEqual(saved_data[0]["status"], "OPEN")
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_env_file(self):
        """Test custom environment loader."""
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
            f.write("DEFAULT_FILTER_CATEGORY=Enterprise Software\n")
            f.write("OUTPUT_PATH=custom_tenders.json\n")
            temp_path = Path(f.name)

        try:
            loaded = load_env_file(temp_path)
            self.assertEqual(loaded.get("DEFAULT_FILTER_CATEGORY"), "Enterprise Software")
            self.assertEqual(loaded.get("OUTPUT_PATH"), "custom_tenders.json")
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
