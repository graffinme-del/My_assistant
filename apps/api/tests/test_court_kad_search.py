from app.court_kad_search import looks_like_cancel_court_sync_jobs


def test_cancel_court_sync_jobs_requires_command_like_phrase() -> None:
    assert looks_like_cancel_court_sync_jobs("останови все задачи") is True
    assert looks_like_cancel_court_sync_jobs("пожалуйста, остановить фоновые задачи") is True
    assert looks_like_cancel_court_sync_jobs("сбрось очередь кад") is True


def test_cancel_court_sync_jobs_ignores_negated_or_explanatory_mentions() -> None:
    for text in (
        "Почему ты не останови все задачи сами?",
        "Не останови все загрузки, только КАД",
        "Объясни, зачем останови все процессы вчера",
    ):
        assert looks_like_cancel_court_sync_jobs(text) is False
