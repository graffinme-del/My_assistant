"""Clock times and slash/ISO dates must not be treated as document ids (hard-delete / move)."""

from __future__ import annotations

import unittest

from app.document_id_parse import (
    looks_like_clock_or_slash_iso_date_scoped_document_request,
    parse_document_ids_for_delete_command,
    parse_document_ids_for_move_command,
)


class DeleteIdParseTests(unittest.TestCase):
    def test_explicit_id_still_works(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 254"), [254])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 214 287"), [214, 287])
        self.assertEqual(parse_document_ids_for_delete_command("удали документ [12]"), [12])
        self.assertEqual(parse_document_ids_for_delete_command("удали файл №7"), [7])

    def test_clock_time_is_not_a_document_id(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 15:00"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 15:30"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали файл 9:05"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали все документы 15:00"), [])
        self.assertEqual(parse_document_ids_for_delete_command("убери документы 15:00:01"), [])

    def test_slash_date_is_not_a_document_id(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали файл 15/03/2026"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 15/03"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали все документы 03/15/2026"), [])

    def test_iso_and_hyphen_date_are_not_document_ids(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 2026-03-15"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали файл 15-03-2026"), [])

    def test_ordinal_day_chisla_is_not_a_document_id(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 15 числа"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 15-го числа"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали все документы 15 числа"), [])
        self.assertEqual(parse_document_ids_for_delete_command("убери файл 15-го"), [])

    def test_id_plus_clock_or_date_keeps_only_the_id(self) -> None:
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ 254 в 15:00"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ 254 от 15/03/2026"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ [18] 15 числа"),
            [18],
        )

    def test_clock_or_date_scope_is_detected(self) -> None:
        self.assertTrue(
            looks_like_clock_or_slash_iso_date_scoped_document_request(
                "удали все документы 15:00 в этой папке"
            )
        )
        self.assertTrue(
            looks_like_clock_or_slash_iso_date_scoped_document_request(
                "удали все документы 15 числа в этой папке"
            )
        )
        self.assertTrue(
            looks_like_clock_or_slash_iso_date_scoped_document_request(
                "удали файл 15/03/2026"
            )
        )
        self.assertFalse(looks_like_clock_or_slash_iso_date_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_clock_or_slash_iso_date_scoped_document_request(
                "удали все документы в этой папке"
            )
        )


class MoveIdParseTests(unittest.TestCase):
    def test_named_id_still_works(self) -> None:
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ 4 в дело Банкротство"),
            [4],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ [18] в дело Банкротство"),
            [18],
        )

    def test_clock_and_slash_date_are_not_move_ids(self) -> None:
        self.assertEqual(
            parse_document_ids_for_move_command("перемести документ 15:00 в дело Банкротство"),
            [],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перемести документ 15/03/2026 в дело Банкротство"),
            [],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перемести документ 15 числа в дело Банкротство"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
