import type { SupabaseClient } from "@supabase/supabase-js"

import {
  portfolioDb,
  type SavedPortfolio,
  type SavedPortfolioHolding,
} from "@/lib/portfolio-db"

type CloudPortfolioRow = {
  user_id: string
  id: string
  name: string
  holdings: unknown
  confidence_level: number
  horizon: number
  n_simulations: number
  created_at: string
  updated_at: string
}

export type PortfolioSyncResult = {
  uploaded: number
  downloaded: number
  unchanged: number
}

function normalizeHoldings(value: unknown): SavedPortfolioHolding[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .map((holding) => {
      if (!holding || typeof holding !== "object") {
        return null
      }

      const ticker = "ticker" in holding ? String(holding.ticker) : ""
      const quantity =
        "quantity" in holding && typeof holding.quantity === "number"
          ? holding.quantity
          : Number.NaN

      if (!ticker.trim() || !Number.isFinite(quantity) || quantity <= 0) {
        return null
      }

      return {
        ticker: ticker.trim().toUpperCase(),
        quantity,
      }
    })
    .filter((holding): holding is SavedPortfolioHolding => holding !== null)
}

function toCloudRow(portfolio: SavedPortfolio, userId: string) {
  return {
    user_id: userId,
    id: portfolio.id,
    name: portfolio.name,
    holdings: portfolio.holdings,
    confidence_level: portfolio.confidenceLevel,
    horizon: portfolio.horizon,
    n_simulations: portfolio.nSimulations,
    created_at: portfolio.createdAt,
    updated_at: portfolio.updatedAt,
  }
}

function fromCloudRow(row: CloudPortfolioRow): SavedPortfolio {
  return {
    id: row.id,
    name: row.name,
    holdings: normalizeHoldings(row.holdings),
    confidenceLevel: row.confidence_level,
    horizon: row.horizon,
    nSimulations: row.n_simulations,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    lastAccessedAt: row.updated_at,
  }
}

function timestamp(value: string) {
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export async function fetchCloudPortfolios(
  supabase: SupabaseClient,
): Promise<SavedPortfolio[]> {
  const { data, error } = await supabase
    .from("portfolios")
    .select(
      "user_id,id,name,holdings,confidence_level,horizon,n_simulations,created_at,updated_at",
    )
    .order("updated_at", { ascending: false })

  if (error) {
    throw new Error(error.message)
  }

  return ((data ?? []) as CloudPortfolioRow[]).map(fromCloudRow)
}

export async function upsertCloudPortfolio(
  supabase: SupabaseClient,
  userId: string,
  portfolio: SavedPortfolio,
) {
  const { error } = await supabase
    .from("portfolios")
    .upsert(toCloudRow(portfolio, userId), {
      onConflict: "user_id,id",
    })

  if (error) {
    throw new Error(error.message)
  }
}

export async function deleteCloudPortfolio(
  supabase: SupabaseClient,
  portfolioId: string,
) {
  const { error } = await supabase
    .from("portfolios")
    .delete()
    .eq("id", portfolioId)

  if (error) {
    throw new Error(error.message)
  }
}

export async function deleteAllCloudPortfolios(
  supabase: SupabaseClient,
  userId: string,
) {
  const { error } = await supabase
    .from("portfolios")
    .delete()
    .eq("user_id", userId)

  if (error) {
    throw new Error(error.message)
  }
}

export async function mirrorLocalAndCloudPortfolios(
  supabase: SupabaseClient,
  userId: string,
): Promise<PortfolioSyncResult> {
  const [localPortfolios, cloudPortfolios] = await Promise.all([
    portfolioDb.savedPortfolios.toArray(),
    fetchCloudPortfolios(supabase),
  ])

  const localById = new Map(
    localPortfolios.map((portfolio) => [portfolio.id, portfolio]),
  )
  const cloudById = new Map(
    cloudPortfolios.map((portfolio) => [portfolio.id, portfolio]),
  )
  const ids = new Set([...localById.keys(), ...cloudById.keys()])
  const result: PortfolioSyncResult = {
    uploaded: 0,
    downloaded: 0,
    unchanged: 0,
  }

  for (const id of ids) {
    const local = localById.get(id)
    const cloud = cloudById.get(id)

    if (local && !cloud) {
      await upsertCloudPortfolio(supabase, userId, local)
      result.uploaded += 1
      continue
    }

    if (!local && cloud) {
      await portfolioDb.savedPortfolios.put(cloud)
      result.downloaded += 1
      continue
    }

    if (!local || !cloud) {
      continue
    }

    const localUpdatedAt = timestamp(local.updatedAt)
    const cloudUpdatedAt = timestamp(cloud.updatedAt)

    if (localUpdatedAt > cloudUpdatedAt) {
      await upsertCloudPortfolio(supabase, userId, local)
      result.uploaded += 1
    } else if (cloudUpdatedAt > localUpdatedAt) {
      await portfolioDb.savedPortfolios.put({
        ...cloud,
        lastAccessedAt: local.lastAccessedAt,
      })
      result.downloaded += 1
    } else {
      result.unchanged += 1
    }
  }

  return result
}
