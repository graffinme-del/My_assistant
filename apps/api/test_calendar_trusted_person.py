"""Trusted-person chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
«по доверенному лицу» as a PDF-text hint.
parse_document_ids_for_delete_command read «1-е доверенное лицо» as document id 1.

A folder titled «Доверенное лицо» is not this guard. «без доверенного лица»
is not this guard. «доверенность», «доверитель», bare «лицо», bare
«представитель», «претензия», and «упущенная прибыль» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_trusted_person import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    looks_like_trusted_person_scoped_document_request,
    mask_trusted_person_ordinals,
    trusted_person_blocks_bulk_document_mutation,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_trusted_person_ordinals(raw)
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


class TrustedPersonFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за доверенное лицо в этой папке",
            "удали все документы по доверенному лицу в этой папке",
            "удали все документы о доверенном лице в этой папке",
            "удали все документы об доверенном лице в этой папке",
            "удали все документы за доверенного представителя в этой папке",
            "удали все документы по доверенному представителю в этой папке",
            "удали все документы за выдачу доверенного лица в этой папке",
            "удали все документы за отзыв доверенного лица в этой папке",
            "удали все документы за отмену доверенного лица в этой папке",
            "удали все документы за назначение доверенного представителя в этой папке",
            "удали все документы за полномочия доверенного лица в этой папке",
            "удали все документы за прекращение полномочий доверенного лица в этой папке",
            "удали все документы за сумму доверенного лица в этой папке",
            "удали все документы за размер доверенного лица в этой папке",
            "удали все документы за оценку доверенного лица в этой папке",
            "удали все документы за расчет доверенного лица в этой папке",
            "удали все документы за расчёт доверенного лица в этой папке",
            "удали все документы за открытие доверенного лица",
            "удали все документы за текущее доверенное лицо",
            "удали все документы за открытое доверенное лицо",
            "удали все документы за текущего доверенного представителя",
            "удали все документы за открытого доверенного представителя",
            "удали все файлы за доверенное лицо в этой папке",
            "удали все документы из доверенных лиц в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(trusted_person_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за доверенное лицо"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(trusted_person_blocks_bulk_document_mutation(numbered), numbered)
        representative = "удали все документы дела А40-12345/2025 за доверенного представителя"
        self.assertTrue(trusted_person_blocks_bulk_document_mutation(representative), representative)

        hint = "удали документы по доверенному лицу"
        self.assertEqual(_pre_fix_pdf_hint(hint), "доверенному лицу")
        self.assertTrue(trusted_person_blocks_bulk_document_mutation(hint), hint)
        hinted_rep = "удали документы по доверенному представителю"
        self.assertEqual(_pre_fix_pdf_hint(hinted_rep), "доверенному представителю")
        self.assertTrue(trusted_person_blocks_bulk_document_mutation(hinted_rep), hinted_rep)
        hinted_all = "удали все документы по генеральному доверенному лицу"
        self.assertEqual(_pre_fix_pdf_hint(hinted_all), "генеральному доверенному лицу")
        self.assertTrue(trusted_person_blocks_bulk_document_mutation(hinted_all), hinted_all)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-е доверенное лицо", [1]),
            ("удали документы 1 доверенное лицо", [1]),
            ("удали документы 1-ое доверенное лицо", [1]),
            ("удали документы 2-е доверенное лицо", [2]),
            ("удали документы 1-й доверенный представитель", [1]),
            ("удали документы 2-го доверенного представителя", [2]),
            ("удали документы 2-му доверенному представителю", [2]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(trusted_person_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 доверенных лиц"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 доверенных лиц"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 доверенных представителей"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 доверенных представителей"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 убытков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 убытков"), [100])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12,5% доверенного лица"),
            [5, 12],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% доверенного лица"), [])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 12.5% доверенного представителя"),
            [12],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% доверенного представителя"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-е доверенное лицо"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е доверенное лицо"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й доверенный представитель"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й доверенный представитель"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за доверенное лицо"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(
            _parse_ids_like_main("удали документы 214 287 за доверенного представителя"),
            [214, 287],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214-я доверенность"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 1-я доверенность"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е наследство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я претензия"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за доверенное лицо в папку Архив",
            "перенеси все документы дела А40-12345/2025 за доверенного представителя в папку Архив",
            "перенеси все документы дела А40-12345/2025 по доверенному лицу в папку Архив",
            "перенеси все документы дела А40-12345/2025 за назначение доверенного представителя в папку Архив",
            "перенеси документ 1-е доверенное лицо в дело Архив",
            "перемести документ 100 доверенных лиц в дело Архив",
        )
        for text in phrases:
            self.assertTrue(trusted_person_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за доверенное лицо в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_trusted_person_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 доверенных лиц в папку Архив"
        masked = mask_trusted_person_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        other = mask_trusted_person_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 убытков в папку Архив"
        )
        self.assertIn("100", other)
        poa = mask_trusted_person_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 доверенностей в папку Архив"
        )
        self.assertIn("100", poa)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            trusted_person_blocks_bulk_document_mutation(
                "удали документ 214 за доверенное лицо",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за доверенное лицо"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по доверенному представителю"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за доверенное лицо"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за доверенного представителя"), [214])
        self.assertIn("доверенное лицо", DELETE_REFUSED_REPLY)
        self.assertIn("доверенного представителя", DELETE_REFUSED_REPLY)
        self.assertIn("доверенное лицо", MOVE_REFUSED_REPLY)
        self.assertNotIn("доверенност", DELETE_REFUSED_REPLY)
        self.assertNotIn("доверител", DELETE_REFUSED_REPLY)
        self.assertNotIn("претенз", DELETE_REFUSED_REPLY)
        self.assertNotIn("упущен", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Доверенное лицо",
            "удали все документы в папке «Доверенное лицо»",
            "удали все документы в папке «ДОВЕРЕННОЕ ЛИЦО»",
            "удали все документы в папке «Доверенный представитель»",
            "удали все документы по делу Доверенное лицо",
            "удали все документы по делу «Доверенное лицо»",
            "удали все документы по делу «Доверенный представитель»",
            "удали все документы по делу «Назначение доверенного представителя»",
            "удали все документы в папке «Отзыв доверенного лица»",
            "удали все документы без доверенного лица в этой папке",
            "удали все документы без доверенного представителя в этой папке",
            "удали все документы за доверенность в этой папке",
            "удали все документы по доверенности в этой папке",
            "удали все документы за выдачу доверенности в этой папке",
            "удали все документы за доверителя в этой папке",
            "удали все документы за доверителя",
            "удали все документы за лицо в этой папке",
            "удали все документы за представителя в этой папке",
            "удали все документы за иск в этой папке",
            "удали все документы за претензию в этой папке",
            "удали все документы за упущенную прибыль в этой папке",
            "удали все документы за наследство в этой папке",
            "удали все документы за уполномоченное лицо в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Доверенное лицо",
            "собери все документы в папку Доверенный представитель",
            "удали документ 214",
            "удали документы по лицу",
        ):
            self.assertFalse(looks_like_trusted_person_scoped_document_request(text), text)
            self.assertFalse(trusted_person_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за доверенное лицо",
            "за доверенного лица",
            "по доверенному лицу",
            "о доверенном лице",
            "об доверенном лице",
            "с доверенным лицом",
            "из доверенных лиц",
            "за «доверенное лицо»",
            "за Доверенное лицо",
            "за ДОВЕРЕННОЕ ЛИЦО",
            "за доверенного представителя",
            "по доверенному представителю",
            "о доверенном представителе",
            "с доверенным представителем",
            "за доверенных представителей",
            "за доверенными лицами",
            "за доверенными представителями",
            "за выдачу доверенного лица",
            "по выдаче доверенного лица",
            "за отзыв доверенного лица",
            "по отзыву доверенного представителя",
            "за отмену доверенного лица",
            "за назначение доверенного представителя",
            "за полномочия доверенного лица",
            "за прекращение полномочий доверенного лица",
            "за участие доверенного лица",
            "за замену доверенного представителя",
            "за явку доверенного лица",
            "за допуск доверенного представителя",
            "за отвод доверенного лица",
            "за статус доверенного лица",
            "за сумму доверенного лица",
            "за размер доверенного лица",
            "за оценку доверенного лица",
            "за расчет доверенного лица",
            "за расчёт доверенного лица",
            "за открытие доверенного лица",
            "за текущее доверенное лицо",
            "за открытое доверенное лицо",
            "за текущего доверенного представителя",
            "за открытого доверенного представителя",
            "за моего доверенного представителя",
            "за моё доверенное лицо",
            "за первое доверенное лицо",
            "за первого доверенного представителя",
            "за все доверенные лица",
            "за всех доверенных представителей",
            "за не доверенное лицо",
            "во время доверенного лица",
            "во время выдачи доверенного лица",
            "на доверенное лицо",
            "документы доверенное лицо",
            "файлы доверенного представителя",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_trusted_person_scoped_document_request(
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
        self.assertIn("trusted_person_blocks_bulk_document_mutation", source)
        self.assertIn("mask_trusted_person_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("trusted_person_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        self.assertLess(
            delete_fn.index("trusted_person_blocks_bulk_document_mutation"),
            delete_fn.index("_extract_delete_target_phrases"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split(
            "\ndef ", 1
        )[0]
        self.assertLess(
            parse_fn.index("mask_trusted_person_ordinals"),
            parse_fn.index("re.search"),
        )
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_trusted_person_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("trusted_person_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
