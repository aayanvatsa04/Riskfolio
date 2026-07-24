import Dexie, { type Table } from "dexie"

export interface SavedPortfolioHolding {
  ticker: string
  quantity: number
}

export interface SavedPortfolio {
  id: string
  name: string
  holdings: SavedPortfolioHolding[]
  confidenceLevel: number
  horizon: number
  nSimulations: number
  createdAt: string
  updatedAt: string
}

export interface HistoricalPriceRow {
  date: string
  prices: Record<string, number>
}

export interface TickerMetadata {
  name?: string | null
  currency?: string | null
  exchange?: string | null
}

export interface CachedPriceResponse {
  cacheKey: string
  tickers: string[]
  period: string
  rows: HistoricalPriceRow[]
  metadata?: Record<string, TickerMetadata>
  fetchedAt: string
}

export type AnalysisCacheType =
  | "var"
  | "optimize"
  | "stress"
  | "monte-carlo-paths"

export interface CachedAnalysisResponse {
  cacheKey: string
  analysisType: AnalysisCacheType
  response: unknown
  fetchedAt: string
}

class RiskfolioDatabase extends Dexie {
  savedPortfolios!: Table<SavedPortfolio, string>
  priceResponses!: Table<CachedPriceResponse, string>
  analysisResponses!: Table<CachedAnalysisResponse, string>

  constructor() {
    super("riskfolio")

    this.version(1).stores({
      savedPortfolios: "id, name, updatedAt, createdAt",
    })

    this.version(2).stores({
      savedPortfolios: "id, name, updatedAt, createdAt",
      priceResponses: "cacheKey, period, fetchedAt",
    })

    this.version(3).stores({
      savedPortfolios: "id, name, updatedAt, createdAt",
      priceResponses: "cacheKey, period, fetchedAt",
      analysisResponses: "cacheKey, analysisType, fetchedAt",
    })
  }
}

export const portfolioDb = new RiskfolioDatabase()
