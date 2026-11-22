"""Lost-profit chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
«по упущенной выгоде» as a PDF-text hint. parse_document_ids_for_delete_command
read «1-я упущенная выгода» as document id 1.

A folder titled «Упущенная выгода» is not this guard. Bare «выгода»,
«выгодный», «компенсация», «ущерб», «расходы», «убытки», «вред»,
«неосновательное обогащение», «наследство», and «претензия» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_lost_profit import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    looks_like_lost_profit_scoped_document_request,
    lost_profit_blocks_bulk_document_mutation,
    mask_lost_profit_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_lost_profit_ordinals(raw)
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


class LostProfitFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за упущенную выгоду в этой папке",
            "удали все документы по упущенной выгоде в этой папке",
            "удали все документы об упущенной выгоде в этой папке",
            "удали все документы за взыскание упущенной выгоды в этой папке",
            "удали все документы за возмещение упущенной выгоды в этой папке",
            "удали все документы за размер упущенной выгоды в этой папке",
            "удали все документы за сумму упущенной выгоды в этой папке",
            "удали все документы за оценку упущенной выгоды в этой папке",
            "удали все документы за расчет упущенной выгоды в этой папке",
            "удали все документы за расчёт упущенной выгоды в этой папке",
            "удали все документы за доказывание упущенной выгоды в этой папке",
            "удали все документы за текущую упущенную выгоду",
            "удали все документы за открытую упущенную выгоду",
            "удали все документы за текущую реальную упущенную выгоду",
            "удали все файлы за упущенную выгоду в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(lost_profit_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за упущенную выгоду"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(lost_profit_blocks_bulk_document_mutation(numbered), numbered)
        recovery = "удали все документы дела А40-12345/2025 за возмещение упущенной выгоды"
        self.assertTrue(lost_profit_blocks_bulk_document_mutation(recovery), recovery)

        hint = "удали документы по упущенной выгоде"
        self.assertEqual(_pre_fix_pdf_hint(hint), "упущенной выгоде")
        self.assertTrue(lost_profit_blocks_bulk_document_mutation(hint), hint)
        hinted_all = "удали все документы по упущенной выгоде"
        self.assertEqual(_pre_fix_pdf_hint(hinted_all), "упущенной выгоде")
        self.assertTrue(lost_profit_blocks_bulk_document_mutation(hinted_all), hinted_all)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я упущенная выгода", [1]),
            ("удали документы 1 упущенная выгода", [1]),
            ("удали документы 2-й упущенной выгоды", [2]),
            ("удали документы 1-ю упущенную выгоду", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(lost_profit_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 упущенных выгод"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 упущенных выгод"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 убытков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 убытков"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% упущенной выгоды"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% упущенной выгоды"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% упущенной выгоды"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% упущенной выгоды"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я упущенная выгода"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я упущенная выгода"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й упущенной выгоды"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й упущенной выгоды"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за упущенную выгоду"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(
            _parse_ids_like_main("удали документы 214 287 за упущенную выгоду"),
            [214, 287],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214-й ущерб"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за упущенную выгоду в папку Архив",
            "перенеси все документы дела А40-12345/2025 за возмещение упущенной выгоды в папку Архив",
            "перенеси все документы дела А40-12345/2025 за расчет упущенной выгоды в папку Архив",
            "перенеси все документы дела А40-12345/2025 по упущенной выгоде в папку Архив",
            "перенеси документ 1-я упущенная выгода в дело Архив",
            "перемести документ 100 упущенных выгод в дело Архив",
        )
        for text in phrases:
            self.assertTrue(lost_profit_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за упущенную выгоду в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_lost_profit_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 упущенных выгод в папку Архив"
        masked = mask_lost_profit_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_lost_profit_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 убытков в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            lost_profit_blocks_bulk_document_mutation(
                "удали документ 214 за упущенную выгоду",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за упущенную выгоду"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по упущенной выгоде"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за упущенную выгоду"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за упущенную выгоду"), [214])
        self.assertIn("упущенн", DELETE_REFUSED_REPLY)
        self.assertIn("выгод", DELETE_REFUSED_REPLY)
        self.assertIn("упущенн", MOVE_REFUSED_REPLY)
        self.assertNotIn("убыт", DELETE_REFUSED_REPLY)
        self.assertNotIn("ущерб", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Упущенная выгода",
            "удали все документы в папке «Упущенная выгода»",
            "удали все документы в папке «Упущенная Выгода»",
            "удали все документы по делу Упущенная выгода",
            "удали все документы по делу «Упущенная выгода»",
            "удали все документы по делу «Возмещение упущенной выгоды»",
            "удали все документы без упущенной выгоды в этой папке",
            "удали все документы за выгоду в этой папке",
            "удали все документы за упущенный срок в этой папке",
            "удали все документы за выгодный контракт в этой папке",
            "удали все документы за выгодность в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за компенсацию упущенной выгоды в этой папке",
            "удали все документы за ущерб в этой папке",
            "удали все документы за расходы в этой папке",
            "удали все документы за убытки в этой папке",
            "удали все документы за вред в этой папке",
            "удали все документы за неосновательное обогащение в этой папке",
            "удали все документы за наследство в этой папке",
            "удали все документы за претензию в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Упущенная выгода",
            "собери все документы в папку Упущенная выгода",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_lost_profit_scoped_document_request(text), text)
            self.assertFalse(lost_profit_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за упущенную выгоду",
            "за упущенной выгоды",
            "по упущенной выгоде",
            "об упущенной выгоде",
            "с упущенной выгодой",
            "с упущенною выгодою",
            "из упущенных выгод",
            "за «упущенную выгоду»",
            "за Упущенную выгоду",
            "за УПУЩЕННУЮ ВЫГОДУ",
            "за взыскание упущенной выгоды",
            "по возмещению упущенной выгоды",
            "за размер упущенной выгоды",
            "за сумму упущенной выгоды",
            "за оценку упущенной выгоды",
            "за расчет упущенной выгоды",
            "за расчёт упущенной выгоды",
            "за доказывание упущенной выгоды",
            "за доказательство упущенной выгоды",
            "за текущую упущенную выгоду",
            "за открытую упущенную выгоду",
            "за мою упущенную выгоду",
            "за моё упущенную выгоду",
            "за первую упущенную выгоду",
            "за все упущенные выгоды",
            "за не упущенную выгоду",
            "во время упущенной выгоды",
            "во время взыскания упущенной выгоды",
            "документы упущенная выгода",
            "файлы упущенной выгоды",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_lost_profit_scoped_document_request(
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
        self.assertIn("lost_profit_blocks_bulk_document_mutation", source)
        self.assertIn("mask_lost_profit_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("lost_profit_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        self.assertLess(
            delete_fn.index("lost_profit_blocks_bulk_document_mutation"),
            delete_fn.index("_extract_delete_target_phrases"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertLess(parse_fn.index("mask_lost_profit_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_lost_profit_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("lost_profit_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
