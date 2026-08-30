"""Relative time quantities must not be treated as document ids (hard-delete / move)."""

from __future__ import annotations

import unittest

from app.document_id_parse import (
    looks_like_relative_time_scoped_document_request,
    parse_document_ids_for_delete_command,
    parse_document_ids_for_move_command,
)


class DeleteIdParseTests(unittest.TestCase):
    def test_explicit_id_still_works(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 254"), [254])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 214 287"), [214, 287])
        self.assertEqual(parse_document_ids_for_delete_command("удали документ [12]"), [12])
        self.assertEqual(parse_document_ids_for_delete_command("удали файл №7"), [7])

    def test_relative_days_are_not_a_document_id(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 3 дня назад"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали файл 2 дня назад"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали все документы 3 дня назад"), [])
        self.assertEqual(parse_document_ids_for_delete_command("убери документы 5 дней"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 1.5 дня назад"), [])

    def test_relative_weeks_hours_months_are_not_ids(self) -> None:
        self.assertEqual(parse_document_ids_for_delete_command("удали документ 2 недели назад"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали файл 5 часов назад"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 1 час назад"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали файлы 3 месяца назад"), [])
        self.assertEqual(parse_document_ids_for_delete_command("удали документы 4 года назад"), [])

    def test_id_plus_relative_time_keeps_only_the_id(self) -> None:
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ 254 за 3 дня"),
            [254],
        )
        self.assertEqual(
            parse_document_ids_for_delete_command("удали документ [18] 2 недели назад"),
            [18],
        )

    def test_relative_time_scope_is_detected(self) -> None:
        self.assertTrue(looks_like_relative_time_scoped_document_request("удали документы 3 дня назад"))
        self.assertTrue(looks_like_relative_time_scoped_document_request("удали все файлы 2 недели назад в этой папке"))
        self.assertFalse(looks_like_relative_time_scoped_document_request("удали документ 254"))
        self.assertFalse(looks_like_relative_time_scoped_document_request("удали все документы в этой папке"))


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

    def test_relative_time_is_not_a_move_id(self) -> None:
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси документ 3 дня назад в дело Банкротство"),
            [],
        )
        self.assertEqual(
            parse_document_ids_for_move_command("перенеси файл 2 недели назад в дело Банкротство"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
