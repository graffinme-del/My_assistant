"""Company-liquidation chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-я ликвидация» as document id 1.
«ликвидировать» and a folder titled «Ликвидация» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_liquidation import (
    looks_like_liquidation_scoped_document_request,
    liquidation_blocks_bulk_document_mutation,
    mask_liquidation_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_liquidation_ordinals(raw)
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


class LiquidationFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за ликвидацию в этой папке",
            "удали все документы за ликвидацию общества в этой папке",
            "удали все документы по ликвидации в этой папке",
            "удали все документы за ликвидационный баланс в этой папке",
            "удали все документы по ликвидационному балансу в этой папке",
            "удали все документы за ликвидационную комиссию в этой папке",
            "удали все документы по ликвидационной стоимости в этой папке",
            "удали все документы за ликвидатора в этой папке",
            "удали все документы за текущую ликвидацию",
            "удали все документы за открытую ликвидацию",
            "удали все документы по балансу ликвидации в этой папке",
            "удали все документы в процессе ликвидации в этой папке",
            "удали все документы за процедуру ликвидации в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(liquidation_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за ликвидацию"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(liquidation_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я ликвидация", [1]),
            ("удали документы 1 ликвидация", [1]),
            ("удали документы 2-й ликвидации", [2]),
            ("удали документы 1-ю ликвидацию", [1]),
            ("удали документы 1-й ликвидационный баланс", [1]),
            ("удали документы 1-го ликвидатора", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(liquidation_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 ликвидаций"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 ликвидаций"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 реструктуризаций"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 реструктуризаций"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% ликвидации"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% ликвидации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% ликвидации"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% ликвидации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я ликвидация"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я ликвидация"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й ликвидации общества"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й ликвидации общества"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за ликвидацию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за ликвидационный баланс"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за ликвидацию"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я реструктуризация"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й зарплаты"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е алименты"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за ликвидацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ликвидационный баланс в папку Архив",
            "перенеси все документы дела А40-12345/2025 по ликвидационному балансу в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ликвидатора в папку Архив",
            "перенеси документ 1-я ликвидация в дело Архив",
            "перемести документ 1-ю ликвидацию в дело Архив",
        )
        for text in phrases:
            self.assertTrue(liquidation_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за ликвидацию в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_liquidation_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 ликвидаций в папку Архив"
        masked = mask_liquidation_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_liquidation_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 реструктуризаций в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            liquidation_blocks_bulk_document_mutation(
                "удали документ 214 за ликвидацию",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за ликвидацию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за ликвидационный баланс"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по ликвидации"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за ликвидацию"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за ликвидацию"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Ликвидация",
            "удали все документы в папке «Ликвидация»",
            "удали все документы по делу Ликвидация",
            "удали все документы по делу Ликвидационный баланс",
            "удали все документы без ликвидации в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за наблюдение в этой папке",
            "удали все документы за конкурсное производство в этой папке",
            "удали все документы за конкурсную массу в этой папке",
            "удали все документы за внешнее управление в этой папке",
            "удали все документы за финансовое оздоровление в этой папке",
            "удали все документы за реструктуризацию в этой папке",
            "удали все документы за реализацию в этой папке",
            "удали все документы за субсидиарную ответственность в этой папке",
            "удали все документы за зарплату в этой папке",
            "удали все документы за алименты в этой папке",
            "удали все документы за ликвидировать долг в этой папке",
            "удали все документы за ликвидированный долг в этой папке",
            "удали все документы за ликвидаторский сбор в этой папке",
            "удали все документы за баланс в этой папке",
            "удали все документы за продажу в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Ликвидация",
            "собери все документы в папку Ликвидация по Гримме",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_liquidation_scoped_document_request(text), text)
            self.assertFalse(liquidation_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за ликвидацию",
            "по ликвидации",
            "на ликвидации",
            "о ликвидации",
            "за ликвидации",
            "за ликвидацией",
            "за ликвидаций",
            "по ликвидациям",
            "о ликвидациях",
            "за ликвидациями",
            "за ликвидацию общества",
            "по балансу ликвидации",
            "за комиссию ликвидации",
            "по стоимости ликвидации",
            "за процедуру ликвидации",
            "в процессе ликвидации",
            "за счет ликвидации",
            "в ходе ликвидации",
            "в рамках ликвидации",
            "при ликвидации",
            "за полную ликвидацию",
            "за добровольную ликвидацию",
            "за принудительную ликвидацию",
            "за текущую ликвидацию",
            "за открытую ликвидацию",
            "за ликвидационный баланс",
            "по ликвидационному балансу",
            "за ликвидационную комиссию",
            "по ликвидационной стоимости",
            "за ликвидатора",
            "по ликвидатору",
            "до ликвидации",
            "за первую ликвидацию",
            "за мою ликвидацию",
            "за нашу ликвидацию",
            "по твоей ликвидации",
            "за вашу ликвидацию",
            "во время ликвидации",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_liquidation_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("liquidation_blocks_bulk_document_mutation", source)
        self.assertIn("mask_liquidation_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("liquidation_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_liquidation_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_liquidation_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("liquidation_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
