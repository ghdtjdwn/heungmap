from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.fetch_tourapi_festivals import (
    TourApiError,
    build_request_url,
    build_summary,
    extract_items,
    parse_env_file,
    write_json_safely,
)


def successful_payload(items, total_count=None):
    return {
        "response": {
            "header": {"resultCode": "0000", "resultMsg": "OK"},
            "body": {
                "items": {"item": items} if items else "",
                "totalCount": len(items) if total_count is None else total_count,
            },
        }
    }


class ParseEnvFileTest(unittest.TestCase):
    def test_reads_plain_quoted_and_exported_values(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "# comment\nPLAIN=value\nQUOTED='two words'\nexport EXPORTED=yes\n",
                encoding="utf-8",
            )

            self.assertEqual(
                parse_env_file(env_file),
                {"PLAIN": "value", "QUOTED": "two words", "EXPORTED": "yes"},
            )

    def test_missing_file_returns_empty_mapping(self):
        self.assertEqual(parse_env_file(Path("does-not-exist")), {})


class RequestTest(unittest.TestCase):
    def test_builds_official_search_festival_request(self):
        url = build_request_url(
            service_key="secret+/=",
            start_date="20250101",
            end_date="20251231",
            page=2,
            rows=100,
        )

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.path, "/B551011/KorService2/searchFestival2")
        self.assertEqual(query["serviceKey"], ["secret+/="])
        self.assertEqual(query["MobileOS"], ["ETC"])
        self.assertEqual(query["MobileApp"], ["HeungMap"])
        self.assertEqual(query["_type"], ["json"])
        self.assertEqual(query["eventStartDate"], ["20250101"])
        self.assertEqual(query["eventEndDate"], ["20251231"])
        self.assertEqual(query["pageNo"], ["2"])
        self.assertEqual(query["numOfRows"], ["100"])


class ResponseTest(unittest.TestCase):
    def test_extracts_list_items_and_total_count(self):
        items, total_count = extract_items(
            successful_payload([{"contentid": "1"}, {"contentid": "2"}], 20)
        )

        self.assertEqual(items, [{"contentid": "1"}, {"contentid": "2"}])
        self.assertEqual(total_count, 20)

    def test_wraps_single_item_as_list(self):
        payload = successful_payload([{"contentid": "1"}])
        payload["response"]["body"]["items"]["item"] = {"contentid": "1"}

        items, _ = extract_items(payload)

        self.assertEqual(items, [{"contentid": "1"}])

    def test_accepts_empty_items(self):
        items, total_count = extract_items(successful_payload([], 0))

        self.assertEqual(items, [])
        self.assertEqual(total_count, 0)

    def test_rejects_api_error_without_secret_data(self):
        payload = {
            "response": {
                "header": {"resultCode": "30", "resultMsg": "UNREGISTERED"},
                "body": {},
            }
        }

        with self.assertRaisesRegex(TourApiError, "TourAPI 오류 30"):
            extract_items(payload)


class SummaryTest(unittest.TestCase):
    def test_reports_missing_and_duplicate_identifiers(self):
        complete = {
            "contentid": "1",
            "title": "축제",
            "eventstartdate": "20250101",
            "eventenddate": "20250102",
            "areacode": "1",
            "sigungucode": "2",
        }
        duplicate = {**complete, "title": ""}

        summary = build_summary(
            items=[complete, duplicate],
            total_count=2,
            start_date="20250101",
            end_date="20251231",
            page=1,
            rows=100,
            retrieved_at="2026-09-04T18:00:00+09:00",
            raw_path=Path("data/raw/sample.json"),
        )

        self.assertEqual(summary["gate_status"], "needs_review")
        self.assertEqual(summary["missing_counts"]["title"], 1)
        self.assertEqual(summary["duplicate_content_id_count"], 1)

    def test_marks_complete_unique_sample_ready(self):
        item = {
            "contentid": "1",
            "title": "축제",
            "eventstartdate": "20250101",
            "eventenddate": "20250102",
            "areacode": "1",
            "sigungucode": "2",
        }

        summary = build_summary(
            items=[item],
            total_count=1,
            start_date="20250101",
            end_date="20251231",
            page=1,
            rows=100,
            retrieved_at="2026-09-04T18:00:00+09:00",
            raw_path=Path("data/raw/sample.json"),
        )

        self.assertEqual(summary["gate_status"], "tourapi_sample_ready")


class WriteJsonTest(unittest.TestCase):
    def test_refuses_to_overwrite_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text("existing", encoding="utf-8")

            with self.assertRaisesRegex(TourApiError, "이미 있습니다"):
                write_json_safely(path, {"new": True}, overwrite=False)

            self.assertEqual(path.read_text(encoding="utf-8"), "existing")

    def test_writes_utf8_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "result.json"

            write_json_safely(path, {"title": "축제"}, overwrite=False)

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")), {"title": "축제"}
            )


if __name__ == "__main__":
    unittest.main()
