"""Чистые хелперы маршрутизации скачанных судебных PDF в папку дела."""


def ingest_case_number_from_search_result(
    case_data: dict | None,
    page_extracted: str | None = None,
) -> str:
    """
    Номер дела для ingest: сначала результат поиска/карточки, не первый regex по HTML.

    HTML карточки КАД часто содержит чужие номера раньше текущего
    (связанные дела, история инстанций, JSON). Первый match уводит PDF в чужую папку.
    """
    for raw in ((case_data or {}).get("case_number"), page_extracted):
        s = (raw or "").strip()
        if s:
            return s
    return ""
