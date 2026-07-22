"""Tests for MetadataManager."""

from __future__ import annotations

from pathlib import Path

from quantpilot.datasource.metadata_manager import MetadataManager


def test_metadata_manager_reads_files(tmp_path: Path) -> None:
    data_log = tmp_path / "data_log"
    data_log.mkdir()
    (data_log / "krx_list.csv").write_text(
        "Ticker,Market\n005930.KS,KOSPI\nAAPL,NASDAQ\n",
        encoding="utf-8",
    )
    (data_log / "last_date.txt").write_text("2026-07-17\n", encoding="utf-8")
    (data_log / "completed_data_list.txt").write_text("005930.KS\n", encoding="utf-8")

    metadata = MetadataManager(data_log)
    assert metadata.has_symbol("005930.KS")
    assert metadata.get_market("005930.KS") == "KOSPI"
    assert metadata.get_last_date().isoformat() == "2026-07-17"
    assert metadata.has_data("005930.KS")
    assert not metadata.has_data("AAPL")
