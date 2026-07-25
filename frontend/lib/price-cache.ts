import {
  portfolioDb,
  type CachedPriceResponse,
  type HistoricalPriceRow,
  type TickerMetadata,
} from "@/lib/portfolio-db"
import { apiUrl } from "@/lib/api"
import { getPriceRefreshIntervalMs } from "@/lib/user-settings"

type ApiErrorDetail = {
  msg?: string
  message?: string
}

export type HistoricalPricesResponse = {
  tickers: string[]
  period: string
  rows: HistoricalPriceRow[]
  metadata?: Record<string, TickerMetadata>
}

export type HistoricalPricesResult = {
  data: HistoricalPricesResponse
  source: "cache" | "network" | "stale-cache"
  fetchedAt: string
}

function normalizeTickers(tickers: string[]) {
  return Array.from(
    new Set(
      tickers
        .map((ticker) => ticker.trim().toUpperCase())
        .filter((ticker) => ticker.length > 0),
    ),
  ).sort()
}

function getPriceCacheKey({
  tickers,
  period,
  includeMetadata,
}: {
  tickers: string[]
  period: string
  includeMetadata: boolean
}) {
  const metadataSuffix = includeMetadata ? "metadata" : "prices"
  return `${period}:${metadataSuffix}:${normalizeTickers(tickers).join(",")}`
}

function isFresh(cached: CachedPriceResponse) {
  const fetchedAt = Date.parse(cached.fetchedAt)
  return (
    Number.isFinite(fetchedAt) &&
    Date.now() - fetchedAt < getPriceRefreshIntervalMs()
  )
}

function toResponse(cached: CachedPriceResponse): HistoricalPricesResponse {
  return {
    tickers: cached.tickers,
    period: cached.period,
    rows: cached.rows,
    metadata: cached.metadata,
  }
}

async function getErrorMessage(response: Response) {
  const errorData = await response.json().catch(() => null)

  if (typeof errorData?.detail === "string") {
    return errorData.detail
  }

  if (Array.isArray(errorData?.detail)) {
    return errorData.detail
      .map(
        (item: ApiErrorDetail) => item.msg || item.message || "Invalid input",
      )
      .join(", ")
  }

  return `Server error: ${response.status}`
}

export async function fetchHistoricalPricesWithCache({
  tickers,
  period,
  includeMetadata = false,
}: {
  tickers: string[]
  period: string
  includeMetadata?: boolean
}): Promise<HistoricalPricesResult> {
  const normalizedTickers = normalizeTickers(tickers)
  const cacheKey = getPriceCacheKey({
    tickers: normalizedTickers,
    period,
    includeMetadata,
  })
  const cached = await portfolioDb.priceResponses.get(cacheKey)

  if (cached && isFresh(cached)) {
    return {
      data: toResponse(cached),
      source: "cache",
      fetchedAt: cached.fetchedAt,
    }
  }

  try {
    const params = new URLSearchParams({
      tickers: normalizedTickers.join(","),
      period,
    })
    if (includeMetadata) {
      params.set("include_metadata", "true")
    }
    const response = await fetch(apiUrl(`historical-prices?${params}`))

    if (!response.ok) {
      throw new Error(await getErrorMessage(response))
    }

    const data = (await response.json()) as HistoricalPricesResponse
    const fetchedAt = new Date().toISOString()

    await portfolioDb.priceResponses.put({
      cacheKey,
      tickers: normalizedTickers,
      period,
      rows: data.rows,
      metadata: data.metadata,
      fetchedAt,
    })

    return { data, source: "network", fetchedAt }
  } catch (err) {
    if (cached) {
      return {
        data: toResponse(cached),
        source: "stale-cache",
        fetchedAt: cached.fetchedAt,
      }
    }

    throw err
  }
}
