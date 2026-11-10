"""Alimony chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-е алименты» as document id 1.
A folder titled «Алименты» is not this guard. «оплата труда» is not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_alimony import (
    alimony_blocks_bulk_document_mutation,
    looks_like_alimony_scoped_document_request,
    mask_alimony_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_alimony_ordinals(raw)
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


def _wants_all(text: str) -> bool:
    low = (text or "").lower()
    return any(
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


def _pre_fix_selects_active_folder(text: str) -> bool:
    """Current main treats these substrings as the open folder once wants_all is true."""
    low = (text or "").lower()
    return _wants_all(text) and any(
        p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело")
    )


class AlimonyFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за алименты в этой папке",
            "удали все документы по алиментам в этой папке",
            "удали все документы об алиментах в этой папке",
            "удали все документы за взыскание алиментов в этой папке",
            "удали все документы за неуплату алиментов в этой папке",
            "удали все документы по выплате алиментов в этой папке",
            "удали все документы за задолженность по алиментам в этой папке",
            "удали все документы по размеру алиментов в этой папке",
            "удали все документы за задержку алиментов в этой папке",
            "удали все документы за платеж алиментов в этой папке",
            "удали все документы за алиментные обязательства в этой папке",
            "удали все документы за текущие алименты",
            "удали все документы за открытые алименты",
            "удали все документы за счёт алиментов в этой папке",
            "удали все файлы за алименты в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(alimony_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за алименты"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(alimony_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-е алименты", [1]),
            ("удали документы 1 алименты", [1]),
            ("удали документы 2-й алиментов", [2]),
            ("удали документы 1-е алиментные", [1]),
            ("удали документы 1-ю алиментную", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(alimony_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 алиментов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 алиментов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 зарплат"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 зарплат"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% алиментов"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% алиментов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% алиментов"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% алиментов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-е алименты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е алименты"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х алиментов"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х алиментов"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за алименты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за алименты"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я зарплата"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оплат труда"), [100])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за алименты в папку Архив",
            "перенеси все документы дела А40-12345/2025 по алиментам в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание алиментов в папку Архив",
            "перенеси все документы дела А40-12345/2025 за неуплату алиментов в папку Архив",
            "перенеси документ 1-е алименты в дело Архив",
            "перемести документ 100 алиментов в дело Архив",
        )
        for text in phrases:
            self.assertTrue(alimony_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за алименты в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_alimony_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 алиментов в папку Архив"
        masked = mask_alimony_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_alimony_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 зарплат в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            alimony_blocks_bulk_document_mutation(
                "удали документ 214 за алименты",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за алименты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по алиментам"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за алименты"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за алименты"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Алименты",
            "удали все документы в папке «Алименты»",
            "удали все документы по делу Алименты",
            "удали все документы по делу «Алименты»",
            "удали все документы в папке Алиментные платежи",
            "удали все документы без алиментов в этой папке",
            "удали все документы за алиментнее в этой папке",
            "удали все документы за алиментщика в этой папке",
            "удали все документы за оплату труда в этой папке",
            "удали все документы за зарплату в этой папке",
            "удали все документы за содержание в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Алименты",
            "собери все документы в папку Алименты по Гримме",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_alimony_scoped_document_request(text), text)
            self.assertFalse(alimony_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за алименты",
            "по алиментам",
            "об алиментах",
            "о алиментах",
            "на алименты",
            "с алиментов",
            "за «алименты»",
            "за взыскание алиментов",
            "по взысканию алиментов",
            "за неуплату алиментов",
            "по выплате алиментов",
            "за задержку алиментов",
            "по размеру алиментов",
            "за начисление алиментов",
            "по задолженности по алиментам",
            "за платеж алиментов",
            "по платежам алиментов",
            "за алиментные обязательства",
            "по алиментным платежам",
            "за алиментную задолженность",
            "за период алиментов",
            "в ходе алиментов",
            "за счет алиментов",
            "за счёт алиментов",
            "при алиментах",
            "за полные алименты",
            "за текущие алименты",
            "за открытые алименты",
            "до алиментов",
            "за первые алименты",
            "за мои алименты",
            "за наши алименты",
            "по твоим алиментам",
            "за ваши алименты",
            "во время алиментов",
            "во время алиментных обязательств",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_alimony_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("alimony_blocks_bulk_document_mutation", source)
        self.assertIn("mask_alimony_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("alimony_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_alimony_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_alimony_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("alimony_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
