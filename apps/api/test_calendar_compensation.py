"""Compensation chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой
папке» (or «текущ» / «открыт», or a case number) as delete-every-file, and
parse_document_ids_for_delete_command read «1-я компенсация» as document id 1.
A folder titled «Компенсация» is not this guard. «пенсия», «пособие»,
«гонорар», «надбавка», «доплата», «премия», «вознаграждение», «зарплата»,
«алименты», and «оплата труда» are not this guard. «компенсационный» and
«компенсаторный» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_compensation import (
    DELETE_REFUSED_REPLY,
    MOVE_REFUSED_REPLY,
    compensation_blocks_bulk_document_mutation,
    looks_like_compensation_scoped_document_request,
    mask_compensation_ordinals,
)


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_compensation_ordinals(raw)
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


class CompensationFolderWipeTest(unittest.TestCase):
    def test_pre_fix_folder_phrase_selects_active_case(self) -> None:
        samples = (
            "удали все документы за компенсацию в этой папке",
            "удали все документы по компенсации в этой папке",
            "удали все документы о компенсации в этой папке",
            "удали все документы за взыскание компенсации в этой папке",
            "удали все документы за невыплату компенсации в этой папке",
            "удали все документы по выплате компенсации в этой папке",
            "удали все документы за задолженность по компенсации в этой папке",
            "удали все документы по размеру компенсации в этой папке",
            "удали все документы за задержку компенсации в этой папке",
            "удали все документы за начисление компенсации в этой папке",
            "удали все документы за индексацию компенсации в этой папке",
            "удали все документы за получение компенсации в этой папке",
            "удали все документы за денежную компенсацию в этой папке",
            "удали все документы за материальную компенсацию в этой папке",
            "удали все документы за моральную компенсацию в этой папке",
            "удали все документы за страховую компенсацию в этой папке",
            "удали все документы за судебную компенсацию в этой папке",
            "удали все документы за полную компенсацию в этой папке",
            "удали все документы за частичную компенсацию в этой папке",
            "удали все документы за отпускную компенсацию в этой папке",
            "удали все документы за компенсацию морального вреда в этой папке",
            "удали все документы за компенсацию расходов в этой папке",
            "удали все документы за компенсацию убытков в этой папке",
            "удали все документы за компенсацию ущерба в этой папке",
            "удали все документы за компенсацию отпуска в этой папке",
            "удали все документы за расчёт компенсации в этой папке",
            "удали все документы за удержание компенсации в этой папке",
            "удали все документы за текущую компенсацию",
            "удали все документы за открытую компенсацию",
            "удали все документы за счёт компенсации в этой папке",
            "удали все файлы за компенсацию в этой папке",
        )
        for sample in samples:
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)
            self.assertTrue(_wants_all(sample), sample)
            self.assertTrue(compensation_blocks_bulk_document_mutation(sample), sample)

        numbered = "удали все документы дела А40-12345/2025 за компенсацию"
        self.assertTrue(_wants_all(numbered), numbered)
        self.assertRegex(numbered, r"А40-12345/2025")
        self.assertTrue(compensation_blocks_bulk_document_mutation(numbered), numbered)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 1-я компенсация", [1]),
            ("удали документы 1 компенсация", [1]),
            ("удали документы 2-й компенсации", [2]),
            ("удали документы 1-ю компенсацию", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(compensation_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 компенсаций"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 компенсаций"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 пенсий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 пенсий"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 пособий"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 пособий"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 гонораров"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 гонораров"), [100])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% компенсации"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% компенсации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% компенсации"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% компенсации"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-я компенсация"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я компенсация"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-х компенсаций"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-х компенсаций"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за компенсацию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за компенсацию"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214-я пенсия"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-е пособие"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й гонорар"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за компенсацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 по компенсации в папку Архив",
            "перенеси все документы дела А40-12345/2025 за взыскание компенсации в папку Архив",
            "перенеси все документы дела А40-12345/2025 за денежную компенсацию в папку Архив",
            "перенеси все документы дела А40-12345/2025 за компенсацию морального вреда в папку Архив",
            "перенеси документ 1-я компенсация в дело Архив",
            "перемести документ 100 компенсаций в дело Архив",
        )
        for text in phrases:
            self.assertTrue(compensation_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за компенсацию в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_compensation_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 компенсаций в папку Архив"
        masked = mask_compensation_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        pension = mask_compensation_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 пенсий в папку Архив"
        )
        self.assertIn("100", pension)
        benefit = mask_compensation_ordinals(
            "перенеси все документы дела А40-12345/2025 за 100 пособий в папку Архив"
        )
        self.assertIn("100", benefit)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            compensation_blocks_bulk_document_mutation(
                "удали документ 214 за компенсацию",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за компенсацию"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по компенсации"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за компенсацию"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за компенсацию"), [214])
        self.assertIn("компенсация", DELETE_REFUSED_REPLY)
        self.assertIn("компенсация", MOVE_REFUSED_REPLY)
        self.assertNotIn("пенси", DELETE_REFUSED_REPLY)
        self.assertNotIn("пособи", DELETE_REFUSED_REPLY)
        self.assertNotIn("гонорар", DELETE_REFUSED_REPLY)

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Компенсация",
            "удали все документы в папке «Компенсация»",
            "удали все документы в папке «Компенсация морального вреда»",
            "удали все документы в папке «Денежная компенсация»",
            "удали все документы по делу Компенсация",
            "удали все документы по делу «Компенсация»",
            "удали все документы по делу «Денежная компенсация»",
            "удали все документы без компенсации в этой папке",
            "удали все документы за пенсию в этой папке",
            "удали все документы за пособие в этой папке",
            "удали все документы за гонорар в этой папке",
            "удали все документы за надбавку в этой папке",
            "удали все документы за доплату в этой папке",
            "удали все документы за премию в этой папке",
            "удали все документы за зарплату в этой папке",
            "удали все документы за алименты в этой папке",
            "удали все документы за оплату труда в этой папке",
            "удали все документы за вознаграждение в этой папке",
            "удали все документы за компенсационный фонд в этой папке",
            "удали все документы за компенсационные выплаты в этой папке",
            "удали все документы за компенсаторный платеж в этой папке",
            "удали все документы за страхование в этой папке",
            "удали все документы за банкротство в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Компенсация",
            "собери все документы в папку Компенсация морального вреда",
            "удали документ 214",
        ):
            self.assertFalse(looks_like_compensation_scoped_document_request(text), text)
            self.assertFalse(compensation_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за компенсацию",
            "по компенсации",
            "о компенсации",
            "об компенсации",
            "на компенсацию",
            "с компенсации",
            "за «компенсацию»",
            "за Компенсацию",
            "за взыскание компенсации",
            "по взысканию компенсации",
            "за невыплату компенсации",
            "по выплате компенсации",
            "за задержку компенсации",
            "по размеру компенсации",
            "за начисление компенсации",
            "по задолженности по компенсации",
            "за платеж компенсации",
            "за индексацию компенсации",
            "за получение компенсации",
            "за лишение компенсации",
            "по проценту компенсации",
            "за период компенсации",
            "в ходе компенсации",
            "за счет компенсации",
            "за счёт компенсации",
            "при компенсации",
            "за полную компенсацию",
            "за частичную компенсацию",
            "за текущую компенсацию",
            "за открытую компенсацию",
            "за денежную компенсацию",
            "за материальную компенсацию",
            "за моральную компенсацию",
            "за страховую компенсацию",
            "за судебную компенсацию",
            "за отпускную компенсацию",
            "за компенсацию морального вреда",
            "за компенсацию расходов",
            "за компенсацию убытков",
            "за компенсацию ущерба",
            "за компенсацию отпуска",
            "за компенсацию за неиспользованный отпуск",
            "за перерасчет компенсации",
            "за перерасчёт компенсации",
            "за удержание компенсации",
            "за расчет компенсации",
            "за расчёт компенсации",
            "за доплату компенсации",
            "за недоплату компенсации",
            "до компенсации",
            "за первую компенсацию",
            "за мою компенсацию",
            "за моё компенсацию",
            "за нашу сумму компенсации",
            "по твоей компенсации",
            "за ваши компенсации",
            "во время компенсации",
            "во время начисления компенсации",
            "за не компенсацию",
            "с компенсацией",
            "из компенсаций",
            "о компенсациях",
            "компенсациями",
            "компенсациям",
            "компенсаций",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_compensation_scoped_document_request(
                    f"удали все документы {text} в этой папке"
                ),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"', source)
        self.assertIn("compensation_blocks_bulk_document_mutation", source)
        self.assertIn("mask_compensation_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("compensation_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_compensation_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_compensation_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("compensation_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
