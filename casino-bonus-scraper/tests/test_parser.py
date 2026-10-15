"""Parser, model-output and fetch tests. No network, no real API calls."""
import json
import os
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import scraper  # noqa: E402

SNIPPET = "Alpha Casino: 100% up to £200 bonus. Wagering 35x bonus. Minimum deposit £20."
TEXT = "Menu\nAlpha Casino\n100% up to £200 bonus\n35x wagering\nMin deposit £20\nBeta Casino\nBonus 50 free spins"


class FakeResponse:
    def __init__(self, text="", status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class FakeSession:
    def __init__(self, responses=None, error=None):
        self.responses, self.error, self.calls = responses or {}, error, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.responses.get(url, FakeResponse("", 404))


class FakeClient:
    """Mimics openai.OpenAI().chat.completions.create(...)."""
    def __init__(self, content=None, error=None):
        self.chat = mock.Mock()
        if error:
            self.chat.completions.create.side_effect = error
        else:
            msg = mock.Mock(content=content)
            self.chat.completions.create.return_value = mock.Mock(choices=[mock.Mock(message=msg)])


class WageringTests(unittest.TestCase):
    def test_recognises_multipliers(self):
        for text in ("35x", "35 x wagering", "35× bonus", "35 times the bonus", "x35"):
            self.assertEqual(scraper.find_wagering_multiplier(text), "35x", text)

    def test_no_multiplier(self):
        self.assertIsNone(scraper.find_wagering_multiplier("Great welcome offer"))


class SnippetTests(unittest.TestCase):
    def test_finds_passage_and_stops_at_next_casino(self):
        snippets = scraper.find_snippets(TEXT, ["Alpha Casino", "Beta Casino"])
        self.assertIn("35x", snippets["Alpha Casino"])
        self.assertNotIn("Beta", snippets["Alpha Casino"])

    def test_missing_casino_gives_none(self):
        self.assertIsNone(scraper.find_snippets(TEXT, ["Gamma Casino"])["Gamma Casino"])

    def test_extract_text_drops_scripts(self):
        text = scraper.extract_text("<p>Hello</p><script>alert(1)</script>")
        self.assertEqual(text, "Hello")


class NoAiTableTests(unittest.TestCase):
    def test_extracts_only_explicit_table_values(self):
        html = """
        <table>
          <thead><tr><th>Casino</th><th>Welcome Bonus</th><th>Best For</th></tr></thead>
          <tbody>
            <tr><td>Jackpot City</td><td>R2,000 Match Bonus Or Up To 350 Free Spins</td><td>Flexible bonus choice</td></tr>
            <tr><td>YesPlay</td><td>100% First Deposit Bonus</td><td>Fast withdrawals</td></tr>
            <tr><td>Jabulabets</td><td>Up To R30,000 + 245 Free Spins</td><td>Biggest bonus value</td></tr>
          </tbody>
        </table>
        """
        records = scraper.extract_bonus_table(html, ["Jackpot City", "YesPlay", "Jabulabets"])
        self.assertEqual(records["Jackpot City"]["welcome_bonus"], "R2,000 Match Bonus Or Up To 350 Free Spins")
        self.assertEqual(records["YesPlay"]["welcome_bonus"], "100% First Deposit Bonus")
        self.assertEqual(records["Jabulabets"]["welcome_bonus"], "Up To R30,000 + 245 Free Spins")
        self.assertTrue(all(record["wagering_requirement"] is None for record in records.values()))
        self.assertTrue(all(record["minimum_deposit"] is None for record in records.values()))

    def test_extracts_wagering_and_deposit_only_from_labeled_columns(self):
        html = """
        <table><tr><th>Casino</th><th>Welcome Bonus</th>
          <th>Wagering Requirement</th><th>Minimum Deposit</th></tr>
          <tr><td>Alpha</td><td>100% up to R1,000</td><td>35x bonus</td><td>R100</td></tr>
        </table>
        """
        record = scraper.extract_bonus_table(html, ["Alpha"])["Alpha"]
        self.assertEqual(record["wagering_requirement"], "35x")
        self.assertEqual(record["minimum_deposit"], "R100")


class ModelOutputTests(unittest.TestCase):
    def test_valid_output(self):
        raw = json.dumps({"welcome_bonus": "100% up to £200", "wagering_requirement": "35x bonus",
                          "minimum_deposit": "£20"})
        fields, notes = scraper.parse_model_output(raw, SNIPPET)
        self.assertEqual(fields["wagering_requirement"], "35x")
        self.assertEqual(fields["minimum_deposit"], "£20")
        self.assertEqual(notes, [])

    def test_unknown_minimum_deposit_is_null(self):
        raw = json.dumps({"welcome_bonus": "100% up to £200", "wagering_requirement": "35x",
                          "minimum_deposit": None})
        fields, _ = scraper.parse_model_output(raw, SNIPPET)
        self.assertIsNone(fields["minimum_deposit"])
        self.assertEqual(scraper.status_for(fields), "partial")

    def test_all_missing_terms(self):
        raw = json.dumps({k: "unknown" for k in scraper.FIELDS})
        fields, _ = scraper.parse_model_output(raw, SNIPPET)
        self.assertTrue(all(v is None for v in fields.values()))

    def test_malformed_output_rejected(self):
        for bad in ("not json", "[]", json.dumps({"welcome_bonus": "x"}),
                    json.dumps({"welcome_bonus": 5, "wagering_requirement": None, "minimum_deposit": None})):
            with self.assertRaises(scraper.ModelOutputError, msg=bad):
                scraper.parse_model_output(bad, SNIPPET)

    def test_hallucinated_number_discarded(self):
        raw = json.dumps({"welcome_bonus": "100% up to £500", "wagering_requirement": "35x",
                          "minimum_deposit": "£20"})
        fields, notes = scraper.parse_model_output(raw, SNIPPET)
        self.assertIsNone(fields["welcome_bonus"])
        self.assertTrue(notes)


class ProcessCasinoTests(unittest.TestCase):
    URL = "https://example.com/promos"

    def test_source_url_preserved_and_complete(self):
        client = FakeClient(json.dumps({"welcome_bonus": "100% up to £200", "wagering_requirement": "35x",
                                        "minimum_deposit": "£20"}))
        rec = scraper.process_casino("Alpha Casino", SNIPPET, self.URL, client, "m")
        self.assertEqual(rec["source_url"], self.URL)
        self.assertEqual(rec["extraction_status"], "complete")

    def test_api_failure_marks_failed(self):
        rec = scraper.process_casino("Alpha Casino", SNIPPET, self.URL, FakeClient(error=RuntimeError("boom")), "m")
        self.assertEqual(rec["extraction_status"], "failed")
        self.assertIn("boom", rec["notes"])

    def test_missing_snippet_is_not_found(self):
        rec = scraper.process_casino("Gamma", None, self.URL, FakeClient("{}"), "m")
        self.assertEqual(rec["extraction_status"], "not_found")
        self.assertIsNone(rec["welcome_bonus"])


class FetchTests(unittest.TestCase):
    URL = "https://example.com/promos"

    def test_network_error(self):
        with self.assertRaises(scraper.FetchError):
            scraper.fetch_page(self.URL, "ua", FakeSession(error=requests.ConnectionError("down")))

    def test_http_error(self):
        with self.assertRaises(scraper.FetchError):
            scraper.fetch_page(self.URL, "ua", FakeSession({self.URL: FakeResponse("", 500)}))

    def test_robots_disallow(self):
        session = FakeSession({"https://example.com/robots.txt": FakeResponse("User-agent: *\nDisallow: /")})
        with self.assertRaises(scraper.RobotsDisallowed):
            scraper.check_robots(self.URL, "BonusAtlasBot/1.0", session)

    def test_robots_allow_and_missing(self):
        scraper.check_robots(self.URL, "ua", FakeSession({"https://example.com/robots.txt": FakeResponse("User-agent: *\nDisallow:")}))
        scraper.check_robots(self.URL, "ua", FakeSession())  # 404 -> allowed

    def test_robots_unreachable_refuses(self):
        with self.assertRaises(scraper.RobotsDisallowed):
            scraper.check_robots(self.URL, "ua", FakeSession(error=requests.Timeout("slow")))

    def test_missing_api_key(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(scraper.ScraperError):
                scraper.make_client()


if __name__ == "__main__":
    unittest.main()


class RegressionTests(unittest.TestCase):
    """Bugs found in review: substring number matching and partial-word name matching."""

    def test_number_must_match_whole_number(self):
        self.assertFalse(scraper.numbers_supported("35x", "Wagering is 350x the bonus"))
        self.assertFalse(scraper.numbers_supported("£20", "Minimum deposit £200"))
        self.assertFalse(scraper.numbers_supported("35x", "rate of 1.35 applies"))
        self.assertTrue(scraper.numbers_supported("35x", "Wagering is 35x the bonus."))
        self.assertTrue(scraper.numbers_supported("£1,000", "Up to £1,000 bonus"))

    def test_casino_name_must_be_whole_word(self):
        text = "Alphabet Casino: 100% up to £50, 30x wagering.\nAlpha: 200% up to £100, 40x wagering, min deposit £20"
        snip = scraper.find_snippets(text, ["Alpha", "Beta", "Gamma"])
        self.assertTrue(snip["Alpha"].startswith("Alpha: 200%"))
        self.assertIsNone(snip["Beta"])
