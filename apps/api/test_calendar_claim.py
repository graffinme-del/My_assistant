"""Claim chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
«по предъявлению претензии» as a PDF-text hint.
parse_document_ids_for_delete_command read «1-я претензия» as document id 1.

A folder titled «Претензия» is not this guard. «без претензии» is not
this guard. «претензионный», «претенциозный», «упущенная прибыль»,
«наследство», «упущенная выгода», and «ущерб» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_claim import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    claim_blocks_bulk_document_mutation,
    looks_like_claim_scoped_document_request,
    mask_claim_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_claim_ordinals(raw)
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


def _pre_fix_pdf_hint(text: str) -> str | None:
    """Tail of «по <phrase>» that handle_delete_documents_chat searches across PDFs."""
    m2 = re.search(
        r"(?<![а-яё])по\s+(?!делу\b)([А-Яа-яЁё][А-Яа-яЁё'\-]*(?:\s+[А-Яа-яЁё][А-Яа-яЁё'\-]*){1,6})"
        r"(?:\s*[!?.…]*)?(?:\s*$|\n)",
        text or "",
        flags=re.IGNORECASE,
    )
    if not m2:
        return None
    return m2.group(1).strip()


class ClaimFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за претензию в этой папке",
            "удали все документы по претензии в этой папке",
            "удали все документы о претензии в этой папке",
            "удали все документы об претензии в этой папке",
            "удали все документы за предъявление претензии в этой папке",
            "удали все документы за направление претензии в этой папке",
            "удали все документы за отзыв претензии в этой папке",
            "удали все документы за удовлетворение претензии в этой папке",
            "удали все документы за рассмотрение претензии в этой папке",
            "удали все документы за отклонение претензии в этой папке",
            "удали все документы за оставление претензии в этой папке",
            "удали все документы за обоснование претензии в этой папке",
            "удали все документы за сумму претензии в этой папке",
            "удали все документы за размер претензии в этой папке",
            "удали все документы за оценку претензии в этой папке",
            "удали все документы за расчет претензии в этой папке",
            "удали все документы за расчёт претензии в этой папке",
            "удали все документы за открытие претензии",
            "удали все документы за текущую претензию",
            "удали все документы за открытую претензию",
            "удали все документы за досудебную претензию в этой папке",
            "удали все документы за мотивированную претензию в этой папке",
            "удали все файлы за претензию в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(claim_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за претензию"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(claim_blocks_bulk_document_mutation(numbered), numbered)
        filing = "удали все документы дела А40-12345/2025 за предъявление претензии"
        self.assertTrue(claim_blocks_bulk_document_mutation(filing), filing)

        hint = "удали документы по предъявлению претензии"
        self.assertEqual(_pre_fix_pdf_hint(hint), "предъявлению претензии")
        self.assertTrue(claim_blocks_bulk_document_mutation(hint), hint)
        hinted_all = "удали все документы по сумме претензии"
        self.assertEqual(_pre_fix_pdf_hint(hinted_all), "сумме претензии")
        self.assertTrue(claim_blocks_bulk_document_mutation(hinted_all), hinted_all)
        single = "удали документы по претензии"
        self.assertIsNone(_pre_fix_pdf_hint(single))
        self.assertTrue(claim_blocks_bulk_document_mutation(single), single)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я претензия", [1]),
            ("удали документы 1 претензия", [1]),
            ("удали документы 2-ю претензию", [2]),
            ("удали документы 1-й претензии", [1]),
            ("удали документы 1-е претензия", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(claim_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 претензий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 претензий"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 убытков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 убытков"), [100])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12,5% претензии"),
            [5, 12],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% претензии"), [])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12.5% претензии"),
            [12],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% претензии"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я претензия"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я претензия"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-ю претензию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-ю претензию"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за претензию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(
            _parse_ids_like_main("удали документы 214 287 за претензию"),
            [214, 287],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214-е наследство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я упущенная прибыль"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за претензию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за предъявление претензии в папку Архив",
            "перенеси все документы дела А40-12345/2025 за отзыв претензии в папку Архив",
            "перенеси все документы дела А40-12345/2025 по претензии в папку Архив",
            "перенеси документ 1-я претензия в дело Архив",
            "перемести документ 100 претензий в дело Архив",
        )
        for text in phrases:
            self.assertTrue(claim_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за претензию в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_claim_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 претензий в папку Архив"
        masked = mask_claim_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_claim_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 убытков в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            claim_blocks_bulk_document_mutation(
                "удали документ 214 за претензию",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за претензию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по претензии"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за претензию"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за претензию"), [214])
        self.assertIn("претенз", DELETE_REFUSED_REPLY)
        self.assertIn("претенз", MOVE_REFUSED_REPLY)
        self.assertNotIn("наследств", DELETE_REFUSED_REPLY)
        self.assertNotIn("упущен", DELETE_REFUSED_REPLY)
        self.assertNotIn("ущерб", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Претензия",
            "удали все документы в папке «Претензия»",
            "удали все документы в папке «ПРЕТЕНЗИЯ»",
            "удали все документы по делу Претензия",
            "удали все документы по делу «Претензия»",
            "удали все документы по делу «Предъявление претензии»",
            "удали все документы в папке «Отзыв претензии»",
            "удали все документы без претензии в этой папке",
            "удали все документы за претензионный порядок в этой папке",
            "удали все документы за претензионную работу в этой папке",
            "удали все документы за претенциозный тон в этой папке",
            "удали все документы за упущенную прибыль в этой папке",
            "удали все документы за наследство в этой папке",
            "удали все документы за упущенную выгоду в этой папке",
            "удали все документы за неосновательное обогащение в этой папке",
            "удали все документы за ущерб в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за расходы в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Претензия",
            "собери все документы в папку Претензия",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_claim_scoped_document_request(text), text)
            self.assertFalse(claim_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за претензию",
            "за претензии",
            "по претензии",
            "о претензии",
            "об претензии",
            "с претензией",
            "из претензий",
            "за «претензию»",
            "за Претензию",
            "за ПРЕТЕНЗИЮ",
            "за предъявление претензии",
            "по предъявлению претензии",
            "за направление претензии",
            "за отзыв претензии",
            "за удовлетворение претензии",
            "за рассмотрение претензии",
            "за отклонение претензии",
            "за оставление претензии",
            "за обоснование претензии",
            "за сумму претензии",
            "за размер претензии",
            "за оценку претензии",
            "за расчет претензии",
            "за расчёт претензии",
            "за открытие претензии",
            "за ответ на претензию",
            "за текущую претензию",
            "за открытую претензию",
            "за досудебную претензию",
            "за мою претензию",
            "за моё претензию",
            "за первую претензию",
            "за все претензии",
            "за не претензию",
            "во время претензии",
            "во время предъявления претензии",
            "на претензию",
            "документы претензия",
            "файлы претензии",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_claim_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            '"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"',
            source,
        )
        self.assertIn("claim_blocks_bulk_document_mutation", source)
        self.assertIn("mask_claim_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("claim_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        self.assertLess(
            delete_fn.index("claim_blocks_bulk_document_mutation"),
            delete_fn.index("_extract_delete_target_phrases"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertLess(
            parse_fn.index("mask_claim_ordinals"),
            parse_fn.index("re.search"),
        )
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_claim_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("claim_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
