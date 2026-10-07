"""«Полис» / «паспорт» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го полиса» as document id 1. The calendar-period parser does
not recognize these phrases. «Полистать» and «паспортизация» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_identity import (
    identity_blocks_bulk_document_mutation,
    looks_like_identity_scoped_document_request,
    mask_identity_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_identity_ordinals(raw)
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


class IdentityScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за полис в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(_open_folder_wipe_phrase(text))
        self.assertTrue(identity_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за полисы в этой папке",
            "удали все документы по полису в этой папке",
            "удали все документы с полисом в этой папке",
            "удали все документы о полисе в этой папке",
            "удали все документы об полисе в этой папке",
            "удали все документы из полиса в этой папке",
            "удали все документы за страховой полис в этой папке",
            "удали все документы за полис ОСАГО в этой папке",
            "удали все документы из страхового полиса в этой папке",
            "удали все документы за паспорт в этой папке",
            "удали все документы за паспорта в этой папке",
            "удали все документы по паспорту в этой папке",
            "удали все документы с паспортом в этой папке",
            "удали все документы о паспорте в этой папке",
            "удали все документы за загранпаспорт в этой папке",
            "удали все документы за загран-паспорт в этой папке",
            "удали все документы по загранпаспорту в этой папке",
            "удали все документы за техпаспорт в этой папке",
            "удали все документы за технический паспорт в этой папке",
            "удали все документы за заграничный паспорт в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertTrue(_open_folder_wipe_phrase(synonym), synonym)
            self.assertEqual(_pre_fix_parse_ids(synonym), [], synonym)
            self.assertIsNone(parse_calendar_period_ru(synonym), synonym)
            self.assertTrue(identity_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        for text in (
            "удали все документы за полис в текущей папке",
            "удали все документы за паспорт в открытой папке",
            "удали все документы по полису из этой папки",
            "удали каждый документ за паспорт в этой папке",
        ):
            self.assertTrue(_open_folder_wipe_phrase(text), text)
            self.assertTrue(identity_blocks_bulk_document_mutation(text), text)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го полиса",
            "удали документы 1-го паспорта",
            "удали документы 1-й паспорт",
            "удали документы 1-го загранпаспорта",
            "удали документы 1-го техпаспорта",
            "удали документ 1-го полиса",
            "удали документ 1 полиса",
            "удали документы 2-го полиса",
            "удали документы 2-го технического паспорта",
        )
        for text in samples:
            expected = [2] if "2-" in text or text.startswith("удали документы 2") else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(identity_blocks_bulk_document_mutation(text), text)

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за полис в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(identity_blocks_bulk_document_mutation(text))
        self.assertTrue(
            identity_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за паспорт в папку Архив"
            )
        )
        self.assertTrue(
            identity_blocks_bulk_document_mutation(
                "перенеси все документы дела А40-12345/2025 за загранпаспорт в папку Архив"
            )
        )
        self.assertTrue(
            identity_blocks_bulk_document_mutation("перенеси документ 1-го полиса в дело Архив")
        )
        self.assertTrue(
            identity_blocks_bulk_document_mutation("перенеси документ 1-го паспорта в дело Архив")
        )

    def test_move_command_does_not_take_ordinal_as_id(self) -> None:
        """move_documents_by_chat_command reads «документ <digits>» and would move document 1."""
        for text, noun in (
            ("перенеси документ 1-го полиса в дело Архив", "полиса"),
            ("перенеси документ 1-го паспорта в дело Архив", "паспорта"),
            ("перенеси документ 1-й загранпаспорт в дело Архив", "загранпаспорт"),
        ):
            pre = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
            safe = mask_identity_ordinals(text)
            post = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
            self.assertEqual(pre, [1], noun)
            self.assertEqual(post, [], noun)
        kept = "перенеси документ 214 за полис в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_identity_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            identity_blocks_bulk_document_mutation(
                "удали документ 254 за полис",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за полис"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за паспорт"), [12])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за загранпаспорт"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за полис"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за полис в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за паспорт"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за паспорт"), [214])
        self.assertIn("214", mask_identity_ordinals("удали документ 214 за полис"))
        self.assertIn("12345", mask_identity_ordinals(text))

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без полиса",
            "удали все документы в этой папке без паспорта",
            "удали все документы в папке Полис",
            "перенеси все документы в папку Паспорт",
            "удали все документы из папки Полис",
            "удали все документы в папку Паспорт",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за штраф в этой папке",
            "удали все документы за гарантию в этой папке",
            "удали все документы за убытки в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за ОСАГО в этой папке",
            "удали все документы за ПТС в этой папке",
            "удали все документы и полистай в этой папке",
            "удали все документы за паспортизацию в этой папке",
            "удали документы 1-го штрафа",
            "удали документы 1-й гарантии",
            "удали документы 1-го ответа",
        ):
            self.assertFalse(looks_like_identity_scoped_document_request(text), text)
            self.assertFalse(identity_blocks_bulk_document_mutation(text), text)

    def test_adjective_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все полисные документы в этой папке",
            "удали все документы полисные в этой папке",
            "удали все паспортные документы в этой папке",
            "удали все документы паспортные в этой папке",
            "удали все документы во время полиса в этой папке",
            "удали все документы во время паспорта в этой папке",
            "удали все документы за первый полис в этой папке",
            "удали все документы за второй паспорт в этой папке",
            "удали документы полиса в этой папке",
            "удали документы паспорта в этой папке",
            "удали документы страхового полиса в этой папке",
        ):
            self.assertTrue(identity_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("identity_blocks_bulk_document_mutation", source)
        self.assertIn("mask_identity_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("identity_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_identity_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_identity_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("identity_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
