"""Power-of-attorney chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
«по отзыву доверенности» as a PDF-text hint.
parse_document_ids_for_delete_command read «1-я доверенность» as document id 1.

A folder titled «Доверенность» is not this guard. «без доверенности» is not
this guard. «доверенный», «претензия», «упущенная прибыль», «наследство»,
«упущенная выгода», and «ущерб» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_power_of_attorney import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    looks_like_power_of_attorney_scoped_document_request,
    mask_power_of_attorney_ordinals,
    power_of_attorney_blocks_bulk_document_mutation,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_power_of_attorney_ordinals(raw)
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


class PowerOfAttorneyFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за доверенность в этой папке",
            "удали все документы по доверенности в этой папке",
            "удали все документы о доверенности в этой папке",
            "удали все документы об доверенности в этой папке",
            "удали все документы за выдачу доверенности в этой папке",
            "удали все документы за отзыв доверенности в этой папке",
            "удали все документы за отмену доверенности в этой папке",
            "удали все документы за прекращение доверенности в этой папке",
            "удали все документы за удостоверение доверенности в этой папке",
            "удали все документы за оформление доверенности в этой папке",
            "удали все документы за предъявление доверенности в этой папке",
            "удали все документы за сумму доверенности в этой папке",
            "удали все документы за размер доверенности в этой папке",
            "удали все документы за оценку доверенности в этой папке",
            "удали все документы за расчет доверенности в этой папке",
            "удали все документы за расчёт доверенности в этой папке",
            "удали все документы за открытие доверенности",
            "удали все документы за текущую доверенность",
            "удали все документы за открытую доверенность",
            "удали все документы за генеральную доверенность в этой папке",
            "удали все документы за нотариальную доверенность в этой папке",
            "удали все документы за судебную доверенность в этой папке",
            "удали все файлы за доверенность в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(power_of_attorney_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за доверенность"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(power_of_attorney_blocks_bulk_document_mutation(numbered), numbered)
        filing = "удали все документы дела А40-12345/2025 за выдачу доверенности"
        self.assertTrue(power_of_attorney_blocks_bulk_document_mutation(filing), filing)

        hint = "удали документы по отзыву доверенности"
        self.assertEqual(_pre_fix_pdf_hint(hint), "отзыву доверенности")
        self.assertTrue(power_of_attorney_blocks_bulk_document_mutation(hint), hint)
        hinted_all = "удали все документы по генеральной доверенности"
        self.assertEqual(_pre_fix_pdf_hint(hinted_all), "генеральной доверенности")
        self.assertTrue(power_of_attorney_blocks_bulk_document_mutation(hinted_all), hinted_all)
        single = "удали документы по доверенности"
        self.assertIsNone(_pre_fix_pdf_hint(single))
        self.assertTrue(power_of_attorney_blocks_bulk_document_mutation(single), single)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я доверенность", [1]),
            ("удали документы 1 доверенность", [1]),
            ("удали документы 2-ю доверенность", [2]),
            ("удали документы 1-й доверенности", [1]),
            ("удали документы 1-е доверенность", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(power_of_attorney_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 доверенностей"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 доверенностей"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 убытков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 убытков"), [100])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12,5% доверенности"),
            [5, 12],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% доверенности"), [])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12.5% доверенности"),
            [12],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% доверенности"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я доверенность"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я доверенность"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-ю доверенность"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-ю доверенность"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за доверенность"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(
            _parse_ids_like_main("удали документы 214 287 за доверенность"),
            [214, 287],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214-е наследство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я претензия"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я упущенная прибыль"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за доверенность в папку Архив",
            "перенеси все документы дела А40-12345/2025 за выдачу доверенности в папку Архив",
            "перенеси все документы дела А40-12345/2025 за отзыв доверенности в папку Архив",
            "перенеси все документы дела А40-12345/2025 по доверенности в папку Архив",
            "перенеси документ 1-я доверенность в дело Архив",
            "перемести документ 100 доверенностей в дело Архив",
        )
        for text in phrases:
            self.assertTrue(power_of_attorney_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за доверенность в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_power_of_attorney_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 доверенностей в папку Архив"
        masked = mask_power_of_attorney_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_power_of_attorney_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 убытков в папку Архив"
        )
        self.assertIn("100", other)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            power_of_attorney_blocks_bulk_document_mutation(
                "удали документ 214 за доверенность",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за доверенность"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по доверенности"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за доверенность"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за доверенность"), [214])
        self.assertIn("доверенност", DELETE_REFUSED_REPLY)
        self.assertIn("доверенност", MOVE_REFUSED_REPLY)
        self.assertNotIn("претенз", DELETE_REFUSED_REPLY)
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
            "удали все документы в папке Доверенность",
            "удали все документы в папке «Доверенность»",
            "удали все документы в папке «ДОВЕРЕННОСТЬ»",
            "удали все документы по делу Доверенность",
            "удали все документы по делу «Доверенность»",
            "удали все документы по делу «Выдача доверенности»",
            "удали все документы в папке «Отзыв доверенности»",
            "удали все документы без доверенности в этой папке",
            "удали все документы за доверенного представителя в этой папке",
            "удали все документы за доверенное лицо в этой папке",
            "удали все документы за доверителя в этой папке",
            "удали все документы за иск в этой папке",
            "удали все документы за отзыв в этой папке",
            "удали все документы за претензию в этой папке",
            "удали все документы за протокол в этой папке",
            "удали все документы за упущенную прибыль в этой папке",
            "удали все документы за наследство в этой папке",
            "удали все документы за упущенную выгоду в этой папке",
            "удали все документы за неосновательное обогащение в этой папке",
            "удали все документы за ущерб в этой папке",
            "удали все документы за компенсацию в этой папке",
            "удали все документы за расходы в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Доверенность",
            "собери все документы в папку Доверенность",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_power_of_attorney_scoped_document_request(text), text)
            self.assertFalse(power_of_attorney_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за доверенность",
            "за доверенности",
            "по доверенности",
            "о доверенности",
            "об доверенности",
            "с доверенностью",
            "из доверенностей",
            "за «доверенность»",
            "за Доверенность",
            "за ДОВЕРЕННОСТЬ",
            "за выдачу доверенности",
            "по выдаче доверенности",
            "за отзыв доверенности",
            "по отзыву доверенности",
            "за отмену доверенности",
            "за прекращение доверенности",
            "за удостоверение доверенности",
            "за оформление доверенности",
            "за предъявление доверенности",
            "за передоверие доверенности",
            "за сумму доверенности",
            "за размер доверенности",
            "за оценку доверенности",
            "за расчет доверенности",
            "за расчёт доверенности",
            "за открытие доверенности",
            "за срок действия доверенности",
            "за текущую доверенность",
            "за открытую доверенность",
            "за генеральную доверенность",
            "за нотариальную доверенность",
            "за судебную доверенность",
            "за мою доверенность",
            "за моё доверенность",
            "за первую доверенность",
            "за все доверенности",
            "за не доверенность",
            "во время доверенности",
            "во время выдачи доверенности",
            "на доверенность",
            "документы доверенность",
            "файлы доверенности",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_power_of_attorney_scoped_document_request(
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
        self.assertIn("power_of_attorney_blocks_bulk_document_mutation", source)
        self.assertIn("mask_power_of_attorney_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("power_of_attorney_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        self.assertLess(
            delete_fn.index("power_of_attorney_blocks_bulk_document_mutation"),
            delete_fn.index("_extract_delete_target_phrases"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertLess(
            parse_fn.index("mask_power_of_attorney_ordinals"),
            parse_fn.index("re.search"),
        )
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_power_of_attorney_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("power_of_attorney_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
