"""Q-SEED data provider backed by local parquet shards."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import polars as pl

from quantpilot.datasource.metadata_manager import MetadataManager
from quantpilot.exceptions import DataNotAvailableError, SymbolNotFoundError
from quantpilot.providers.base_provider import BaseProvider
from quantpilot.providers.qseed_schema import (
    COLUMN_RENAME_MAP,
    PARQUET_SHARD_PATTERN,
    QP_PRICE_COLUMNS,
    QSEED_DATE,
    QSEED_TICKER,
)


class QSeedProvider(BaseProvider):
    """Read OHLCV data from Q-SEED parquet shards on local storage."""

    def __init__(
        self,
        data_path: Path,
        metadata: MetadataManager,
        cache_path: Path | None = None,
    ) -> None:
        self._data_path = data_path
        self._metadata = metadata
        self._cache_path = cache_path or data_path.parent / ".quantpilot_cache"
        self._shard_index: dict[str, int] | None = None

    def has_symbol(self, symbol: str) -> bool:
        return self._metadata.has_symbol(symbol)

    def list_symbols(self) -> list[str]:
        return self._metadata.list_symbols()

    def get_last_date(self) -> date | None:
        return self._metadata.get_last_date()

    def get_price(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        if not self.has_symbol(symbol):
            raise SymbolNotFoundError(symbol)

        shard = self._resolve_shard(symbol)
        parquet_path = self._data_path / PARQUET_SHARD_PATTERN.format(shard=shard)

        conn = duckdb.connect()
        try:
            query = f"""
                SELECT Date, Ticker, Open, High, Low, Close, Volume, Market
                FROM read_parquet('{parquet_path}')
                WHERE {QSEED_TICKER} = ?
                  AND CAST({QSEED_DATE} AS DATE) >= ?
                  AND CAST({QSEED_DATE} AS DATE) <= ?
                ORDER BY {QSEED_DATE}
            """
            pdf = conn.execute(query, [symbol, start, end]).pl()
        finally:
            conn.close()

        if pdf.is_empty():
            raise DataNotAvailableError(symbol, str(start), str(end))

        result = (
            pdf.rename(COLUMN_RENAME_MAP)
            .with_columns(pl.col("date").cast(pl.Date))
            .unique(subset=["date"], keep="last")
            .sort("date")
            .select(list(QP_PRICE_COLUMNS))
        )
        return result

    def _resolve_shard(self, symbol: str) -> int:
        index = self._get_shard_index()
        if symbol not in index:
            raise DataNotAvailableError(symbol, "?", "?")
        return index[symbol]

    def _get_shard_index(self) -> dict[str, int]:
        if self._shard_index is not None:
            return self._shard_index

        cache_file = self._cache_path / "shard_index.json"
        if cache_file.exists():
            self._shard_index = {
                k: int(v) for k, v in json.loads(cache_file.read_text()).items()
            }
            return self._shard_index

        index: dict[str, int] = {}
        conn = duckdb.connect()
        try:
            for parquet_path in sorted(self._data_path.glob("stocks_*.parquet")):
                if parquet_path.name.startswith("._"):
                    continue
                shard_str = parquet_path.stem.split("_")[-1]
                shard = int(shard_str)
                rows = conn.execute(
                    f"SELECT DISTINCT {QSEED_TICKER} "
                    f"FROM read_parquet('{parquet_path}')"
                ).fetchall()
                for (ticker,) in rows:
                    index[ticker] = shard
        finally:
            conn.close()

        self._cache_path.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(index, indent=2), encoding="utf-8")
        self._shard_index = index
        return index
