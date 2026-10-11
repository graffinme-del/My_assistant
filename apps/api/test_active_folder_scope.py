"""«текущ» / «открыт» / «в этой» must not select the open folder by themselves.

Pre-fix, handle_delete_documents_chat treated any of those substrings, together
with «все документы», as delete-every-file in the active case.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from app.active_folder_scope import looks_like_active_folder_reference


def _pre_fix_active_folder(text: str) -> bool:
    low = (text or "").lower()
    return any(p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело"))


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


class ActiveFolderScopeTests(unittest.TestCase):
    def test_documented_folder_commands_still_match(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы этой папки",
            "удали все документы в этой же папке",
            "удали все документы в текущей папке",
            "удали все документы текущей папки",
            "удали все документы в текущем деле",
            "удали все документы текущего дела",
            "удали все документы в открытой папке",
            "удали все документы открытой папки",
            "удали все документы в открытом деле",
            "удали все документы открытого дела",
            "удали все документы это дело",
            "удали все файлы в этой папке",
            "удали каждый документ в текущей папке",
        ):
            self.assertTrue(_wants_all(text), text)
            self.assertTrue(_pre_fix_active_folder(text), text)
            self.assertTrue(looks_like_active_folder_reference(text), text)

    def test_unrelated_tekush_and_otkryt_do_not_select_the_open_folder(self) -> None:
        for text in (
            "удали все документы по текущей задолженности",
            "удали все документы за текущий ремонт",
            "удали все документы за текущие платежи",
            "удали все документы после открытия",
            "удали все документы об открытии счета",
            "удали все документы открытые вчера",
            "удали все документы, которые открыты",
            "удали все документы в этой ситуации",
            "удали все документы в этой редакции",
            "удали все документы из этой выгрузки",
            "удали все документы это делопроизводство",
        ):
            self.assertTrue(_wants_all(text), text)
            self.assertTrue(_pre_fix_active_folder(text), text)
            self.assertFalse(looks_like_active_folder_reference(text), text)

    def test_case_title_and_named_folder_are_not_the_active_folder_shortcut(self) -> None:
        for text in (
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы в папке Наблюдение",
            "удали все документы в папке Конкурсное производство",
        ):
            self.assertFalse(looks_like_active_folder_reference(text), text)

    def test_main_uses_the_helper_instead_of_the_bare_substrings(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("looks_like_active_folder_reference", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("looks_like_active_folder_reference(text)", delete_fn)
        self.assertNotIn('"открыт"', delete_fn)
        self.assertNotIn('"текущ"', delete_fn)


if __name__ == "__main__":
    unittest.main()
