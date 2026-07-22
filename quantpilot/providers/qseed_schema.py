"""Q-SEED data schema constants and column mappings."""

from typing import Final

# Raw Q-SEED parquet / DuckDB column names
QSEED_DATE: Final = "Date"
QSEED_TICKER: Final = "Ticker"
QSEED_OPEN: Final = "Open"
QSEED_HIGH: Final = "High"
QSEED_LOW: Final = "Low"
QSEED_CLOSE: Final = "Close"
QSEED_VOLUME: Final = "Volume"
QSEED_MARKET: Final = "Market"
QSEED_DIVIDENDS: Final = "Dividends"
QSEED_SPLIT: Final = "Split"

QSEED_PRICE_COLUMNS: Final = (
    QSEED_DATE,
    QSEED_TICKER,
    QSEED_OPEN,
    QSEED_HIGH,
    QSEED_LOW,
    QSEED_CLOSE,
    QSEED_VOLUME,
    QSEED_MARKET,
)

# QuantPilot standardized output columns
QP_SYMBOL: Final = "symbol"
QP_DATE: Final = "date"
QP_OPEN: Final = "open"
QP_HIGH: Final = "high"
QP_LOW: Final = "low"
QP_CLOSE: Final = "close"
QP_VOLUME: Final = "volume"
QP_MARKET: Final = "market"

QP_PRICE_COLUMNS: Final = (
    QP_SYMBOL,
    QP_DATE,
    QP_OPEN,
    QP_HIGH,
    QP_LOW,
    QP_CLOSE,
    QP_VOLUME,
    QP_MARKET,
)

# Parquet shard file pattern: stocks_0001.parquet .. stocks_0099.parquet
PARQUET_SHARD_PATTERN: Final = "stocks_{shard:04d}.parquet"

# DuckDB raw_stocks table (alternative query path in stocks.db)
RAW_STOCKS_TABLE: Final = "raw_stocks"

# Metadata files under data_log/
KRX_LIST_FILE: Final = "krx_list.csv"
LAST_DATE_FILE: Final = "last_date.txt"
COMPLETED_DATA_LIST_FILE: Final = "completed_data_list.txt"

# Column rename map: Q-SEED -> QuantPilot
COLUMN_RENAME_MAP: Final = {
    QSEED_DATE: QP_DATE,
    QSEED_TICKER: QP_SYMBOL,
    QSEED_OPEN: QP_OPEN,
    QSEED_HIGH: QP_HIGH,
    QSEED_LOW: QP_LOW,
    QSEED_CLOSE: QP_CLOSE,
    QSEED_VOLUME: QP_VOLUME,
    QSEED_MARKET: QP_MARKET,
}
