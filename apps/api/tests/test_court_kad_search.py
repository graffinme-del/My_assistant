import unittest

from app.court_kad_search import CourtSearchRequest, apply_active_case_number_to_kad_request


class ActiveCaseNumberOverrideTest(unittest.TestCase):
    def test_unrelated_participant_query_is_not_rewritten_to_active_case(self) -> None:
        request = CourtSearchRequest(query_type="participant_name", query_value="Петров")

        result = apply_active_case_number_to_kad_request(
            "найди в кад по данным Петров",
            request,
            active_case_title="Банкротство Эмиль",
            active_case_number="А40-12345/2025",
        )

        self.assertEqual(result, request)

    def test_matching_active_case_title_still_uses_folder_case_number(self) -> None:
        request = CourtSearchRequest(query_type="participant_name", query_value="Эмиль")

        result = apply_active_case_number_to_kad_request(
            "проверь КАД по делу банкротство Эмиль",
            request,
            active_case_title="Банкротство Эмиль",
            active_case_number="А40-12345/2025",
        )

        self.assertEqual(result.query_type, "case_number")
        self.assertEqual(result.query_value, "A40-12345/2025")

    def test_generic_title_word_does_not_align_different_case(self) -> None:
        request = CourtSearchRequest(query_type="participant_name", query_value="Петров")

        result = apply_active_case_number_to_kad_request(
            "проверь КАД по делу банкротство Петров",
            request,
            active_case_title="Банкротство Эмиль",
            active_case_number="А40-12345/2025",
        )

        self.assertEqual(result, request)


if __name__ == "__main__":
    unittest.main()
