"""«Ответ» / «отказ» / «согласие» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го ответа» as document id 1. The calendar-period parser does
not recognize these phrases, and the запрос guard does not match them.
«Отзыв» is not «ответ». «Соглашение» is not «согласие».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_reply import (
    looks_like_reply_scoped_document_request,
    mask_reply_ordinals,
    reply_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_reply_ordinals(raw)
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        safe,
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", safe, flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


def _pre_fix_parse_ids(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        text or "",
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", text or "", flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


def _open_folder_wipe_phrase(text: str) -> bool:
    """Same wants_all + open-folder checks as handle_delete_documents_chat."""
    low = (text or "").lower()
    wants_all = any(
        w in low
        for w in (
            "все документ",
            "все файлы",
            "всех документ",
            "всех файлов",
            "каждый документ",
            "каждый файл",
        )
    )
    open_folder = any(p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"))
    return wants_all and open_folder


class ReplyScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за ответ в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(_open_folder_wipe_phrase(text))
        self.assertTrue(reply_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за ответы в этой папке",
            "удали все документы по ответу в этой папке",
            "удали все документы с ответом в этой папке",
            "удали все документы с ответами в этой папке",
            "удали все документы на ответ в этой папке",
            "удали все документы из ответа в этой папке",
            "удали все документы в ответ в этой папке",
            "удали все документы об ответе в этой папке",
            "удали все документы за письменный ответ в этой папке",
            "удали все документы за мотивированный ответ в этой папке",
            "удали все документы за отказ в этой папке",
            "удали все документы за отказы в этой папке",
            "удали все документы по отказу в этой папке",
            "удали все документы с отказом в этой папке",
            "удали все документы об отказе в этой папке",
            "удали все документы за мотивированный отказ в этой папке",
            "удали все документы за согласие в этой папке",
            "удали все документы по согласию в этой папке",
            "удали все документы с согласием в этой папке",
            "удали все документы со согласием в этой папке",
            "удали все документы о согласии в этой папке",
            "удали все документы за несогласие в этой папке",
            "удали все документы за нотариальное согласие в этой папке",
            "удали все документы за информированное согласие в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertTrue(_open_folder_wipe_phrase(synonym), synonym)
            self.assertEqual(_pre_fix_parse_ids(synonym), [], synonym)
            self.assertIsNone(parse_calendar_period_ru(synonym), synonym)
            self.assertTrue(reply_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        for text in (
            "удали все документы за текущий ответ",
            "удали все документы за открытый отказ",
            "удали все документы за открытые согласия",
        ):
            low = text.lower()
            self.assertIn("все документ", low)
            self.assertTrue("текущ" in low or "открыт" in low)
            self.assertTrue(_open_folder_wipe_phrase(text), text)
            self.assertIsNone(parse_calendar_period_ru(text))
            self.assertTrue(reply_blocks_bulk_document_mutation(text), text)

    def test_case_number_scope_would_wipe_that_case(self) -> None:
        text = "удали все документы за ответ дела А53-13969/2026"
        self.assertIn("все документ", text.lower())
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertTrue(reply_blocks_bulk_document_mutation(text))
        self.assertTrue(
            reply_blocks_bulk_document_mutation(
                "удали все документы за отказ дела А40-12345/2025"
            )
        )
        self.assertTrue(
            reply_blocks_bulk_document_mutation(
                "удали все документы за согласие дела А40-12345/2025"
            )
        )

    def test_ordinal_wrong_id_trigger(self) -> None:
        """Pre-fix: the leading ordinal digit was document id 1 and that file was hard-deleted."""
        samples = (
            "удали документы 1-го ответа",
            "удали документы 1-й ответ",
            "удали документы 1-го отказа",
            "удали документы 1-й отказ",
            "удали документы 1-го согласия",
            "удали документы 1-е согласие",
            "удали документы 1-го несогласия",
            "удали документы 2-го ответа",
            "удали документы 2-го письменного отказа",
        )
        for text in samples:
            expected = [2] if text.startswith("удали документы 2-") else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(reply_blocks_bulk_document_mutation(text), text)

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за ответ в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(reply_blocks_bulk_document_mutation(text))
        self.assertTrue(
            reply_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за отказ в папку Архив"
            )
        )
        self.assertTrue(
            reply_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за согласие в папку Архив"
            )
        )
        self.assertTrue(
            reply_blocks_bulk_document_mutation(
                "перенеси все документы с ответами в папку Архив"
            )
        )
        self.assertTrue(
            reply_blocks_bulk_document_mutation(
                "перенеси документ 1-го ответа в дело Архив"
            )
        )
        self.assertTrue(
            reply_blocks_bulk_document_mutation(
                "перенеси документ 1-го отказа в дело Архив"
            )
        )
        self.assertTrue(
            reply_blocks_bulk_document_mutation(
                "перенеси документ 1-го согласия в дело Архив"
            )
        )

    def test_move_command_does_not_take_ordinal_as_id(self) -> None:
        """move_documents_by_chat_command reads «документ <digits>» and would move document 1."""
        for text, noun in (
            ("перенеси документ 1-го ответа в дело Архив", "ответа"),
            ("перенеси документ 1-го отказа в дело Архив", "отказа"),
            ("перенеси документ 1-го согласия в дело Архив", "согласия"),
        ):
            pre = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
            safe = mask_reply_ordinals(text)
            post = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
            self.assertEqual(pre, [1], noun)
            self.assertEqual(post, [], noun)
        kept = "перенеси документ 214 за ответ в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_reply_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            reply_blocks_bulk_document_mutation(
                "удали документ 254 за ответ",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за ответ"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за отказ"), [12])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за согласие"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за ответ"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за ответ в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за отказ"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за согласие"), [214])
        self.assertIn("214", mask_reply_ordinals("удали документ 214 за ответ"))
        self.assertIn("12345", mask_reply_ordinals(text))

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без ответа",
            "удали все документы в этой папке без отказа",
            "удали все документы в этой папке без согласия",
            "удали все документы в этой папке и дай ответ",
            "удали все документы в папке Ответ",
            "перенеси все документы в папку Отказ",
            "удали все документы из папки Согласие",
            "удали все документы в папку Ответ",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за запрос в этой папке",
            "удали все документы за разъяснение в этой папке",
            "удали все документы за отзыв в этой папке",
            "удали все документы за соглашение в этой папке",
            "удали все документы по ответчику в этой папке",
            "удали все документы за ответственность в этой папке",
            "удали все документы за соответствие в этой папке",
            "удали все документы по согласованию в этой папке",
            "удали все документы за разногласия в этой папке",
            "удали документы 1-го запроса",
            "удали документы 1-го отзыва",
            "удали документы 1-го соглашения",
            "отказаться удалить документы в этой папке",
        ):
            self.assertFalse(looks_like_reply_scoped_document_request(text), text)
            self.assertFalse(reply_blocks_bulk_document_mutation(text), text)

    def test_adjective_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все ответные документы в этой папке",
            "удали все документы ответные в этой папке",
            "удали все отказные документы в этой папке",
            "удали все согласительные документы в этой папке",
            "удали все документы за ответное письмо в этой папке",
            "удали все документы во время ответа в этой папке",
            "удали все документы во время отказа в этой папке",
            "удали все документы за первый ответ в этой папке",
            "удали все документы за второе согласие в этой папке",
            "удали документы ответа в этой папке",
            "удали документы отказа в этой папке",
            "удали документы согласия в этой папке",
        ):
            self.assertTrue(reply_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("reply_blocks_bulk_document_mutation", source)
        self.assertIn("mask_reply_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("reply_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_reply_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_reply_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("reply_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
