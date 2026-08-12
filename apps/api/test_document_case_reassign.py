"""Regression: moving a document must relocate DocumentChunk.case_id for RAG."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class ReassignDocumentCaseTests(unittest.TestCase):
    def test_updates_existing_chunk_case_ids(self) -> None:
        from app.document_case_reassign import reassign_document_to_case

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.update.return_value = 2

        document = MagicMock()
        document.id = 42
        document.case_id = 1
        document.extracted_text = "полный текст решения"

        with patch("app.document_case_reassign.sync_document_chunks") as sync_chunks:
            out = reassign_document_to_case(db, document, 7)

        self.assertIs(out, document)
        self.assertEqual(document.case_id, 7)
        query.update.assert_called_once()
        args, kwargs = query.update.call_args
        values = args[0]
        # SQLAlchemy Column keys or plain strings depending on mock/model
        case_values = [v for k, v in values.items() if getattr(k, "key", k) == "case_id" or k == "case_id"]
        self.assertEqual(case_values, [7])
        self.assertEqual(kwargs.get("synchronize_session"), "fetch")
        sync_chunks.assert_not_called()

    def test_syncs_chunks_when_none_exist_but_text_present(self) -> None:
        from app.document_case_reassign import reassign_document_to_case

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.update.return_value = 0

        document = MagicMock()
        document.id = 9
        document.case_id = 3
        document.extracted_text = "есть текст для индексации"

        with patch("app.document_case_reassign.sync_document_chunks") as sync_chunks:
            reassign_document_to_case(db, document, 11)

        self.assertEqual(document.case_id, 11)
        sync_chunks.assert_called_once_with(db, document)

    def test_does_not_sync_when_no_chunks_and_empty_text(self) -> None:
        from app.document_case_reassign import reassign_document_to_case

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.update.return_value = 0

        document = MagicMock()
        document.id = 5
        document.case_id = 2
        document.extracted_text = "   "

        with patch("app.document_case_reassign.sync_document_chunks") as sync_chunks:
            reassign_document_to_case(db, document, 8)

        self.assertEqual(document.case_id, 8)
        sync_chunks.assert_not_called()


if __name__ == "__main__":
    unittest.main()
