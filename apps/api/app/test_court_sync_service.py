import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.court_sync_service import upsert_case_source, upsert_document_source
from app.db import Base
from app.models import Case, Document


class CourtSyncServiceRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_case_source_upsert_preserves_existing_case_link_when_worker_omits_link(self) -> None:
        db = self.Session()
        try:
            case = Case(title="A40", court_name="", case_number="A40-1/2026")
            db.add(case)
            db.commit()

            source = upsert_case_source(
                db,
                remote_case_id="remote-case",
                source_system="kad",
                linked_case_id=case.id,
                case_number="A40-1/2026",
            )
            self.assertEqual(source.case_id, case.id)

            source = upsert_case_source(
                db,
                remote_case_id="remote-case",
                source_system="kad",
                linked_case_id=None,
                case_number="A40-1/2026",
            )

            self.assertEqual(source.case_id, case.id)
        finally:
            db.close()

    def test_document_source_upsert_preserves_downloaded_document_link_on_failed_update(self) -> None:
        db = self.Session()
        try:
            case = Case(title="A40", court_name="", case_number="A40-2/2026")
            db.add(case)
            db.commit()
            doc = Document(case_id=case.id, filename="decision.pdf", s3_key="local/decision.pdf")
            db.add(doc)
            db.commit()

            source = upsert_document_source(
                db,
                remote_document_id="https://kad.arbitr.ru/doc/decision",
                local_document_id=doc.id,
                filename="decision.pdf",
                status="downloaded",
            )
            self.assertEqual(source.local_document_id, doc.id)
            self.assertIsNotNone(source.last_downloaded_at)

            source = upsert_document_source(
                db,
                remote_document_id="https://kad.arbitr.ru/doc/decision",
                local_document_id=None,
                filename="decision.pdf",
                status="failed",
            )

            self.assertEqual(source.local_document_id, doc.id)
            self.assertEqual(source.status, "failed")
            self.assertIsNotNone(source.last_downloaded_at)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
