"""Unit tests for true-duplicate matching (no Postgres / FastAPI import)."""

from __future__ import annotations

import unittest

from app.document_duplicate_match import (
    MIN_SHARED_TRUE_DUPLICATES_FOR_MERGE,
    connected_case_components,
    content_fingerprint,
    pair_share_counts,
    true_duplicate_group_key,
)


class ContentFingerprintTests(unittest.TestCase):
    def test_short_or_empty_text_is_not_fingerprinted(self) -> None:
        self.assertIsNone(content_fingerprint(""))
        self.assertIsNone(content_fingerprint("   "))
        self.assertIsNone(content_fingerprint("короткий текст"))

    def test_same_text_same_fingerprint_after_whitespace_normalize(self) -> None:
        a = "Арбитражный суд города Москвы\n\nОпределение по делу А40-1/2024 " + ("x" * 40)
        b = "Арбитражный суд города Москвы Определение по делу А40-1/2024 " + ("x" * 40)
        self.assertEqual(content_fingerprint(a), content_fingerprint(b))

    def test_different_text_different_fingerprint(self) -> None:
        a = "Определение по делу А40-111/2024: удовлетворить ходатайство истца. " + ("a" * 40)
        b = "Определение по делу А40-222/2025: отказать в удовлетворении. " + ("b" * 40)
        self.assertNotEqual(content_fingerprint(a), content_fingerprint(b))


class GroupKeyTests(unittest.TestCase):
    def test_require_content_rejects_filename_only_collision(self) -> None:
        text_a = "Текст определения по делу А40-111/2024. " + ("a" * 40)
        text_b = "Текст определения по делу А40-222/2025. " + ("b" * 40)
        key_a = true_duplicate_group_key("Определение.pdf", text_a, require_content_match=True)
        key_b = true_duplicate_group_key("Определение.pdf", text_b, require_content_match=True)
        self.assertIsNotNone(key_a)
        self.assertIsNotNone(key_b)
        self.assertNotEqual(key_a, key_b)

    def test_identical_content_same_key(self) -> None:
        text = "Полный одинаковый текст судебного акта. " + ("z" * 40)
        key_a = true_duplicate_group_key("Определение.pdf", text, require_content_match=True)
        key_b = true_duplicate_group_key("определение.pdf", text, require_content_match=True)
        self.assertEqual(key_a, key_b)

    def test_empty_text_skipped_when_content_required(self) -> None:
        self.assertIsNone(
            true_duplicate_group_key("Определение.pdf", "", require_content_match=True)
        )

    def test_filename_only_opt_in_groups_by_name(self) -> None:
        key_a = true_duplicate_group_key("Определение.pdf", "aaa", require_content_match=False)
        key_b = true_duplicate_group_key("определение.pdf", "bbb", require_content_match=False)
        self.assertEqual(key_a, key_b)


class MergeComponentTests(unittest.TestCase):
    def test_single_shared_generic_filename_does_not_merge_unrelated_cases(self) -> None:
        """Concrete trigger: two unrelated cases each have «Определение.pdf» with different text."""
        text_a = "Определение по делу А40-111/2024 — отложить заседание. " + ("a" * 40)
        text_b = "Определение по делу А40-999/2025 — взыскать расходы. " + ("b" * 40)
        case_docs = [
            (1, "Определение.pdf", text_a),
            (1, "Иск.pdf", "Исковое заявление А40-111/2024. " + ("c" * 40)),
            (2, "Определение.pdf", text_b),
            (2, "Отзыв.pdf", "Отзыв ответчика А40-999/2025. " + ("d" * 40)),
        ]
        shares = pair_share_counts(case_docs, require_content_match=True)
        self.assertEqual(shares, {})
        self.assertEqual(
            connected_case_components(
                case_docs,
                require_content_match=True,
                min_shared_keys=MIN_SHARED_TRUE_DUPLICATES_FOR_MERGE,
            ),
            [],
        )

    def test_one_identical_file_still_insufficient_for_folder_merge(self) -> None:
        """Even a true single-file duplicate must not collapse whole folders alone."""
        shared = "Общий шаблон ходатайства, случайно попавший в оба дела. " + ("s" * 40)
        case_docs = [
            (1, "Ходатайство.pdf", shared),
            (1, "Уникальный-A.pdf", "Только дело A материалы. " + ("a" * 40)),
            (2, "Ходатайство.pdf", shared),
            (2, "Уникальный-B.pdf", "Только дело B материалы. " + ("b" * 40)),
        ]
        shares = pair_share_counts(case_docs, require_content_match=True)
        self.assertEqual(shares[(1, 2)], 1)
        self.assertEqual(
            connected_case_components(
                case_docs,
                require_content_match=True,
                min_shared_keys=MIN_SHARED_TRUE_DUPLICATES_FOR_MERGE,
            ),
            [],
        )

    def test_two_true_duplicates_link_cases(self) -> None:
        shared1 = "Первый общий документ полностью идентичен. " + ("1" * 40)
        shared2 = "Второй общий документ полностью идентичен. " + ("2" * 40)
        case_docs = [
            (10, "Акт1.pdf", shared1),
            (10, "Акт2.pdf", shared2),
            (10, "Лишнее.pdf", "Только в первой папке. " + ("x" * 40)),
            (20, "Акт1.pdf", shared1),
            (20, "Акт2.pdf", shared2),
        ]
        comps = connected_case_components(
            case_docs,
            require_content_match=True,
            min_shared_keys=MIN_SHARED_TRUE_DUPLICATES_FOR_MERGE,
        )
        self.assertEqual(comps, [[10, 20]])

    def test_filename_only_legacy_would_have_merged_unrelated(self) -> None:
        """Documents the old bug: filename-only pairing merges unrelated cases."""
        case_docs = [
            (1, "Определение.pdf", "текст A " + ("a" * 40)),
            (2, "Определение.pdf", "текст B " + ("b" * 40)),
        ]
        legacy = connected_case_components(
            case_docs,
            require_content_match=False,
            min_shared_keys=1,
        )
        self.assertEqual(legacy, [[1, 2]])
        safe = connected_case_components(
            case_docs,
            require_content_match=True,
            min_shared_keys=MIN_SHARED_TRUE_DUPLICATES_FOR_MERGE,
        )
        self.assertEqual(safe, [])


if __name__ == "__main__":
    unittest.main()
