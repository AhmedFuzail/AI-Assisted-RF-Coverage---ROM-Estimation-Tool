import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from address_lookup import search_address


class AddressLookupTests(unittest.TestCase):
    @patch("address_lookup.urlopen")
    def test_returns_valid_suggestions(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps([
            {"display_name": "Tesla Gigafactory", "lat": "30.2219321", "lon": "-97.6187733"}
        ]).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = response

        suggestions, error = search_address("1 Tesla Road")

        self.assertIsNone(error)
        self.assertEqual(suggestions[0]["label"], "Tesla Gigafactory")
        self.assertEqual(suggestions[0]["latitude"], 30.2219321)

    @patch("address_lookup.urlopen", side_effect=HTTPError("url", 429, "Too Many Requests", None, None))
    def test_reports_rate_limit_response(self, _mock_urlopen):
        suggestions, error = search_address("1 Tesla Road")

        self.assertEqual(suggestions, [])
        self.assertEqual(error, "Address service returned HTTP 429. Please try again later.")

    @patch("address_lookup.urlopen", side_effect=URLError("offline"))
    def test_reports_network_failure(self, _mock_urlopen):
        suggestions, error = search_address("1 Tesla Road")

        self.assertEqual(suggestions, [])
        self.assertIn("unavailable", error)


if __name__ == "__main__":
    unittest.main()
