"""Franchising / royalty / grant / dotation chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-го роялти» as document id 1. The calendar period parser does not recognize
these phrases.

«франшиза» is not «франчайзинг». «субсидия» / «субсидиарная» are not «дотация».
A folder titled «Роялти» is not this guard. Bare «банкротство» is not this guard.
«иммигрант», «рояль», and «грань» are not «грант» / «роялти».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_franchising import (
    franchising_blocks_bulk_document_mutation,
    looks_like_franchising_scoped_document_request,
    mask_franchising_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_franchising_ordinals(raw)
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


class FranchisingScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за франчайзинг в этой папке",
            "удали все документы по франчайзингу в этой папке",
            "удали все документы о франчайзинге в этой папке",
            "удали все документы за договор франчайзинга в этой папке",
            "удали все документы за франчайзинговый договор в этой папке",
            "удали все документы за франчайзи в этой папке",
            "удали все документы за франчайзера в этой папке",
            "удали все документы за франчайзора в этой папке",
            "удали все документы за роялти в этой папке",
            "удали все документы за рояльти в этой папке",
            "удали все документы за выплату роялти в этой папке",
            "удали все документы за невыплату роялти в этой папке",
            "удали все документы за ставку роялти в этой папке",
            "удали все документы за размер роялти в этой папке",
            "удали все документы за роялти-платеж в этой папке",
            "удали все документы за роялтийный платеж в этой папке",
            "удали все документы за грант в этой папке",
            "удали все документы по гранту в этой папке",
            "удали все документы за получение гранта в этой папке",
            "удали все документы за грантовый проект в этой папке",
            "удали все документы за грантополучателя в этой папке",
            "удали все документы за микрогрант в этой папке",
            "удали все документы за дотацию в этой папке",
            "удали все документы по дотации в этой папке",
            "удали все документы за предоставление дотации в этой папке",
            "удали все документы за возврат дотации в этой папке",
            "удали все документы за дотационную программу в этой папке",
            "удали все документы за целевую дотацию в этой папке",
            "удали все документы за текущий франчайзинг",
            "удали все документы за открытый грант",
            "удали все документы за текущую дотацию",
            "удали все документы за открытое роялти",
            "удали каждый документ за роялти в этой папке",
            "удали все файлы за гранты в этой папке",
            "удали все документы каждого франчайзинга в этой папке",
            "удали все документы по всем дотациям в этой папке",
            "удали все документы дела А40-12345/2025 за франчайзинг",
            "удали все документы дела А40-12345/2025 за роялти",
            "удали все документы дела А40-12345/2025 за грант",
            "удали все документы дела А40-12345/2025 за дотацию",
            "удали все документы за Франчайзинг в этой папке",
            "удали все документы за Роялти в этой папке",
            "удали все документы за Грант в этой папке",
            "удали все документы за Дотацию в этой папке",
            "удали все документы во время франчайзинга в этой папке",
            "удали все документы во время роялти в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(franchising_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за франчайзинг в этой папке",
            "удали все документы за франчайзи в этой папке",
            "удали все документы за франчайзера в этой папке",
            "удали все документы за роялти в этой папке",
            "удали все документы за грант в этой папке",
            "удали все документы за дотацию в этой папке",
            "удали все документы за текущий франчайзинг",
            "удали все документы за открытый грант",
            "удали все документы за открытую дотацию в этой папке",
            "удали все документы за текущую дотацию",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го франчайзинга",
            "удали документы 1-го франчайзи",
            "удали документы 1-го франчайзера",
            "удали документы 1-го франчайзора",
            "удали документы 1-го роялти",
            "удали документы 1-й роялти",
            "удали документы 1-му гранту",
            "удали документы 1-й дотации",
            "удали документы 1-ю дотацию",
            "удали документы 2-го гранта",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(franchising_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 франчайзинга"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 франчайзинга"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 роялти"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 роялти"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 гранта"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 гранта"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 дотации"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 дотации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 роялти"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 роялти"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% дотации"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% дотации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% гранта"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% гранта"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го франчайзера"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го франчайзера"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го франчайзинга"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го франчайзинга"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й дотации"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й дотации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го грантополучателя"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го грантополучателя"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за 100 роялти"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за роялти"), [214, 287])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го иммигранта"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го иммигранта"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й франшизы"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й субсидии"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го кредита"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за франчайзинг в папку Архив",
            "перенеси все документы дела А40-12345/2025 за франчайзи в папку Архив",
            "перенеси все документы дела А40-12345/2025 за франчайзера в папку Архив",
            "перенеси все документы дела А40-12345/2025 за роялти в папку Архив",
            "перенеси все документы дела А40-12345/2025 за грант в папку Архив",
            "перенеси все документы дела А40-12345/2025 за дотацию в папку Архив",
            "перенеси документ 1-го роялти в дело Архив",
            "перемести документ 1-го гранта в дело Архив",
            "перемести документ 1-й дотации в дело Архив",
        )
        for text in phrases:
            self.assertTrue(franchising_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за роялти в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_franchising_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 роялти в папку Архив"
        masked = mask_franchising_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            franchising_blocks_bulk_document_mutation(
                "удали документ 214 за роялти",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за франчайзинг"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за роялти"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за грант"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за дотацию"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за роялти"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за дотацию"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без франчайзинга",
            "удали все документы в этой папке без франчайзи",
            "удали все документы в этой папке без франчайзера",
            "удали все документы в этой папке без роялти",
            "удали все документы в этой папке без рояльти",
            "удали все документы в этой папке без гранта",
            "удали все документы в этой папке без дотации",
            "удали все документы в папке «Франчайзинг»",
            "удали все документы в папке Франчайзинг",
            "удали все документы в папке Роялти",
            "удали все документы в папке Грант",
            "удали все документы в папке Дотация",
            "удали все документы в папке «Роялтийный платеж»",
            "удали все документы из папки Франчайзи",
            "перенеси все документы в папку Франчайзинг",
            "перенеси все документы в папку Роялти",
            "перенеси все документы в папку Гранты",
            "перенеси все документы в папку Дотации",
            "удали все документы по делу Франчайзинг",
            "удали все документы по делу Роялти",
            "удали все документы по делу Грант",
            "удали все документы по делу Дотация",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за банкротство в этой папке",
            "удали все документы за франшизу в этой папке",
            "удали все документы за дивиденд в этой папке",
            "удали все документы за субсидию в этой папке",
            "удали все документы за субсидиарную ответственность в этой папке",
            "удали все документы за субсидиарку в этой папке",
            "удали все документы за кредит в этой папке",
            "удали все документы за овердрафт в этой папке",
            "удали все документы за ренту в этой папке",
            "удали все документы за ссуду в этой папке",
            "удали все документы за платеж в этой папке",
            "удали все документы за паушальный взнос в этой папке",
            "удали все документы за коммерческую концессию в этой папке",
            "удали все документы за иммигранта в этой папке",
            "удали все документы за эмигранта в этой папке",
            "удали все документы за мигранта в этой папке",
            "удали все документы за рояль в этой папке",
            "удали все документы за грань в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за график в этой папке",
            "удали все документы о том в этой папке",
            "удали все документы за тем в этой папке",
            "удали все документы после открытия",
            "удали все документы по текущей задолженности",
            "удали документы 1-го приказа",
            "удали документы 1-й субсидиарной ответственности",
            "удали документы 1-й франшизы",
            "перенеси все документы в папку Архив",
        ):
            self.assertFalse(looks_like_franchising_scoped_document_request(text), text)
            self.assertFalse(franchising_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы франчайзинга в этой папке",
            "удали документы франчайзи в этой папке",
            "удали документы франчайзера в этой папке",
            "удали документы роялти в этой папке",
            "удали документы гранта в этой папке",
            "удали документы дотации в этой папке",
            "удали все документы за первый грант в этой папке",
            "удали все документы за первую дотацию в этой папке",
            "удали все документы за эту дотацию в этой папке",
            "удали все документы за тот грант в этой папке",
            "удали все документы о том роялти в этой папке",
        ):
            self.assertTrue(franchising_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за франчайзинг",
            "за франчайзинга",
            "по франчайзингу",
            "о франчайзинге",
            "за франчайзингом",
            "за франчайзинги",
            "за франчайзингов",
            "за франчайзинговый договор",
            "за франчайзингового партнера",
            "за франчайзинговую сеть",
            "за франчайзи",
            "для франчайзи",
            "за франчайзер",
            "за франчайзера",
            "за франчайзеру",
            "за франчайзером",
            "о франчайзере",
            "за франчайзеры",
            "за франчайзеров",
            "за франчайзор",
            "за франчайзора",
            "за франчайзору",
            "за франчайзором",
            "за роялти",
            "за рояльти",
            "по роялти",
            "о роялти",
            "за роялтийный платеж",
            "за роялтийную ставку",
            "за грант",
            "за гранта",
            "за гранту",
            "за грантом",
            "о гранте",
            "за гранты",
            "за грантов",
            "за грантам",
            "за грантами",
            "за грантах",
            "за грантовый проект",
            "за грантового получателя",
            "за микрогрант",
            "за микрогранта",
            "за микрогрантовый проект",
            "за грантополучателя",
            "за грантополучателю",
            "за грантополучателем",
            "о грантополучателе",
            "за грантополучатели",
            "за грантополучателей",
            "за дотацию",
            "за дотации",
            "по дотации",
            "о дотации",
            "за дотацией",
            "за дотациею",
            "за дотациям",
            "за дотациями",
            "за дотациях",
            "за дотаций",
            "за дотационный проект",
            "за дотационную программу",
            "за дотационного получателя",
            "за выплату роялти",
            "за невыплату роялти",
            "за получение гранта",
            "за предоставление дотации",
            "за условие франчайзинга",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_franchising_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("franchising_blocks_bulk_document_mutation", source)
        self.assertIn("mask_franchising_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("franchising_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_franchising_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_franchising_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("franchising_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
