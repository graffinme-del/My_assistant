"""Remedy-scoped chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го убытка» as document id 1. The calendar-period parser does not
recognize these phrases. «Арестовать», «описание», and «компенсировать» are not
this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_remedy import (
    mask_remedy_ordinals,
    remedy_blocks_bulk_document_mutation,
    looks_like_remedy_scoped_document_request,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_remedy_ordinals(raw)
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


class RemedyScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за убытки в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(_open_folder_wipe_phrase(text))
        self.assertTrue(remedy_blocks_bulk_document_mutation(text))
        for synonym in (
            "удали все документы за убыток в этой папке",
            "удали все документы по убыткам в этой папке",
            "удали все документы с убытками в этой папке",
            "удали все документы об убытках в этой папке",
            "удали все документы за взыскание убытков в этой папке",
            "удали все документы за прямой убыток в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за компенсацию морального вреда в этой папке",
            "удали все документы по компенсации в этой папке",
            "удали все документы за моральную компенсацию в этой папке",
            "удали все документы за арест в этой папке",
            "удали все документы под арест в этой папке",
            "удали все документы за наложение ареста в этой папке",
            "удали все документы по аресту в этой папке",
            "удали все документы за запрет в этой папке",
            "удали все документы за наложение запрета в этой папке",
            "удали все документы по запрету в этой папке",
            "удали все документы за опись в этой папке",
            "удали все документы по описи в этой папке",
            "удали все документы с описью в этой папке",
            "удали все документы за опись имущества в этой папке",
            "удали все документы за мировую в этой папке",
            "удали все документы за мировое соглашение в этой папке",
            "удали все документы по мировой в этой папке",
            "удали все документы за приговор в этой папке",
            "удали все документы за вынесение приговора в этой папке",
            "удали все документы по приговору в этой папке",
            "удали все документы с приговором в этой папке",
        ):
            self.assertIn("все документ", synonym.lower())
            self.assertIn("в этой", synonym.lower())
            self.assertTrue(_open_folder_wipe_phrase(synonym), synonym)
            self.assertEqual(_pre_fix_parse_ids(synonym), [], synonym)
            self.assertIsNone(parse_calendar_period_ru(synonym), synonym)
            self.assertTrue(remedy_blocks_bulk_document_mutation(synonym), synonym)

    def test_current_and_open_scopes_use_active_folder(self) -> None:
        for text in (
            "удали все документы за убытки в текущей папке",
            "удали все документы за компенсацию в открытой папке",
            "удали все документы по аресту из этой папки",
            "удали каждый документ за приговор в этой папке",
            "удали все файлы за опись в этой папке",
            "удали всех документов за мировую в этой папке",
        ):
            self.assertTrue(_open_folder_wipe_phrase(text), text)
            self.assertTrue(remedy_blocks_bulk_document_mutation(text), text)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го убытка",
            "удали документы 1-х убытков",
            "удали документы 1-й компенсации",
            "удали документы 1-го ареста",
            "удали документы 1-го запрета",
            "удали документы 1-й описи",
            "удали документы 1-ю опись",
            "удали документы 1-й мировой",
            "удали документы 1-го приговора",
            "удали документ 1 убытка",
            "удали документы 2-го приговора",
            "удали документы 2-го взыскания убытков",
        )
        for text in samples:
            expected = [2] if "2-" in text or text.startswith("удали документы 2") else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(remedy_blocks_bulk_document_mutation(text), text)

    def test_move_all_with_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за убытки в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(remedy_blocks_bulk_document_mutation(text))
        for phrase in (
            "перенеси все документы дела А40-12345/2025 за компенсацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за арест в папку Архив",
            "перенеси все документы дела А40-12345/2025 за запрет в папку Архив",
            "перенеси все документы дела А40-12345/2025 за опись в папку Архив",
            "перенеси все документы дела А40-12345/2025 за мировую в папку Архив",
            "перенеси все документы дела А40-12345/2025 за приговор в папку Архив",
            "перенеси документ 1-го убытка в дело Архив",
            "перенеси документ 1-го приговора в дело Архив",
        ):
            self.assertTrue(remedy_blocks_bulk_document_mutation(phrase), phrase)

    def test_move_command_does_not_take_ordinal_as_id(self) -> None:
        """move_documents_by_chat_command reads «документ <digits>» and would move document 1."""
        for text in (
            "перенеси документ 1-го убытка в дело Архив",
            "перенеси документ 1-й компенсации в дело Архив",
            "перенеси документ 1-го ареста в дело Архив",
            "перенеси документ 1-го приговора в дело Архив",
        ):
            pre = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
            safe = mask_remedy_ordinals(text)
            post = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
            self.assertEqual(pre, [1], text)
            self.assertEqual(post, [], text)
        kept = "перенеси документ 214 за убытки в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_remedy_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            remedy_blocks_bulk_document_mutation(
                "удали документ 254 за убытки",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за убытки"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за компенсацию"), [12])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за арест"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за приговор"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за убытки"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])

    def test_case_number_is_not_masked_as_ordinal(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за убытки в папку Архив"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214 за приговор"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за приговор"), [214])
        self.assertIn("214", mask_remedy_ordinals("удали документ 214 за убытки"))
        self.assertIn("12345", mask_remedy_ordinals(text))
        self.assertIn("2025", mask_remedy_ordinals(text))

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в этой папке без убытков",
            "удали все документы в этой папке без компенсации",
            "удали все документы в этой папке без ареста",
            "удали все документы в этой папке без запрета",
            "удали все документы в этой папке без описи",
            "удали все документы в этой папке без мировой",
            "удали все документы в этой папке без приговора",
            "удали все документы в папке Убытки",
            "перенеси все документы в папку Компенсация",
            "удали все документы из папки Арест",
            "удали все документы в папку Запрет",
            "удали все документы в папке Опись",
            "удали все документы в папке Мировая",
            "удали все документы в папке Приговор",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за полис в этой папке",
            "удали все документы за паспорт в этой папке",
            "удали все документы за штраф в этой папке",
            "удали все документы за гарантию в этой папке",
            "удали все документы за соглашение в этой папке",
            "удали все документы за взыскание в этой папке",
            "удали все документы и арестовать в этой папке",
            "удали все документы за арестованного в этой папке",
            "удали все документы за арестанта в этой папке",
            "удали все документы за запретить в этой папке",
            "удали все документы за запрещено в этой папке",
            "удали все документы за описание в этой папке",
            "удали все документы за описать в этой папке",
            "удали все документы за описывать в этой папке",
            "удали все документы за описку в этой папке",
            "удали все документы за приговорить в этой папке",
            "удали все документы за компенсировать в этой папке",
            "удали все документы за убыть в этой папке",
            "удали все документы за убытие в этой папке",
            "удали все документы за мировоззрение в этой папке",
            "удали документы 1-го полиса",
            "удали документы 1-го штрафа",
            "удали документы 1-го паспорта",
        ):
            self.assertFalse(looks_like_remedy_scoped_document_request(text), text)
            self.assertFalse(remedy_blocks_bulk_document_mutation(text), text)

    def test_adjective_and_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали все убыточные документы в этой папке",
            "удали все документы убыточные в этой папке",
            "удали все компенсационные документы в этой папке",
            "удали все арестные документы в этой папке",
            "удали все запретные документы в этой папке",
            "удали все документы во время ареста в этой папке",
            "удали все документы во время приговора в этой папке",
            "удали все документы за первый убыток в этой папке",
            "удали все документы за второй приговор в этой папке",
            "удали документы убытков в этой папке",
            "удали документы компенсации в этой папке",
            "удали документы приговора в этой папке",
            "удали документы описи в этой папке",
            "удали эти убытки в этой папке",
            "удали все документы за обеспечительный арест в этой папке",
            "удали все документы за обвинительный приговор в этой папке",
        ):
            self.assertTrue(remedy_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("remedy_blocks_bulk_document_mutation", source)
        self.assertIn("mask_remedy_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("remedy_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_remedy_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_remedy_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("remedy_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
