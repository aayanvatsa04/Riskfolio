import {
  portfolioDb,
  type CachedPriceResponse,
  type HistoricalPriceRow,
} from "@/lib/portfolio-db"

type ApiErrorDetail = {
  msg?: string
  message?: string
}

export type HistoricalPricesResponse = {
  tickers: string[]
  period: string
  rows: HistoricalPriceRow[]
}

export type HistoricalPricesResult = {
  data: HistoricalPricesResponse
  source: "cache" | "network" | "stale-cache"
  fetchedAt: string
}

const PRICE_CACHE_TTL_MS = 15 * 60 * 1000

function normalizeTickers(tickers: string[]) {
  return Array.from(
    new Set(
      tickers
        .map((ticker) => ticker.trim().toUpperCase())
        .filter((ticker) => ticker.length > 0),
    ),
  ).sort()
}

function getPriceCacheKey(tickers: string[], period: string) {
  return `${period}:${normalizeTickers(tickers).join(",")}`
}

function isFresh(cached: CachedPriceResponse) {
  const fetchedAt = Date.parse(cached.fetchedAt)
  return (
    Number.isFinite(fetchedAt) && Date.now() - fetchedAt < PRICE_CACHE_TTL_MS
  )
}

function toResponse(cached: CachedPriceResponse): HistoricalPricesResponse {
  return {
    tickers: cached.tickers,
    period: cached.period,
    rows: cached.rows,
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
  apiBaseUrl,
  tickers,
  period,
}: {
  apiBaseUrl: string
  tickers: string[]
  period: string
}): Promise<HistoricalPricesResult> {
  const normalizedTickers = normalizeTickers(tickers)
  const cacheKey = getPriceCacheKey(normalizedTickers, period)
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
    const response = await fetch(
      `${apiBaseUrl}/api/v1/historical-prices?${params}`,
    )

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
