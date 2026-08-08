"""Regression: Parser-API PDF harvest must not mix sibling/related cases."""

from __future__ import annotations

import unittest

from parser_api_client import extract_kad_pdf_url_entries_with_dates


def _case(number: str, url: str, related_url: str | None = None) -> dict:
    case = {
        "CaseNumber": number,
        "CaseInstances": [
            {
                "InstanceEvents": [
                    {
                        "Date": "2024-06-01",
                        "File": url,
                    }
                ]
            }
        ],
    }
    if related_url:
        case["RelatedNoise"] = related_url
    return case


class ParserCaseScopeTests(unittest.TestCase):
    def test_filters_to_requested_case_number(self) -> None:
        payload = {
            "Success": 1,
            "Cases": [
                _case(
                    "A40-111/2024",
                    "https://kad.arbitr.ru/Kad/PdfDocument/111/file.pdf",
                ),
                _case(
                    "A40-999/2023",
                    "https://kad.arbitr.ru/Kad/PdfDocument/999/file.pdf",
                ),
            ],
        }
        urls = [
            u
            for u, _ in extract_kad_pdf_url_entries_with_dates(
                payload, case_number="A40-111/2024"
            )
        ]
        self.assertEqual(urls, ["https://kad.arbitr.ru/Kad/PdfDocument/111/file.pdf"])

    def test_deep_walk_ignores_related_cases_outside_selected(self) -> None:
        payload = {
            "Success": 1,
            "Cases": [
                _case(
                    "A40-111/2024",
                    "https://kad.arbitr.ru/Kad/PdfDocument/111/file.pdf",
                ),
            ],
            "RelatedCases": [
                {
                    "CaseNumber": "A40-999/2023",
                    "File": "https://kad.arbitr.ru/Kad/PdfDocument/999/related.pdf",
                }
            ],
        }
        urls = [
            u
            for u, _ in extract_kad_pdf_url_entries_with_dates(
                payload, case_number="A40-111/2024"
            )
        ]
        self.assertEqual(urls, ["https://kad.arbitr.ru/Kad/PdfDocument/111/file.pdf"])
        self.assertNotIn("related.pdf", " ".join(urls))

    def test_cyrillic_a_normalizes_for_match(self) -> None:
        payload = {
            "Success": 1,
            "Cases": [
                _case(
                    "А40-111/2024",
                    "https://kad.arbitr.ru/Document/Pdf/abc/file.pdf",
                ),
                _case(
                    "A40-222/2024",
                    "https://kad.arbitr.ru/Document/Pdf/def/file.pdf",
                ),
            ],
        }
        urls = [
            u
            for u, _ in extract_kad_pdf_url_entries_with_dates(
                payload, case_number="A40-111/2024"
            )
        ]
        self.assertEqual(urls, ["https://kad.arbitr.ru/Document/Pdf/abc/file.pdf"])


if __name__ == "__main__":
    unittest.main()
