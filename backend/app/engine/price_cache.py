from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from typing import cast

import pandas as pd
from postgrest.types import ReturnMethod
from supabase import Client, create_client

from app.db_types import PublicPriceHistoryInsert
from app.supabase import supabase

QUERY_PAGE_SIZE = 1_000
UPSERT_BATCH_SIZE = 1_000


def _normalize_tickers(tickers: list[str]) -> list[str]:
    normalized: list[str] = []
    for ticker in tickers:
        normalized_ticker = ticker.strip().upper()
        if normalized_ticker and normalized_ticker not in normalized:
            normalized.append(normalized_ticker)
    return normalized


def _date_iso(value: pd.Timestamp | dt.date | str) -> str:
    return pd.Timestamp(value).date().isoformat()


def _frame_from_records(
    records: list[dict[str, object]], tickers: list[str]
) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=tickers)

    frame = pd.DataFrame(records)
    frame["price_date"] = pd.to_datetime(frame["price_date"])
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    frame["adjusted_close"] = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    frame = frame.sort_values(["price_date", "ticker"])

    pivot = (
        frame.pivot(index="price_date", columns="ticker", values="adjusted_close")
        .sort_index()
        .reindex(columns=tickers)
        .dropna(how="any")
    )
    pivot.index.name = None
    return pivot


@dataclass(slots=True)
class SupabasePriceCache:
    table: str = "price_history"
    timeout_s: float = 10.0
    supabase: Client | None = supabase
    supabase_url: str | None = None
    api_key: str | None = field(default=None, repr=False)

    @property
    def enabled(self) -> bool:
        return bool(self.supabase)

    def query_prices(
        self,
        tickers: list[str],
        start_date: pd.Timestamp | dt.date | str | None = None,
        end_date: pd.Timestamp | dt.date | str | None = None,
    ) -> pd.DataFrame:
        normalized_tickers = _normalize_tickers(tickers)
        if not normalized_tickers or self.supabase is None:
            return pd.DataFrame()

        records: list[dict[str, object]] = []
        offset = 0

        while True:
            query = (
                self.supabase.table(self.table)
                .select("ticker,price_date,adjusted_close")
                .in_("ticker", normalized_tickers)
                .order("price_date")
                .order("ticker")
                .range(offset, offset + QUERY_PAGE_SIZE - 1)
            )
            if start_date is not None:
                query = query.gte("price_date", _date_iso(start_date))
            if end_date is not None:
                query = query.lte("price_date", _date_iso(end_date))

            response = query.execute()
            page = response.data or []
            records.extend(page)

            if len(page) < QUERY_PAGE_SIZE:
                break
            offset += QUERY_PAGE_SIZE

        return _frame_from_records(records, normalized_tickers)

    def upsert_prices(self, prices: pd.DataFrame, source: str = "yfinance") -> None:
        if prices.empty or self.supabase is None:
            return

        rows: list[PublicPriceHistoryInsert] = []
        for price_date, row in prices.iterrows():
            row_date = pd.Timestamp(price_date).date()
            for ticker, value in row.items():
                if pd.isna(value):
                    continue
                normalized_ticker = str(ticker).strip().upper()
                if not normalized_ticker:
                    continue

                rows.append(
                    cast(
                        PublicPriceHistoryInsert,
                        {
                            "ticker": normalized_ticker,
                            "price_date": row_date.isoformat(),
                            "adjusted_close": float(value),
                            "source": source,
                        },
                    )
                )

        if not rows:
            return

        for offset in range(0, len(rows), UPSERT_BATCH_SIZE):
            self.supabase.table(self.table).upsert(
                rows[offset : offset + UPSERT_BATCH_SIZE],
                on_conflict="ticker,price_date",
                returning=ReturnMethod.minimal,
            ).execute()


def build_supabase_price_cache_from_env() -> SupabasePriceCache | None:
    supabase_url = os.getenv("SUPABASE_URL")
    api_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not supabase_url or not api_key:
        return None

    return SupabasePriceCache(
        supabase=create_client(supabase_url=supabase_url, supabase_key=api_key),
        supabase_url=supabase_url,
        api_key=api_key,
    )
