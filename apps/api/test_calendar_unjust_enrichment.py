"""Unjust-enrichment chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
«по неосновательному обогащению» as a PDF-text hint.
parse_document_ids_for_delete_command read «1-е неосновательное обогащение»
as document id 1.

A folder titled «Неосновательное обогащение» is not this guard. Bare
«обогащение», «неосновательный», «компенсация», «ущерб», «расходы»,
«убытки», «вред», «упущенная выгода», «упущенная прибыль», «наследство»,
and «претензия» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_unjust_enrichment import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    looks_like_unjust_enrichment_scoped_document_request,
    mask_unjust_enrichment_ordinals,
    unjust_enrichment_blocks_bulk_document_mutation,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_unjust_enrichment_ordinals(raw)
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


class UnjustEnrichmentFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за неосновательное обогащение в этой папке",
            "удали все документы по неосновательному обогащению в этой папке",
            "удали все документы об неосновательном обогащении в этой папке",
            "удали все документы о неосновательном обогащении в этой папке",
            "удали все документы за взыскание неосновательного обогащения в этой папке",
            "удали все документы за возврат неосновательного обогащения в этой папке",
            "удали все документы за возмещение неосновательного обогащения в этой папке",
            "удали все документы за истребование неосновательного обогащения в этой папке",
            "удали все документы за размер неосновательного обогащения в этой папке",
            "удали все документы за сумму неосновательного обогащения в этой папке",
            "удали все документы за оценку неосновательного обогащения в этой папке",
            "удали все документы за расчет неосновательного обогащения в этой папке",
            "удали все документы за расчёт неосновательного обогащения в этой папке",
            "удали все документы за доказывание неосновательного обогащения в этой папке",
            "удали все документы за текущее неосновательное обогащение",
            "удали все документы за открытое неосновательное обогащение",
            "удали все документы за текущее реальное неосновательное обогащение",
            "удали все файлы за неосновательное обогащение в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(unjust_enrichment_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за неосновательное обогащение"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(unjust_enrichment_blocks_bulk_document_mutation(numbered), numbered)
        recovery = "удали все документы дела А40-12345/2025 за возврат неосновательного обогащения"
        self.assertTrue(unjust_enrichment_blocks_bulk_document_mutation(recovery), recovery)

        hint = "удали документы по неосновательному обогащению"
        self.assertEqual(_pre_fix_pdf_hint(hint), "неосновательному обогащению")
        self.assertTrue(unjust_enrichment_blocks_bulk_document_mutation(hint), hint)
        hinted_all = "удали все документы по неосновательному обогащению"
        self.assertEqual(_pre_fix_pdf_hint(hinted_all), "неосновательному обогащению")
        self.assertTrue(unjust_enrichment_blocks_bulk_document_mutation(hinted_all), hinted_all)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-е неосновательное обогащение", [1]),
            ("удали документы 1 неосновательное обогащение", [1]),
            ("удали документы 1-ое неосновательное обогащение", [1]),
            ("удали документы 2-е неосновательного обогащения", [2]),
            ("удали документы 1-м неосновательным обогащением", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(unjust_enrichment_blocks_bulk_document_mutation(text), text)
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 100 неосновательных обогащений"),
            [100],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 100 неосновательных обогащений"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 убытков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 убытков"), [100])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12,5% неосновательного обогащения"),
            [5, 12],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документы 12,5% неосновательного обогащения"),
            [],
        )
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12.5% неосновательного обогащения"),
            [12],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документы 12.5% неосновательного обогащения"),
            [],
        )
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 214-е неосновательное обогащение"),
            [214],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документы 214-е неосновательное обогащение"),
            [],
        )
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 214-ое неосновательное обогащение"),
            [214],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документы 214-ое неосновательное обогащение"),
            [],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за неосновательное обогащение"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(
            _parse_ids_like_main("удали документы 214 287 за неосновательное обогащение"),
            [214, 287],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214-й ущерб"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я упущенная выгода"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за неосновательное обогащение в папку Архив",
            "перенеси все документы дела А40-12345/2025 за возврат неосновательного обогащения в папку Архив",
            "перенеси все документы дела А40-12345/2025 за расчет неосновательного обогащения в папку Архив",
            "перенеси все документы дела А40-12345/2025 по неосновательному обогащению в папку Архив",
            "перенеси документ 1-е неосновательное обогащение в дело Архив",
            "перемести документ 100 неосновательных обогащений в дело Архив",
        )
        for text in phrases:
            self.assertTrue(unjust_enrichment_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за неосновательное обогащение в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_unjust_enrichment_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = (
            "перенеси все документы дела А40-12345/2025 за 100 неосновательных обогащений в папку Архив"
        )
        masked = mask_unjust_enrichment_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_unjust_enrichment_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 убытков в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            unjust_enrichment_blocks_bulk_document_mutation(
                "удали документ 214 за неосновательное обогащение",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за неосновательное обогащение"),
            [214],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ 18 по неосновательному обогащению"),
            [18],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за неосновательное обогащение"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за неосновательное обогащение"), [214])
        self.assertIn("неосновательн", DELETE_REFUSED_REPLY)
        self.assertIn("обогащен", DELETE_REFUSED_REPLY)
        self.assertIn("неосновательн", MOVE_REFUSED_REPLY)
        self.assertNotIn("упущенн", DELETE_REFUSED_REPLY)
        self.assertNotIn("ущерб", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Неосновательное обогащение",
            "удали все документы в папке «Неосновательное обогащение»",
            "удали все документы в папке «Неосновательное Обогащение»",
            "удали все документы по делу Неосновательное обогащение",
            "удали все документы по делу «Неосновательное обогащение»",
            "удали все документы по делу «Возврат неосновательного обогащения»",
            "удали все документы без неосновательного обогащения в этой папке",
            "удали все документы за обогащение в этой папке",
            "удали все документы за неосновательный иск в этой папке",
            "удали все документы за неосновательность в этой папке",
            "удали все документы за неосновательно в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за компенсацию неосновательного обогащения в этой папке",
            "удали все документы за ущерб в этой папке",
            "удали все документы за расходы в этой папке",
            "удали все документы за убытки в этой папке",
            "удали все документы за вред в этой папке",
            "удали все документы за упущенную выгоду в этой папке",
            "удали все документы за упущенную прибыль в этой папке",
            "удали все документы за наследство в этой папке",
            "удали все документы за претензию в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Неосновательное обогащение",
            "собери все документы в папку Неосновательное обогащение",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_unjust_enrichment_scoped_document_request(text), text)
            self.assertFalse(unjust_enrichment_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за неосновательное обогащение",
            "за неосновательного обогащения",
            "по неосновательному обогащению",
            "об неосновательном обогащении",
            "о неосновательном обогащении",
            "с неосновательным обогащением",
            "из неосновательных обогащений",
            "за «неосновательное обогащение»",
            "за Неосновательное обогащение",
            "за НЕОСНОВАТЕЛЬНОЕ ОБОГАЩЕНИЕ",
            "за взыскание неосновательного обогащения",
            "по возврату неосновательного обогащения",
            "за истребование неосновательного обогащения",
            "за возмещение неосновательного обогащения",
            "за размер неосновательного обогащения",
            "за сумму неосновательного обогащения",
            "за оценку неосновательного обогащения",
            "за расчет неосновательного обогащения",
            "за расчёт неосновательного обогащения",
            "за доказывание неосновательного обогащения",
            "за доказательство неосновательного обогащения",
            "за текущее неосновательное обогащение",
            "за открытое неосновательное обогащение",
            "за моё неосновательное обогащение",
            "за мое неосновательное обогащение",
            "за первое неосновательное обогащение",
            "за все неосновательные обогащения",
            "за не неосновательное обогащение",
            "во время неосновательного обогащения",
            "во время взыскания неосновательного обогащения",
            "документы неосновательное обогащение",
            "файлы неосновательного обогащения",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_unjust_enrichment_scoped_document_request(
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
        self.assertIn("unjust_enrichment_blocks_bulk_document_mutation", source)
        self.assertIn("mask_unjust_enrichment_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("unjust_enrichment_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        self.assertLess(
            delete_fn.index("unjust_enrichment_blocks_bulk_document_mutation"),
            delete_fn.index("_extract_delete_target_phrases"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertLess(
            parse_fn.index("mask_unjust_enrichment_ordinals"),
            parse_fn.index("re.search"),
        )
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_unjust_enrichment_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("unjust_enrichment_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
