from app.court_kad_search import looks_like_cancel_court_sync_jobs


def test_cancel_command_matches_clear_imperative() -> None:
    assert looks_like_cancel_court_sync_jobs("Останови все задачи КАД") is True


def test_cancel_command_ignores_negated_imperative() -> None:
    assert looks_like_cancel_court_sync_jobs("Не останови все задачи, только покажи статус") is False
    assert looks_like_cancel_court_sync_jobs("Не останавливай фоновые задачи") is False
    assert looks_like_cancel_court_sync_jobs("Не отменяй задачи скачивания") is False
