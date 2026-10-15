"""JSON output, schema and failed-scrape safety tests."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import scraper  # noqa: E402
from tests.test_parser import FakeClient, FakeResponse, FakeSession, TEXT  # noqa: E402

URL = "https://example.com/promos"
GOOD = {"welcome_bonus": "100% up to £200", "wagering_requirement": "35x", "minimum_deposit": "£20"}


def good_dataset():
    rec = scraper.build_record("Alpha", URL, GOOD, "complete")
    return scraper.assemble_dataset(URL, [rec])


class DatasetTests(unittest.TestCase):
    def test_valid_dataset(self):
        self.assertEqual(scraper.validate_dataset(good_dataset()), [])

    def test_initial_casinos_json_is_valid_and_empty(self):
        path = os.path.join(os.path.dirname(__file__), "..", "casinos.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["casinos"], [])
        self.assertIsNone(data["last_updated"])

    def test_detects_problems(self):
        data = good_dataset()
        data["casinos"].append(dict(data["casinos"][0]))          # duplicate
        data["casinos"][0]["source_url"] = "not a url"            # bad URL
        del data["casinos"][0]["notes"]                           # missing field
        data["casinos"][0]["minimum_deposit"] = 20                # wrong type
        errors = " | ".join(scraper.validate_dataset(data))
        for expected in ("Duplicate", "invalid source_url", "missing 'notes'", "must be a string"):
            self.assertIn(expected, errors)

    def test_timestamp_is_iso8601(self):
        from datetime import datetime
        datetime.fromisoformat(good_dataset()["last_updated"])


class WriteSafetyTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "casinos.json")

    def tearDown(self):
        self.dir.cleanup()

    def test_writes_valid_json(self):
        self.assertTrue(scraper.write_json_safely(self.path, good_dataset()))
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["casinos"][0]["source_url"], URL)

    def test_failed_scrape_does_not_overwrite_good_data(self):
        scraper.write_json_safely(self.path, good_dataset())
        with open(self.path, encoding="utf-8") as fh:
            before = fh.read()
        empty = scraper.assemble_dataset(URL, [scraper.build_record("Alpha", URL, status="failed", notes="x")])
        self.assertFalse(scraper.write_json_safely(self.path, empty))
        self.assertFalse(scraper.write_json_safely(self.path, scraper.assemble_dataset(URL, [])))
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_full_run_with_mocks(self):
        html = "<html><body>" + TEXT.replace("\n", "<br>") + "</body></html>"
        session = FakeSession({"https://example.com/robots.txt": FakeResponse("User-agent: *\nDisallow:"),
                               URL: FakeResponse(html)})
        client = FakeClient(json.dumps(GOOD))
        code = scraper.run(URL, ["Alpha Casino", "Beta Casino", "Gamma Casino"], self.path, "m", "ua",
                           client=client, session=session)
        self.assertEqual(code, 2)  # Gamma not found -> written but incomplete
        with open(self.path, encoding="utf-8") as fh:
            statuses = {r["casino_name"]: r["extraction_status"] for r in json.load(fh)["casinos"]}
        self.assertEqual(statuses["Gamma Casino"], "not_found")

    def test_run_fails_without_writing_on_http_error(self):
        session = FakeSession({"https://example.com/robots.txt": FakeResponse("User-agent: *\nDisallow:"),
                               URL: FakeResponse("", 503)})
        with self.assertRaises(scraper.FetchError):
            scraper.run(URL, ["A", "B", "C"], self.path, "m", "ua", client=FakeClient("{}"), session=session)
        self.assertFalse(os.path.exists(self.path))

    def test_requires_exactly_three_casinos(self):
        with self.assertRaises(scraper.ScraperError):
            scraper.run(URL, ["A", "B"], self.path, "m", "ua", client=FakeClient("{}"))


if __name__ == "__main__":
    unittest.main()
