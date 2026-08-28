"""Date-like tokens must not be treated as document ids (hard-delete / move)."""

from __future__ import annotations

import unittest

from app.document_id_parse import (
    parse_document_ids_for_delete_command,
    parse_document_ids_for_move_command,
)


class DeleteIdParseTests(unittest.TestCase):
    def test_explicit_id_still_works(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 254"), [254])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 214 287"), [214, 287])
        self.assertEqual(parse_document_ids_for_delete_command("удали документ [12]"), [12])
        self.assertEqual(parse_document_ids_for_delete_command("удали файл №7"), [7])

    def test_calendar_date_is_not_a_document_id(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали файл 12.05.2026"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 12.05"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы: 15.03.2025"), [])
        self.assertEqual(parse_document_ids_for_delete_command("убери документ 1.2 определения"), [])

    def test_id_plus_date_keeps_only_the_id(self) -> None:
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ 254 от 12.05.2026"),
            [254],
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

    def test_date_is_not_a_move_id(self) -> None:
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ 12.05.2026 в дело Банкротство"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
