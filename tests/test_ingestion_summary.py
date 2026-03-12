from app.ingestion.service import IngestionSummary


def test_ingestion_summary_includes_run_and_csv_counters() -> None:
    summary = IngestionSummary(run_id=7, scanned_messages=3, csv_rows_parsed=11)
    payload = summary.to_dict()

    assert payload["run_id"] == 7
    assert payload["scanned_messages"] == 3
    assert payload["csv_rows_parsed"] == 11
