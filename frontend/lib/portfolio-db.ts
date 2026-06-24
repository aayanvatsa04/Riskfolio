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

class RiskfolioDatabase extends Dexie {
  savedPortfolios!: Table<SavedPortfolio, string>

  constructor() {
    super("riskfolio")

    this.version(1).stores({
      savedPortfolios: "id, name, updatedAt, createdAt",
    })
  }
}

export const portfolioDb = new RiskfolioDatabase()
