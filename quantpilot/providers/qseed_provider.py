"""Q-SEED data provider backed by local parquet shards."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

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
from quantpilot.providers.sql_utils import sql_string_literal

_CACHE_FILENAME = "shard_index.json"


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
        if not self._metadata.has_symbol(symbol):
            return False
        return symbol in self._get_shard_index()

    def list_symbols(self) -> list[str]:
        index = self._get_shard_index()
        return sorted(
            symbol for symbol in self._metadata.list_symbols() if symbol in index
        )

    def get_last_date(self) -> date | None:
        return self._metadata.get_last_date()

    def get_price(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        if not self.has_symbol(symbol):
            raise SymbolNotFoundError(symbol)

        shard = self._resolve_shard(symbol)
        parquet_path = self._data_path / PARQUET_SHARD_PATTERN.format(shard=shard)

        conn = duckdb.connect()
        try:
            path_literal = sql_string_literal(parquet_path)
            query = f"""
                SELECT Date, Ticker, Open, High, Low, Close, Volume, Market
                FROM read_parquet({path_literal})
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
            raise SymbolNotFoundError(symbol)
        return index[symbol]

    def _parquet_shard_paths(self) -> list[Path]:
        return sorted(
            path
            for path in self._data_path.glob("stocks_*.parquet")
            if not path.name.startswith("._")
        )

    def _dataset_fingerprint(self) -> str:
        parts: list[str] = []
        for parquet_path in self._parquet_shard_paths():
            stat = parquet_path.stat()
            parts.append(f"{parquet_path.name}:{stat.st_mtime_ns}:{stat.st_size}")
        digest = hashlib.sha256("\n".join(parts).encode()).hexdigest()
        return digest

    def _load_cache(self, cache_file: Path) -> dict[str, int] | None:
        if not cache_file.exists():
            return None

        try:
            payload: dict[str, Any] = json.loads(cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        if payload.get("fingerprint") != self._dataset_fingerprint():
            return None

        index = payload.get("index")
        if not isinstance(index, dict):
            return None

        return {str(symbol): int(shard) for symbol, shard in index.items()}

    def _write_cache(self, cache_file: Path, index: dict[str, int]) -> None:
        payload = {
            "fingerprint": self._dataset_fingerprint(),
            "index": index,
        }
        self._cache_path.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            dir=self._cache_path,
            prefix="shard_index.",
            suffix=".tmp",
        )
        os.close(fd)
        temp_file = Path(temp_path)
        try:
            temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(temp_file, cache_file)
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def _build_shard_index(self) -> dict[str, int]:
        index: dict[str, int] = {}
        conn = duckdb.connect()
        try:
            for parquet_path in self._parquet_shard_paths():
                shard = int(parquet_path.stem.split("_")[-1])
                path_literal = sql_string_literal(parquet_path)
                rows = conn.execute(
                    f"SELECT DISTINCT {QSEED_TICKER} FROM read_parquet({path_literal})"
                ).fetchall()
                for (ticker,) in rows:
                    index[ticker] = shard
        finally:
            conn.close()
        return index

    def _get_shard_index(self) -> dict[str, int]:
        if self._shard_index is not None:
            return self._shard_index

        cache_file = self._cache_path / _CACHE_FILENAME
        cached = self._load_cache(cache_file)
        if cached is not None:
            self._shard_index = cached
            return cached

        index = self._build_shard_index()
        self._write_cache(cache_file, index)
        self._shard_index = index
        return index
