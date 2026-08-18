import unittest

from app.delete_anaphora import (
    clarification_for_ambiguous_anaphora,
    is_singular_document_anaphora,
    looks_like_document_delete_anaphora,
    resolve_anaphora_document_ids,
)


class DeleteAnaphoraTests(unittest.TestCase):
    def test_singular_phrases_detected(self) -> None:
        self.assertTrue(looks_like_document_delete_anaphora("удали этот документ"))
        self.assertTrue(looks_like_document_delete_anaphora("убери этот файл"))
        self.assertTrue(is_singular_document_anaphora("удали этот документ и папку"))

    def test_plural_phrases_detected_but_not_singular(self) -> None:
        self.assertTrue(looks_like_document_delete_anaphora("удали эти документы"))
        self.assertFalse(is_singular_document_anaphora("удали эти документы"))
        self.assertTrue(looks_like_document_delete_anaphora("удали найденные файлы"))
        self.assertFalse(is_singular_document_anaphora("удали из списка"))

    def test_plural_wins_over_singular(self) -> None:
        self.assertFalse(is_singular_document_anaphora("удали этот документ и эти файлы тоже"))

    def test_singular_with_from_list_still_singular(self) -> None:
        self.assertTrue(is_singular_document_anaphora("удали этот документ из списка"))

    def test_singular_multi_id_asks_instead_of_deleting(self) -> None:
        ids, err = resolve_anaphora_document_ids("удали этот документ", [213, 214, 215])
        self.assertEqual(ids, [])
        self.assertIsNotNone(err)
        self.assertIn("[213]", err)
        self.assertIn("[214]", err)
        self.assertIn("[215]", err)
        self.assertIn("удали документ 214", err)
        self.assertIn("удали эти документы", err)

    def test_singular_one_id_deletes_that_file(self) -> None:
        ids, err = resolve_anaphora_document_ids("удали этот документ", [213])
        self.assertEqual(ids, [213])
        self.assertIsNone(err)

    def test_singular_zero_ids_falls_through(self) -> None:
        ids, err = resolve_anaphora_document_ids("удали этот документ", [])
        self.assertEqual(ids, [])
        self.assertIsNone(err)

    def test_plural_keeps_all_ids(self) -> None:
        ids, err = resolve_anaphora_document_ids("удали эти документы", [213, 214, 215])
        self.assertEqual(ids, [213, 214, 215])
        self.assertIsNone(err)

    def test_from_list_keeps_all_ids(self) -> None:
        ids, err = resolve_anaphora_document_ids("удали из списка", [10, 20])
        self.assertEqual(ids, [10, 20])
        self.assertIsNone(err)

    def test_non_anaphora_does_not_block(self) -> None:
        ids, err = resolve_anaphora_document_ids("удали документы 10 20", [10, 20, 99])
        self.assertEqual(ids, [10, 20, 99])
        self.assertIsNone(err)

    def test_dedupes_and_drops_non_positive(self) -> None:
        ids, err = resolve_anaphora_document_ids("удали эти файлы", [0, -1, 5, 5, 7])
        self.assertEqual(ids, [5, 7])
        self.assertIsNone(err)

    def test_clarification_truncates_long_lists(self) -> None:
        msg = clarification_for_ambiguous_anaphora(list(range(1, 25)))
        self.assertIn("[1]", msg)
        self.assertIn("[20]", msg)
        self.assertNotIn("[21]", msg)
        self.assertIn("и ещё 4", msg)


if __name__ == "__main__":
    unittest.main()
