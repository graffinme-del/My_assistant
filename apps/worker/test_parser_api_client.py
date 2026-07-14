import unittest

from parser_api_client import safe_parser_diag_error


class SafeParserDiagErrorTests(unittest.TestCase):
    def test_redacts_keys_containing_s_characters(self) -> None:
        error = RuntimeError(
            "GET https://parser-api.com/parser/arbitr_api/details_by_id"
            "?key=super-secret&CaseId=123"
        )

        result = safe_parser_diag_error(error)

        self.assertNotIn("super-secret", result)
        self.assertIn("?key=***&CaseId=123", result)

    def test_redacts_key_case_insensitively_and_preserves_following_params(self) -> None:
        error = ConnectionError("request failed: https://example.test/path?KEY=abc123&Page=2")

        result = safe_parser_diag_error(error)

        self.assertNotIn("abc123", result)
        self.assertIn("?KEY=***&Page=2", result)


if __name__ == "__main__":
    unittest.main()
