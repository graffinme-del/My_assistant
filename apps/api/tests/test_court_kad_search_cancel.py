from app.court_kad_search import looks_like_cancel_court_sync_jobs


def test_cancel_requires_download_or_queue_context() -> None:
    assert looks_like_cancel_court_sync_jobs("отмени все задачи") is True
    assert looks_like_cancel_court_sync_jobs("останови скачивание") is True
    assert looks_like_cancel_court_sync_jobs("останови все задачи КАД") is True

    assert looks_like_cancel_court_sync_jobs("останови всё, давай по пунктам") is False
    assert looks_like_cancel_court_sync_jobs("останови все и объясни заново") is False


def test_cancel_ignores_negated_and_report_phrases() -> None:
    assert looks_like_cancel_court_sync_jobs("не останавливай задачи КАД") is False
    assert looks_like_cancel_court_sync_jobs("отчёт по задаче 123") is False
