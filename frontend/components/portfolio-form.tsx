"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { LoginForm } from "@/components/login-form"
import { useSupabaseAuth } from "@/hooks/use-supabase-auth"
import {
  getAnalysisCacheKey,
  readCachedAnalysisResponse,
  writeCachedAnalysisResponse,
} from "@/lib/analysis-cache"
import { apiUrl } from "@/lib/api"
import {
  deleteCloudPortfolio,
  mirrorLocalAndCloudPortfolios,
  upsertCloudPortfolio,
  type PortfolioSyncResult,
} from "@/lib/cloud-portfolios"
import { fetchHistoricalPricesWithCache } from "@/lib/price-cache"
import { portfolioDb, type SavedPortfolio } from "@/lib/portfolio-db"
import {
  notifyPortfolioListChanged,
  PORTFOLIO_DELETE_EVENT,
  PORTFOLIO_LOAD_EVENT,
  PORTFOLIO_NEW_EVENT,
} from "@/lib/portfolio-events"
import {
  DEFAULT_USER_SETTINGS,
  formatPriceRefreshInterval,
  getPriceRefreshIntervalMs,
  getUserSettings,
  USER_SETTINGS_CHANGED_EVENT,
  type UserSettings,
} from "@/lib/user-settings"
import {
  OptimizerResults,
  type OptimizerResult,
} from "@/components/optimizer-results"
import { MonteCarloSimulationChart } from "@/components/monte-carlo-simulation-chart"
import {
  StressTestResults,
  type StressTestResult,
} from "@/components/stress-test-results"
import {
  Trash2,
  Plus,
  TrendingUp,
  AlertTriangle,
  Loader2,
  Save,
  Cloud,
  LogIn,
  LogOut,
  RefreshCw,
  Info,
  Gauge,
} from "lucide-react"

interface PortfolioEntry {
  id: string
  ticker: string
  companyName?: string | null
  quoteCurrency?: string | null
  exchange?: string | null
  quantity: number
  currentPrice: number | null
  previousClose?: number | null
  priceStatus: "idle" | "loading" | "loaded" | "error"
  priceError?: string
  priceFetchedAt?: string
  priceSource?: "cache" | "network" | "stale-cache"
}

interface PortfolioRequest {
  holdings: {
    ticker: string
    quantity: number
  }[]
  horizon: number
  confidence_level: number
  n_simulations: number
}

interface HoldingValuation {
  ticker: string
  quantity: number
  latest_price: number
  market_value: number
  weight: number
}

interface VaRResult {
  var_amount: number
  var_percentage: number
  cvar_amount: number
  cvar_percentage: number
  mean_pnl: number
  std_pnl: number
  best_case: number
  worst_case: number
  confidence_level: number
  horizon: number
  n_simulations: number
  portfolio_value: number
  holdings: HoldingValuation[]
}

interface ApiErrorDetail {
  msg?: string
  message?: string
}

const DEFAULT_CONFIDENCE_LEVEL = 95
const CONFIDENCE_LEVEL_OPTIONS = [90, 95, 99] as const
const DEFAULT_N_PORTFOLIOS = "5000"
const DEFAULT_RISK_FREE_RATE = 0.05
const AUTOSAVE_DELAY_MS = 900
const STARTER_PORTFOLIO_NAME = "Sample Portfolio"
const STARTER_PORTFOLIO_HOLDINGS = [
  { ticker: "AAPL", quantity: 27 },
  { ticker: "KO", quantity: 108 },
  { ticker: "XOM", quantity: 58 },
  { ticker: "JPM", quantity: 26 },
] as const

function formatCacheTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value))
}

function getSyncMessage(result: PortfolioSyncResult) {
  const changes = [
    result.uploaded ? `${result.uploaded} uploaded` : null,
    result.downloaded ? `${result.downloaded} downloaded` : null,
  ].filter((item): item is string => item !== null)

  return changes.length
    ? `Cloud sync complete: ${changes.join(", ")}.`
    : "Cloud sync is up to date."
}

function getPortfolioSnapshotKey({
  holdings,
  name,
  confidenceLevel,
  horizon,
  nSimulations,
}: {
  holdings: PortfolioRequest["holdings"]
  name: string
  confidenceLevel: number
  horizon: number
  nSimulations: number
}) {
  return JSON.stringify({
    holdings,
    name,
    confidenceLevel,
    horizon,
    nSimulations,
  })
}

function createPortfolioId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID()
  }

  return Date.now().toString()
}

function getDefaultPortfolioName(holdings: PortfolioRequest["holdings"]) {
  const tickers = holdings.map((holding) => holding.ticker).join(", ")
  return tickers ? `${tickers} Portfolio` : "Untitled Portfolio"
}

function normalizeConfidenceLevel(value: number | null | undefined): number {
  const nextValue = Number(value)

  return CONFIDENCE_LEVEL_OPTIONS.some((option) => option === nextValue)
    ? nextValue
    : DEFAULT_CONFIDENCE_LEVEL
}

function createStarterEntries(): PortfolioEntry[] {
  return STARTER_PORTFOLIO_HOLDINGS.map((holding) => ({
    id: `starter-${holding.ticker}`,
    ticker: holding.ticker,
    quantity: holding.quantity,
    currentPrice: null,
    priceStatus: "loading",
  }))
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

function AnalysisPlaceholderCard({
  title,
  description,
  isActive = false,
}: {
  title: string
  description: string
  isActive?: boolean
}) {
  const skeletonClass = isActive ? "" : "animate-none bg-muted/70"

  return (
    <Card className="border-dashed bg-card/70">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-muted-foreground" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Skeleton className={`h-20 w-full ${skeletonClass}`} />
          <Skeleton className={`h-20 w-full ${skeletonClass}`} />
          <Skeleton className={`h-20 w-full ${skeletonClass}`} />
        </div>
        <Skeleton className={`h-56 w-full ${skeletonClass}`} />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Skeleton className={`h-10 w-full ${skeletonClass}`} />
          <Skeleton className={`h-10 w-full ${skeletonClass}`} />
        </div>
      </CardContent>
    </Card>
  )
}

export function PortfolioForm() {
  const router = useRouter()
  const [entries, setEntries] = useState<PortfolioEntry[]>(createStarterEntries)
  const [confidenceLevel, setConfidenceLevel] = useState<number>(
    DEFAULT_CONFIDENCE_LEVEL,
  )
  const [horizon, setHorizon] = useState<number>(5)
  const [nSimulations, setNSimulations] = useState<number>(10000)
  const [nPortfolios, setNPortfolios] = useState<string>(DEFAULT_N_PORTFOLIOS)
  const [isVarLoading, setIsVarLoading] = useState(false)
  const [isOptimizerLoading, setIsOptimizerLoading] = useState(false)
  const [result, setResult] = useState<VaRResult | null>(null)
  const [optimizerResult, setOptimizerResult] =
    useState<OptimizerResult | null>(null)
  const [stressResult, setStressResult] = useState<StressTestResult | null>(
    null,
  )
  const [stressResultCacheKey, setStressResultCacheKey] = useState<
    string | null
  >(null)
  const [varError, setVarError] = useState<string | null>(null)
  const [optimizerError, setOptimizerError] = useState<string | null>(null)
  const [stressError, setStressError] = useState<string | null>(null)
  const [isStressLoading, setIsStressLoading] = useState(false)
  const [stressPriceShocks, setStressPriceShocks] = useState<
    Record<string, number>
  >({})
  const [stressVolatilityPercent, setStressVolatilityPercent] = useState(100)
  const [error, setError] = useState<string | null>(null)
  const [savedPortfolios, setSavedPortfolios] = useState<SavedPortfolio[]>([])
  const [hasCachedPortfolios, setHasCachedPortfolios] = useState<
    boolean | null
  >(null)
  const [
    isPortfolioInitializationComplete,
    setIsPortfolioInitializationComplete,
  ] = useState(false)
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(
    null,
  )
  const [portfolioName, setPortfolioName] = useState(STARTER_PORTFOLIO_NAME)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isAutosaving, setIsAutosaving] = useState(false)
  const [userSettings, setUserSettings] = useState<UserSettings>(
    DEFAULT_USER_SETTINGS,
  )
  const {
    supabase,
    user,
    isConfigured: isSupabaseConfigured,
    isLoading: isAuthLoading,
    signInWithGoogle,
    signOut,
  } = useSupabaseAuth()
  const [authError, setAuthError] = useState<string | null>(null)
  const [syncStatus, setSyncStatus] = useState<string | null>(null)
  const [isSyncing, setIsSyncing] = useState(false)
  const [isSigningIn, setIsSigningIn] = useState(false)
  const syncedUserIdRef = useRef<string | null>(null)
  const loadPortfolioRef = useRef<(portfolioId: string) => Promise<void>>(
    async () => {},
  )
  const newPortfolioRef = useRef<() => void>(() => {})
  const deletePortfolioRef = useRef<(portfolioId: string) => Promise<void>>(
    async () => {},
  )
  const lastAutosaveKeyRef = useRef<string | null>(null)
  const hasSeededStarterPortfolioRef = useRef(false)

  const createBlankEntry = (): PortfolioEntry => ({
    id: Date.now().toString(),
    ticker: "",
    quantity: 0,
    currentPrice: null,
    priceStatus: "idle",
  })

  const refreshSavedPortfolios = useCallback(async () => {
    const portfolios = await portfolioDb.savedPortfolios
      .orderBy("lastAccessedAt")
      .reverse()
      .toArray()

    setSavedPortfolios(portfolios)
    notifyPortfolioListChanged()
  }, [])

  useEffect(() => {
    void refreshSavedPortfolios()
  }, [refreshSavedPortfolios])

  useEffect(() => {
    const refreshSettings = () => {
      setUserSettings(getUserSettings())
    }

    refreshSettings()
    window.addEventListener(USER_SETTINGS_CHANGED_EVENT, refreshSettings)

    return () => {
      window.removeEventListener(USER_SETTINGS_CHANGED_EVENT, refreshSettings)
    }
  }, [])

  useEffect(() => {
    const nextConfidenceLevel = normalizeConfidenceLevel(confidenceLevel)

    if (nextConfidenceLevel !== confidenceLevel) {
      setConfidenceLevel(nextConfidenceLevel)
    }
  }, [confidenceLevel])

  const syncPortfolios = useCallback(async () => {
    if (!supabase || !user) {
      return
    }

    setIsSyncing(true)
    setSyncStatus("Syncing cloud portfolios...")
    setAuthError(null)

    try {
      const syncResult = await mirrorLocalAndCloudPortfolios(supabase, user.id)
      await refreshSavedPortfolios()
      setSyncStatus(getSyncMessage(syncResult))
    } catch (err) {
      setSyncStatus(null)
      setAuthError(
        err instanceof Error ? err.message : "Failed to sync portfolios.",
      )
      syncedUserIdRef.current = null
    } finally {
      setIsSyncing(false)
    }
  }, [refreshSavedPortfolios, supabase, user])

  useEffect(() => {
    if (!supabase || !user) {
      syncedUserIdRef.current = null
      return
    }

    if (syncedUserIdRef.current === user.id) {
      return
    }

    syncedUserIdRef.current = user.id
    void syncPortfolios()
  }, [supabase, syncPortfolios, user])

  useEffect(() => {
    if (user) {
      setIsSigningIn(false)
    }
  }, [user])

  const handleGoogleSignIn = async () => {
    setAuthError(null)

    if (!isSupabaseConfigured) {
      setAuthError("Supabase is not configured for this environment.")
      return
    }

    setIsSigningIn(true)
    const nextError = await signInWithGoogle()

    if (nextError) {
      setAuthError(nextError)
      setIsSigningIn(false)
    }
  }

  const handleSignOut = async () => {
    setAuthError(null)
    setSyncStatus(null)
    const nextError = await signOut()

    if (nextError) {
      setAuthError(nextError)
    }
  }

  const addEntry = () => {
    setResult(null)
    setOptimizerResult(null)
    setStressResult(null)
    setStressResultCacheKey(null)
    setVarError(null)
    setOptimizerError(null)
    setStressError(null)
    setError(null)
    setEntries([...entries, createBlankEntry()])
  }

  const removeEntry = (id: string) => {
    if (entries.length > 1) {
      setResult(null)
      setOptimizerResult(null)
      setStressResult(null)
      setStressResultCacheKey(null)
      setVarError(null)
      setOptimizerError(null)
      setStressError(null)
      setError(null)
      setEntries(entries.filter((entry) => entry.id !== id))
    }
  }

  const updateEntry = (
    id: string,
    field: keyof PortfolioEntry,
    value: string | number | null,
  ) => {
    setResult(null)
    setOptimizerResult(null)
    setStressResult(null)
    setStressResultCacheKey(null)
    setVarError(null)
    setOptimizerError(null)
    setStressError(null)
    setError(null)
    setEntries(
      entries.map((entry) =>
        entry.id === id ? { ...entry, [field]: value } : entry,
      ),
    )
  }

  const updateTicker = (id: string, ticker: string) => {
    setResult(null)
    setOptimizerResult(null)
    setStressResult(null)
    setStressResultCacheKey(null)
    setVarError(null)
    setOptimizerError(null)
    setStressError(null)
    setStressPriceShocks({})
    setStressVolatilityPercent(100)
    setError(null)
    setEntries(
      entries.map((entry) =>
        entry.id === id
          ? {
              ...entry,
              ticker,
              companyName: null,
              quoteCurrency: null,
              exchange: null,
              currentPrice: null,
              priceStatus: ticker.trim() ? "loading" : "idle",
              priceError: undefined,
              priceFetchedAt: undefined,
              priceSource: undefined,
              previousClose: null,
            }
          : entry,
      ),
    )
  }

  const priceRefreshIntervalMs = getPriceRefreshIntervalMs(userSettings)
  const priceRefreshIntervalLabel = formatPriceRefreshInterval(
    userSettings.priceRefreshIntervalMinutes,
  )

  useEffect(() => {
    const now = Date.now()
    const timers = entries
      .map((entry) => {
        const ticker = entry.ticker.toUpperCase().trim()
        const fetchedAtMs = entry.priceFetchedAt
          ? Date.parse(entry.priceFetchedAt)
          : Number.NaN
        const priceAgeMs = Number.isFinite(fetchedAtMs)
          ? now - fetchedAtMs
          : null
        const hasFreshPrice =
          entry.currentPrice !== null &&
          priceAgeMs !== null &&
          priceAgeMs >= 0 &&
          priceAgeMs < priceRefreshIntervalMs

        if (!ticker || entry.priceStatus === "error") {
          return null
        }

        const refreshDelay =
          hasFreshPrice && priceAgeMs !== null
            ? Math.max(priceRefreshIntervalMs - priceAgeMs + 250, 1000)
            : 500

        return window.setTimeout(() => {
          void (async () => {
            try {
              const priceResult = await fetchHistoricalPricesWithCache({
                tickers: [ticker],
                period: "5d",
                includeMetadata: true,
              })
              const latestRow = priceResult.data.rows?.at(-1)
              const previousRow = priceResult.data.rows
                ?.slice(0, -1)
                .reverse()
                .find(
                  (row) =>
                    typeof row.prices?.[ticker] === "number" &&
                    Number.isFinite(row.prices[ticker]),
                )
              const latestPrice = latestRow?.prices?.[ticker]
              const previousClose = previousRow?.prices?.[ticker]
              const metadata = priceResult.data.metadata?.[ticker]

              if (
                typeof latestPrice !== "number" ||
                !Number.isFinite(latestPrice)
              ) {
                throw new Error(`No current price found for ${ticker}`)
              }

              setEntries((currentEntries) =>
                currentEntries.map((currentEntry) =>
                  currentEntry.id === entry.id &&
                  currentEntry.ticker.toUpperCase().trim() === ticker
                    ? {
                        ...currentEntry,
                        companyName: metadata?.name ?? null,
                        quoteCurrency: metadata?.currency ?? null,
                        exchange: metadata?.exchange ?? null,
                        currentPrice: latestPrice,
                        previousClose:
                          typeof previousClose === "number" &&
                          Number.isFinite(previousClose)
                            ? previousClose
                            : null,
                        priceStatus: "loaded",
                        priceError: undefined,
                        priceFetchedAt:
                          priceResult.source === "stale-cache"
                            ? new Date().toISOString()
                            : priceResult.fetchedAt,
                        priceSource: priceResult.source,
                      }
                    : currentEntry,
                ),
              )
            } catch (err) {
              setEntries((currentEntries) =>
                currentEntries.map((currentEntry) =>
                  currentEntry.id === entry.id &&
                  currentEntry.ticker.toUpperCase().trim() === ticker
                    ? {
                        ...currentEntry,
                        companyName: null,
                        quoteCurrency: null,
                        exchange: null,
                        currentPrice: null,
                        previousClose: null,
                        priceStatus: "error",
                        priceError:
                          err instanceof Error
                            ? err.message
                            : "Failed to fetch price",
                        priceFetchedAt: undefined,
                        priceSource: undefined,
                      }
                    : currentEntry,
                ),
              )
            }
          })()
        }, refreshDelay)
      })
      .filter((timer): timer is number => timer !== null)

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [entries, priceRefreshIntervalMs])

  const buildHoldingsRequest = (): PortfolioRequest["holdings"] | null => {
    const validEntries = entries.filter(
      (entry) => entry.ticker.trim() !== "" && entry.quantity > 0,
    )

    if (validEntries.length === 0) {
      return null
    }

    return validEntries.map((entry) => ({
      ticker: entry.ticker.toUpperCase().trim(),
      quantity: entry.quantity,
    }))
  }

  const getEntriesFromPortfolio = (
    portfolio: SavedPortfolio,
  ): PortfolioEntry[] => {
    if (portfolio.holdings.length === 0) {
      return [createBlankEntry()]
    }

    return portfolio.holdings.map((holding, index) => ({
      id: `${portfolio.id}-${index}`,
      ticker: holding.ticker,
      quantity: holding.quantity,
      currentPrice: null,
      priceStatus: holding.ticker ? "loading" : "idle",
    }))
  }

  const handleSavePortfolio = async () => {
    const holdings = buildHoldingsRequest()
    if (!holdings) {
      setSaveStatus("Add at least one ticker and quantity before saving.")
      return
    }

    setIsSaving(true)
    setSaveStatus(null)

    try {
      const now = new Date().toISOString()
      const existingPortfolio = selectedPortfolioId
        ? await portfolioDb.savedPortfolios.get(selectedPortfolioId)
        : null
      const portfolio: SavedPortfolio = {
        id: existingPortfolio?.id ?? createPortfolioId(),
        name: portfolioName.trim() || getDefaultPortfolioName(holdings),
        holdings,
        confidenceLevel,
        horizon,
        nSimulations,
        createdAt: existingPortfolio?.createdAt ?? now,
        updatedAt: now,
        lastAccessedAt: now,
      }

      await portfolioDb.savedPortfolios.put(portfolio)
      setSelectedPortfolioId(portfolio.id)
      setPortfolioName(portfolio.name)
      router.replace(`/?portfolio=${encodeURIComponent(portfolio.id)}`)
      lastAutosaveKeyRef.current = getPortfolioSnapshotKey({
        holdings,
        name: portfolio.name,
        confidenceLevel,
        horizon,
        nSimulations,
      })

      if (supabase && user) {
        try {
          await upsertCloudPortfolio(supabase, user.id, portfolio)
          setSaveStatus("Portfolio saved locally and synced to cloud.")
          setSyncStatus("Cloud sync is up to date.")
        } catch (err) {
          setSaveStatus("Portfolio saved locally. Cloud sync failed.")
          setAuthError(
            err instanceof Error ? err.message : "Failed to sync portfolio.",
          )
        }
      } else {
        setSaveStatus("Portfolio saved locally.")
      }

      await refreshSavedPortfolios()
    } catch (err) {
      setSaveStatus(
        err instanceof Error ? err.message : "Failed to save portfolio.",
      )
    } finally {
      setIsSaving(false)
    }
  }

  const handleLoadPortfolio = async (portfolioId: string) => {
    const portfolio = await portfolioDb.savedPortfolios.get(portfolioId)
    if (!portfolio) {
      setSaveStatus("Saved portfolio not found.")
      await refreshSavedPortfolios()
      return
    }

    const lastAccessedAt = new Date().toISOString()
    await portfolioDb.savedPortfolios.update(portfolio.id, {
      lastAccessedAt,
    })
    setSelectedPortfolioId(portfolio.id)
    setPortfolioName(portfolio.name)
    setEntries(getEntriesFromPortfolio(portfolio))
    const nextConfidenceLevel = normalizeConfidenceLevel(
      portfolio.confidenceLevel,
    )
    setConfidenceLevel(nextConfidenceLevel)
    setHorizon(portfolio.horizon)
    setNSimulations(portfolio.nSimulations)
    lastAutosaveKeyRef.current = getPortfolioSnapshotKey({
      holdings: portfolio.holdings,
      name: portfolio.name,
      confidenceLevel: nextConfidenceLevel,
      horizon: portfolio.horizon,
      nSimulations: portfolio.nSimulations,
    })
    setResult(null)
    setOptimizerResult(null)
    setStressResult(null)
    setStressResultCacheKey(null)
    setVarError(null)
    setOptimizerError(null)
    setStressError(null)
    setStressPriceShocks({})
    setStressVolatilityPercent(100)
    setError(null)
    setSaveStatus(`Loaded`)
    router.replace(`/?portfolio=${encodeURIComponent(portfolio.id)}`)
    await refreshSavedPortfolios()
  }

  loadPortfolioRef.current = handleLoadPortfolio

  const clearWorkingPortfolio = () => {
    setSelectedPortfolioId(null)
    setPortfolioName("")
    lastAutosaveKeyRef.current = null
    setEntries([createBlankEntry()])
    setResult(null)
    setOptimizerResult(null)
    setStressResult(null)
    setStressResultCacheKey(null)
    setVarError(null)
    setOptimizerError(null)
    setStressError(null)
    setStressPriceShocks({})
    setStressVolatilityPercent(100)
    setError(null)
  }

  const deletePortfolioById = async (portfolioId: string) => {
    await portfolioDb.savedPortfolios.delete(portfolioId)

    if (supabase && user) {
      try {
        await deleteCloudPortfolio(supabase, portfolioId)
        setSyncStatus("Cloud copy deleted.")
      } catch (err) {
        setAuthError(
          err instanceof Error
            ? err.message
            : "Failed to delete the cloud copy.",
        )
      }
    }

    if (selectedPortfolioId === portfolioId) {
      clearWorkingPortfolio()
    }

    setSaveStatus("Saved portfolio deleted.")
    await refreshSavedPortfolios()
  }

  const handleDeletePortfolio = async () => {
    if (!selectedPortfolioId) {
      return
    }

    await deletePortfolioById(selectedPortfolioId)
  }

  const handleNewPortfolio = () => {
    clearWorkingPortfolio()
    setSaveStatus(null)
    router.replace("/")
  }

  newPortfolioRef.current = handleNewPortfolio
  deletePortfolioRef.current = deletePortfolioById

  useEffect(() => {
    const handleSidebarPortfolioLoad = (event: Event) => {
      const portfolioId = (event as CustomEvent<{ portfolioId?: string }>)
        .detail?.portfolioId

      if (portfolioId) {
        void loadPortfolioRef.current(portfolioId)
      }
    }

    const handleSidebarPortfolioNew = () => {
      newPortfolioRef.current()
    }

    const handleSidebarPortfolioDelete = (event: Event) => {
      const portfolioId = (event as CustomEvent<{ portfolioId?: string }>)
        .detail?.portfolioId

      if (portfolioId) {
        void deletePortfolioRef.current(portfolioId)
      }
    }

    window.addEventListener(PORTFOLIO_LOAD_EVENT, handleSidebarPortfolioLoad)
    window.addEventListener(PORTFOLIO_NEW_EVENT, handleSidebarPortfolioNew)
    window.addEventListener(
      PORTFOLIO_DELETE_EVENT,
      handleSidebarPortfolioDelete,
    )

    let cancelled = false

    void (async () => {
      try {
        const initialPortfolioId = new URLSearchParams(
          window.location.search,
        ).get("portfolio")
        const requestedPortfolio = initialPortfolioId
          ? await portfolioDb.savedPortfolios.get(initialPortfolioId)
          : null
        const portfolio =
          requestedPortfolio ??
          (await portfolioDb.savedPortfolios.orderBy("lastAccessedAt").last())

        if (cancelled) {
          return
        }

        if (portfolio) {
          setHasCachedPortfolios(true)
          await loadPortfolioRef.current(portfolio.id)
        } else {
          setHasCachedPortfolios(false)
        }
      } catch {
        if (!cancelled) {
          // Avoid creating a duplicate if IndexedDB cannot be inspected.
          setHasCachedPortfolios(true)
          setSaveStatus("Unable to load cached portfolios.")
        }
      } finally {
        if (!cancelled) {
          setIsPortfolioInitializationComplete(true)
        }
      }
    })()

    return () => {
      cancelled = true
      window.removeEventListener(
        PORTFOLIO_LOAD_EVENT,
        handleSidebarPortfolioLoad,
      )
      window.removeEventListener(PORTFOLIO_NEW_EVENT, handleSidebarPortfolioNew)
      window.removeEventListener(
        PORTFOLIO_DELETE_EVENT,
        handleSidebarPortfolioDelete,
      )
    }
  }, [])

  const autosaveSnapshot = useMemo(() => {
    const holdings = entries
      .filter((entry) => entry.ticker.trim() !== "" && entry.quantity > 0)
      .map((entry) => ({
        ticker: entry.ticker.toUpperCase().trim(),
        quantity: entry.quantity,
      }))

    if (holdings.length === 0) {
      return null
    }

    const name = portfolioName.trim() || getDefaultPortfolioName(holdings)
    const key = getPortfolioSnapshotKey({
      holdings,
      name,
      confidenceLevel,
      horizon,
      nSimulations,
    })

    return {
      holdings,
      name,
      key,
    }
  }, [confidenceLevel, entries, horizon, nSimulations, portfolioName])

  useEffect(() => {
    if (!isPortfolioInitializationComplete || !autosaveSnapshot) {
      return
    }

    if (lastAutosaveKeyRef.current === autosaveSnapshot.key) {
      return
    }

    const timer = window.setTimeout(() => {
      void (async () => {
        setIsAutosaving(true)

        try {
          const now = new Date().toISOString()
          const existingPortfolio = selectedPortfolioId
            ? await portfolioDb.savedPortfolios.get(selectedPortfolioId)
            : null
          const portfolio: SavedPortfolio = {
            id:
              existingPortfolio?.id ??
              selectedPortfolioId ??
              createPortfolioId(),
            name: autosaveSnapshot.name,
            holdings: autosaveSnapshot.holdings,
            confidenceLevel,
            horizon,
            nSimulations,
            createdAt: existingPortfolio?.createdAt ?? now,
            updatedAt: now,
            lastAccessedAt: existingPortfolio?.lastAccessedAt ?? now,
          }

          await portfolioDb.savedPortfolios.put(portfolio)
          lastAutosaveKeyRef.current = autosaveSnapshot.key
          setSelectedPortfolioId((current) => current ?? portfolio.id)
          if (!selectedPortfolioId) {
            router.replace(`/?portfolio=${encodeURIComponent(portfolio.id)}`)
          }

          if (!portfolioName.trim()) {
            setPortfolioName(portfolio.name)
          }

          if (supabase && user) {
            try {
              await upsertCloudPortfolio(supabase, user.id, portfolio)
              setSyncStatus("Autosave synced to cloud.")
            } catch (err) {
              setAuthError(
                err instanceof Error
                  ? err.message
                  : "Autosave cloud sync failed.",
              )
            }
          }

          await refreshSavedPortfolios()
          setSaveStatus(`Autosaved`)
        } catch (err) {
          setSaveStatus(err instanceof Error ? err.message : "Autosave failed.")
        } finally {
          setIsAutosaving(false)
        }
      })()
    }, AUTOSAVE_DELAY_MS)

    return () => {
      window.clearTimeout(timer)
    }
  }, [
    autosaveSnapshot,
    confidenceLevel,
    horizon,
    isPortfolioInitializationComplete,
    nSimulations,
    portfolioName,
    refreshSavedPortfolios,
    router,
    selectedPortfolioId,
    supabase,
    user,
  ])

  const buildStressTestRequest = useCallback(
    (holdings: PortfolioRequest["holdings"]) => {
      const priceShocks = holdings.reduce<Record<string, number>>(
        (acc, holding) => {
          const shockPercent = stressPriceShocks[holding.ticker] ?? 0
          if (shockPercent !== 0) {
            acc[holding.ticker] = shockPercent / 100
          }
          return acc
        },
        {},
      )

      return {
        holdings,
        price_shocks: priceShocks,
        volatility_multiplier: stressVolatilityPercent / 100,
        horizon,
        confidence_level: confidenceLevel / 100,
        n_simulations: nSimulations,
      }
    },
    [
      confidenceLevel,
      horizon,
      nSimulations,
      stressPriceShocks,
      stressVolatilityPercent,
    ],
  )

  const runVarAnalysis = useCallback(
    async (holdings: PortfolioRequest["holdings"]) => {
      const request: PortfolioRequest = {
        holdings,
        horizon,
        confidence_level: confidenceLevel / 100,
        n_simulations: nSimulations,
      }

      setIsVarLoading(true)
      setVarError(null)

      try {
        const response = await fetch(apiUrl("analyze"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(request),
        })

        if (!response.ok) {
          throw new Error(await getErrorMessage(response))
        }

        const data = await response.json()
        const portfolioValue = data.portfolio_value ?? 0
        const varAmount =
          data.var_positive ??
          Math.abs(data.var ?? data.var_amount ?? data.VaR ?? 0)
        const cvarAmount = data.cvar_positive ?? Math.abs(data.cvar ?? 0)
        const nextResult = {
          var_amount: varAmount,
          var_percentage:
            data.var_percentage ??
            (portfolioValue > 0 ? (varAmount / portfolioValue) * 100 : 0),
          cvar_amount: cvarAmount,
          cvar_percentage:
            data.cvar_percentage ??
            (portfolioValue > 0 ? (cvarAmount / portfolioValue) * 100 : 0),
          mean_pnl: data.mean_pnl ?? 0,
          std_pnl: data.std_pnl ?? 0,
          best_case: data.best_case ?? 0,
          worst_case: data.worst_case ?? 0,
          confidence_level: confidenceLevel,
          horizon,
          n_simulations: data.n_simulations ?? nSimulations,
          portfolio_value: portfolioValue,
          holdings: data.holdings ?? [],
        }

        await writeCachedAnalysisResponse("var", request, nextResult)
        setResult(nextResult)
      } catch (err) {
        setVarError(
          err instanceof Error ? err.message : "Failed to analyze portfolio.",
        )
      } finally {
        setIsVarLoading(false)
      }
    },
    [confidenceLevel, horizon, nSimulations],
  )

  const runOptimization = useCallback(
    async (holdings: PortfolioRequest["holdings"]) => {
      if (holdings.length < 2) {
        setOptimizerResult(null)
        setOptimizerError(
          "Add at least two distinct tickers to run the optimizer.",
        )
        return
      }

      const request = {
        holdings,
        n_portfolios: parseInt(nPortfolios, 10),
        risk_free_rate: DEFAULT_RISK_FREE_RATE,
      }

      setIsOptimizerLoading(true)
      setOptimizerError(null)

      try {
        const response = await fetch(apiUrl("optimize"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(request),
        })

        if (!response.ok) {
          throw new Error(await getErrorMessage(response))
        }

        const data = (await response.json()) as OptimizerResult
        await writeCachedAnalysisResponse("optimize", request, data)
        setOptimizerResult(data)
      } catch (err) {
        setOptimizerError(
          err instanceof Error ? err.message : "Failed to optimize portfolio.",
        )
      } finally {
        setIsOptimizerLoading(false)
      }
    },
    [nPortfolios],
  )

  const runStressTest = useCallback(
    async (holdings: PortfolioRequest["holdings"]) => {
      const request = buildStressTestRequest(holdings)
      const requestKey = getAnalysisCacheKey("stress", request)

      setIsStressLoading(true)
      setStressError(null)

      try {
        const response = await fetch(apiUrl("stress-test"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(request),
        })

        if (!response.ok) {
          throw new Error(await getErrorMessage(response))
        }

        const data = (await response.json()) as StressTestResult
        await writeCachedAnalysisResponse("stress", request, data)
        setStressResult(data)
        setStressResultCacheKey(requestKey)
      } catch (err) {
        setStressError(
          err instanceof Error ? err.message : "Failed to run stress test.",
        )
      } finally {
        setIsStressLoading(false)
      }
    },
    [buildStressTestRequest],
  )

  const runAllAnalyses = useCallback(
    async (holdings: PortfolioRequest["holdings"] | null) => {
      setError(null)

      if (!holdings) {
        setError(
          "Please add at least one valid portfolio entry with a ticker and quantity.",
        )
        return
      }

      await Promise.all([
        runVarAnalysis(holdings),
        runStressTest(holdings),
        runOptimization(holdings),
      ])
    },
    [runOptimization, runStressTest, runVarAnalysis],
  )

  const getValidatedHoldings = () => {
    const holdings = buildHoldingsRequest()
    setError(null)

    if (!holdings) {
      setError(
        "Please add at least one valid portfolio entry with a ticker and quantity.",
      )
      return null
    }

    return holdings
  }

  const handleRunVarAnalysis = async () => {
    const holdings = getValidatedHoldings()

    if (!holdings) {
      return
    }

    await runVarAnalysis(holdings)
  }

  const handleRunStressTest = async () => {
    const holdings = getValidatedHoldings()

    if (!holdings) {
      return
    }

    await runStressTest(holdings)
  }

  const handleRunOptimization = async () => {
    const holdings = getValidatedHoldings()

    if (!holdings) {
      return
    }

    await runOptimization(holdings)
  }

  const handleSubmit = async (e: React.SubmitEvent) => {
    e.preventDefault()
    await runAllAnalyses(buildHoldingsRequest())
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(value)
  }

  const formatSignedCurrency = (value: number) => {
    const absoluteValue = formatCurrency(Math.abs(value))

    if (value > 0) {
      return `+${absoluteValue}`
    }

    if (value < 0) {
      return `-${absoluteValue}`
    }

    return absoluteValue
  }

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(2)}%`
  }

  const formatSignedPercent = (value: number) => {
    const absoluteValue = `${Math.abs(value * 100).toFixed(2)}%`

    if (value > 0) {
      return `+${absoluteValue}`
    }

    if (value < 0) {
      return `-${absoluteValue}`
    }

    return absoluteValue
  }

  const getHorizonLabel = (days: number) => {
    if (days === 1) {
      return "1 day"
    }

    if (days === 5) {
      return "1 week"
    }

    if (days === 22) {
      return "1 month"
    }

    return `${days} trading days`
  }

  const totalQuantity = entries.reduce(
    (sum, entry) => sum + (entry.quantity || 0),
    0,
  )

  const estimatedPortfolioValue = entries.reduce(
    (sum, entry) =>
      sum +
      (entry.currentPrice !== null ? entry.currentPrice * entry.quantity : 0),
    0,
  )

  const entryWeightEstimates = useMemo(() => {
    return new Map(
      entries.map((entry) => {
        const marketValue =
          entry.currentPrice !== null ? entry.currentPrice * entry.quantity : 0
        const weight =
          estimatedPortfolioValue > 0 && marketValue > 0
            ? marketValue / estimatedPortfolioValue
            : null

        return [entry.id, weight] as const
      }),
    )
  }, [entries, estimatedPortfolioValue])

  const getEntryWeightLabel = (entryId: string) => {
    const weight = entryWeightEstimates.get(entryId)
    return typeof weight === "number" ? formatPercent(weight) : "-"
  }

  const getEntryMarketValue = (entry: PortfolioEntry) => {
    if (entry.currentPrice === null || entry.quantity <= 0) {
      return null
    }

    return entry.currentPrice * entry.quantity
  }

  const getEntryDayChange = (entry: PortfolioEntry) => {
    if (
      entry.currentPrice === null ||
      !entry.previousClose ||
      entry.previousClose <= 0
    ) {
      return null
    }

    const priceChange = entry.currentPrice - entry.previousClose

    return {
      amount: priceChange,
      percent: priceChange / entry.previousClose,
      pnl: priceChange * entry.quantity,
    }
  }

  const getEntryPriceStatus = (entry: PortfolioEntry) => {
    if (entry.priceStatus === "loading") {
      return {
        label: "Fetching",
        tone: "muted",
        title: `Fetching latest USD quote. Prices refresh every ${priceRefreshIntervalLabel}.`,
      }
    }

    if (entry.priceStatus === "error") {
      return {
        label: "Invalid",
        tone: "error",
        title: entry.priceError ?? "Failed to fetch price.",
      }
    }

    if (
      entry.priceStatus === "loaded" &&
      entry.priceFetchedAt &&
      entry.priceSource
    ) {
      const source =
        entry.priceSource === "network"
          ? "Updated"
          : entry.priceSource === "cache"
            ? "Cached"
            : "Stale cache"

      return {
        label: source,
        tone: "muted",
        title: `${source} ${formatCacheTimestamp(entry.priceFetchedAt)}. Prices refresh every ${priceRefreshIntervalLabel}.`,
      }
    }

    return {
      label: entry.ticker.trim() ? "Pending" : "Empty",
      tone: "subtle",
      title: "Enter a ticker to fetch a USD quote.",
    }
  }

  const stressHoldingsKey = useMemo(() => {
    return JSON.stringify(
      entries
        .filter((entry) => entry.ticker.trim() !== "" && entry.quantity > 0)
        .map((entry) => ({
          ticker: entry.ticker.toUpperCase().trim(),
          quantity: entry.quantity,
        })),
    )
  }, [entries])

  const stressHoldings = useMemo(
    () => JSON.parse(stressHoldingsKey) as PortfolioRequest["holdings"],
    [stressHoldingsKey],
  )

  const cachedVarRequest = useMemo<PortfolioRequest | null>(() => {
    if (stressHoldings.length === 0) {
      return null
    }

    return {
      holdings: stressHoldings,
      horizon,
      confidence_level: confidenceLevel / 100,
      n_simulations: nSimulations,
    }
  }, [confidenceLevel, horizon, nSimulations, stressHoldings])

  const cachedOptimizerRequest = useMemo(() => {
    if (stressHoldings.length < 2) {
      return null
    }

    return {
      holdings: stressHoldings,
      n_portfolios: parseInt(nPortfolios, 10),
      risk_free_rate: DEFAULT_RISK_FREE_RATE,
    }
  }, [nPortfolios, stressHoldings])

  const cachedStressRequest = useMemo(() => {
    if (stressHoldings.length === 0) {
      return null
    }

    return buildStressTestRequest(stressHoldings)
  }, [buildStressTestRequest, stressHoldings])

  const cachedStressRequestKey = cachedStressRequest
    ? getAnalysisCacheKey("stress", cachedStressRequest)
    : null

  const updateStressPriceShock = (ticker: string, value: number) => {
    setStressPriceShocks((current) => ({
      ...current,
      [ticker]: value,
    }))
  }

  useEffect(() => {
    if (!cachedVarRequest) {
      setResult(null)
      return
    }

    let cancelled = false

    void readCachedAnalysisResponse<VaRResult>("var", cachedVarRequest).then(
      (cached) => {
        if (!cancelled) {
          setResult(cached?.response ?? null)
          if (cached) {
            setVarError(null)
          }
        }
      },
    )

    return () => {
      cancelled = true
    }
  }, [cachedVarRequest])

  useEffect(() => {
    if (!cachedOptimizerRequest) {
      setOptimizerResult(null)
      return
    }

    let cancelled = false

    void readCachedAnalysisResponse<OptimizerResult>(
      "optimize",
      cachedOptimizerRequest,
    ).then((cached) => {
      if (!cancelled) {
        setOptimizerResult(cached?.response ?? null)
        if (cached) {
          setOptimizerError(null)
        }
      }
    })

    return () => {
      cancelled = true
    }
  }, [cachedOptimizerRequest])

  useEffect(() => {
    if (!cachedStressRequest) {
      setStressResult(null)
      setStressResultCacheKey(null)
      setStressError(null)
      return
    }

    let cancelled = false

    void readCachedAnalysisResponse<StressTestResult>(
      "stress",
      cachedStressRequest,
    ).then((cached) => {
      if (cancelled || !cached) {
        return
      }

      setStressResult(cached.response)
      setStressResultCacheKey(cachedStressRequestKey)
      setStressError(null)
    })

    return () => {
      cancelled = true
    }
  }, [cachedStressRequest, cachedStressRequestKey])

  const isStressResultStale =
    Boolean(stressResult) &&
    Boolean(cachedStressRequestKey) &&
    stressResultCacheKey !== cachedStressRequestKey

  useEffect(() => {
    if (stressHoldings.length > 0) {
      return
    }

    setStressResult(null)
    setStressResultCacheKey(null)
    setStressError(null)
  }, [stressHoldings.length])

  useEffect(() => {
    if (
      hasSeededStarterPortfolioRef.current ||
      !isPortfolioInitializationComplete ||
      hasCachedPortfolios !== false ||
      selectedPortfolioId
    ) {
      return
    }

    const starterHoldings = STARTER_PORTFOLIO_HOLDINGS.map((holding) => ({
      ticker: holding.ticker,
      quantity: holding.quantity,
    }))

    hasSeededStarterPortfolioRef.current = true
    const now = new Date().toISOString()
    const starterPortfolio: SavedPortfolio = {
      id: createPortfolioId(),
      name: STARTER_PORTFOLIO_NAME,
      holdings: starterHoldings,
      confidenceLevel,
      horizon,
      nSimulations,
      createdAt: now,
      updatedAt: now,
      lastAccessedAt: now,
    }
    lastAutosaveKeyRef.current = getPortfolioSnapshotKey({
      holdings: starterPortfolio.holdings,
      name: starterPortfolio.name,
      confidenceLevel: starterPortfolio.confidenceLevel,
      horizon: starterPortfolio.horizon,
      nSimulations: starterPortfolio.nSimulations,
    })
    setSelectedPortfolioId(starterPortfolio.id)
    setPortfolioName(STARTER_PORTFOLIO_NAME)
    setSaveStatus("Saving Sample Portfolio...")
    void portfolioDb.savedPortfolios
      .put(starterPortfolio)
      .then(async () => {
        setHasCachedPortfolios(true)

        if (supabase && user) {
          try {
            await upsertCloudPortfolio(supabase, user.id, starterPortfolio)
            setSyncStatus("Sample Portfolio synced to cloud.")
          } catch (syncError) {
            setAuthError(
              syncError instanceof Error
                ? syncError.message
                : "Failed to sync Sample Portfolio.",
            )
          }
        }

        await refreshSavedPortfolios()
        router.replace(`/?portfolio=${encodeURIComponent(starterPortfolio.id)}`)
        setSaveStatus("Saved Sample Portfolio.")
      })
      .catch((saveError) => {
        lastAutosaveKeyRef.current = null
        setSelectedPortfolioId((current) =>
          current === starterPortfolio.id ? null : current,
        )
        setSaveStatus(
          saveError instanceof Error
            ? saveError.message
            : "Failed to save Sample Portfolio.",
        )
      })
    void runAllAnalyses(starterHoldings)
  }, [
    confidenceLevel,
    hasCachedPortfolios,
    horizon,
    isPortfolioInitializationComplete,
    nSimulations,
    refreshSavedPortfolios,
    router,
    runAllAnalyses,
    selectedPortfolioId,
    supabase,
    user,
  ])

  const isAnyAnalysisLoading =
    isVarLoading || isStressLoading || isOptimizerLoading

  return (
    <form onSubmit={handleSubmit} className="min-w-0 space-y-6">
      <Card className="min-w-0 bg-card/88">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Portfolio Holdings
          </CardTitle>
          <CardDescription>
            Enter your portfolio positions with ticker symbols and quantities.
          </CardDescription>
        </CardHeader>
        <CardContent className="min-w-0 space-y-6">
          <div className="space-y-4 rounded-lg border bg-muted/50 p-4">
            <div className="grid gap-4 xl:grid-cols-[minmax(18rem,0.75fr)_minmax(0,1fr)_auto] xl:items-end">
              <div className="min-w-0 space-y-2">
                <Label htmlFor="portfolio-name">Active portfolio</Label>
                <Input
                  id="portfolio-name"
                  placeholder="Untitled portfolio"
                  value={portfolioName}
                  onChange={(event) => setPortfolioName(event.target.value)}
                  className="font-heading text-base"
                />
              </div>

              <div className="grid gap-2 rounded-md border bg-background px-3 py-2 text-xs text-muted-foreground sm:grid-cols-3">
                <div>
                  <p className="font-medium text-foreground">
                    {selectedPortfolioId ? "Loaded" : "Draft"}
                  </p>
                  <p className="truncate" title={portfolioName || "Untitled"}>
                    {portfolioName || "Untitled portfolio"}
                  </p>
                </div>
                <div>
                  <p className="font-medium text-foreground">Saved</p>
                  <p>{savedPortfolios.length.toLocaleString()} portfolios</p>
                </div>
                <div>
                  <p className="font-medium text-foreground">Status</p>
                  <div
                    className="flex min-w-0 items-center gap-2"
                    role="status"
                  >
                    {isAutosaving ? (
                      <Loader2 className="size-3.5 shrink-0 animate-spin" />
                    ) : (
                      <span className="size-2 shrink-0 rounded-full bg-chart-3" />
                    )}
                    <span className="truncate">
                      {isAutosaving
                        ? "Autosaving"
                        : saveStatus
                          ? saveStatus
                          : "Autosave on"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 sm:flex xl:justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleNewPortfolio}
                  className="w-full sm:w-28"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  New
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleSavePortfolio()}
                  disabled={isSaving}
                  className="w-full sm:w-28"
                >
                  {isSaving ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-2" />
                  )}
                  Save
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleDeletePortfolio()}
                  disabled={!selectedPortfolioId}
                  className="w-full sm:w-28"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </Button>
              </div>
            </div>

            <div className="flex flex-col gap-3 rounded-md border bg-background p-3 text-sm md:flex-row md:items-center md:justify-between">
              <div className="flex items-start gap-3">
                <Cloud className="mt-0.5 h-4 w-4 text-primary" />
                <div className="space-y-1">
                  <p className="font-medium">
                    {user ? "Cloud sync enabled" : "Local-only by default"}
                  </p>
                  <p className="text-muted-foreground">
                    {user
                      ? `Signed in as ${user.email ?? "your Supabase user"}.`
                      : "Your portfolios stay in this browser unless you sign in."}
                  </p>
                  {(syncStatus || authError) && (
                    <p
                      className={
                        authError ? "text-destructive" : "text-muted-foreground"
                      }
                      role={authError ? "alert" : "status"}
                    >
                      {authError ?? syncStatus}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                {user ? (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isSyncing}
                      onClick={() => void syncPortfolios()}
                    >
                      {isSyncing ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                      Sync now
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void handleSignOut()}
                    >
                      <LogOut className="h-4 w-4" />
                      Sign out
                    </Button>
                  </>
                ) : (
                  <Dialog>
                    <DialogTrigger asChild>
                      <Button type="button" variant="outline" size="sm">
                        <LogIn className="h-4 w-4" />
                        Sign in to sync
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Cloud sync</DialogTitle>
                        <DialogDescription>
                          Local portfolios remain private unless you sign in.
                        </DialogDescription>
                      </DialogHeader>
                      <LoginForm
                        error={authError}
                        isLoading={isAuthLoading || isSigningIn}
                        onGoogleSignIn={() => void handleGoogleSignIn()}
                      />
                    </DialogContent>
                  </Dialog>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 size-4 text-primary" />
              <p>
                Use US-listed or USD-quoted holdings only. Mixed currencies make
                portfolio value and weights misleading.
              </p>
            </div>
          </div>

          {/* Portfolio Entries */}
          <div className="flex min-w-0 w-full flex-col gap-4">
            <div className="max-w-full min-w-0 overflow-hidden pb-1">
              <div className="min-w-0 space-y-2">
                <div className="grid w-full grid-cols-[10.5rem_4.5rem_11.25rem_4rem_6rem_6.5rem_6rem_2rem] gap-2 text-sm font-medium text-muted-foreground">
                  <div>Security</div>
                  <div>Quantity</div>
                  <div className="flex items-center gap-1">
                    Current Price (USD)
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="size-3.5 cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent>
                        Latest USD quote. Prices refresh every{" "}
                        {priceRefreshIntervalLabel}; change this in Settings.
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <div>Weight</div>
                  <div>Market Value</div>
                  <div>Day Move</div>
                  <div>Day P&L</div>
                  <div />
                </div>

                {entries.map((entry) => {
                  const priceStatus = getEntryPriceStatus(entry)
                  const priceValue =
                    entry.priceStatus === "loading"
                      ? "Loading..."
                      : entry.currentPrice !== null
                        ? formatCurrency(entry.currentPrice)
                        : "Auto-filled"
                  const priceStatusClass =
                    priceStatus.tone === "error"
                      ? "text-destructive"
                      : priceStatus.tone === "subtle"
                        ? "text-muted-foreground/65"
                        : "text-muted-foreground"
                  const priceStatusDotClass =
                    priceStatus.tone === "error"
                      ? "bg-destructive"
                      : priceStatus.tone === "subtle"
                        ? "bg-muted-foreground/35"
                        : "bg-chart-3"
                  const marketValue = getEntryMarketValue(entry)
                  const dayChange = getEntryDayChange(entry)
                  const dayChangeClass =
                    dayChange && dayChange.pnl > 0
                      ? "text-chart-3"
                      : dayChange && dayChange.pnl < 0
                        ? "text-chart-5"
                        : "text-muted-foreground"

                  return (
                    <div
                      key={entry.id}
                      className="grid grid-cols-[10.5rem_4.5rem_11.25rem_4rem_6rem_6.5rem_6rem_2rem] gap-2"
                    >
                      <div>
                        <InputGroup className="min-w-0 overflow-hidden">
                          {entry.companyName && (
                            <InputGroupAddon
                              align="inline-start"
                              className="min-w-0 max-w-[5.5rem] flex-none justify-start border-r px-2 text-left text-xs font-normal"
                              title={[
                                entry.companyName,
                                entry.exchange,
                                entry.quoteCurrency,
                              ]
                                .filter(Boolean)
                                .join(" - ")}
                            >
                              <span className="block w-full truncate text-left">
                                {entry.companyName}
                              </span>
                            </InputGroupAddon>
                          )}
                          <InputGroupInput
                            placeholder="AAPL"
                            value={entry.ticker}
                            onChange={(e) =>
                              updateTicker(
                                entry.id,
                                e.target.value.toUpperCase(),
                              )
                            }
                            className={`min-w-0 font-mono text-right uppercase md:px-2 ${
                              entry.companyName
                                ? "ml-auto w-16 flex-none px-1.5"
                                : "flex-1"
                            }`}
                          />
                        </InputGroup>
                      </div>
                      <div>
                        <Input
                          type="number"
                          placeholder="0"
                          min="0"
                          step="any"
                          value={entry.quantity || ""}
                          onChange={(e) =>
                            updateEntry(
                              entry.id,
                              "quantity",
                              parseFloat(e.target.value) || 0,
                            )
                          }
                          className="px-2"
                        />
                      </div>
                      <div
                        className={`flex h-9 min-w-0 items-center rounded-md border bg-background px-2 text-sm shadow-xs ${
                          entry.priceStatus === "error"
                            ? "border-destructive"
                            : "border-input"
                        }`}
                        role="textbox"
                        aria-readonly="true"
                        aria-invalid={entry.priceStatus === "error"}
                        title={priceStatus.title}
                      >
                        <span
                          className={`shrink-0 whitespace-nowrap tabular-nums ${
                            entry.currentPrice === null &&
                            entry.priceStatus !== "loading"
                              ? "text-muted-foreground"
                              : ""
                          }`}
                        >
                          {priceValue}
                        </span>
                        <span className="mx-2 h-4 w-px shrink-0 bg-border" />
                        <span
                          className={`ml-auto inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-sm bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] ${priceStatusClass}`}
                        >
                          <span
                            className={`size-1.5 shrink-0 rounded-full ${priceStatusDotClass}`}
                          />
                          <span className="whitespace-nowrap">
                            {priceStatus.label}
                          </span>
                        </span>
                      </div>
                      <Input
                        readOnly
                        value={getEntryWeightLabel(entry.id)}
                        aria-label={`${entry.ticker || "Holding"} weight`}
                        className="px-2 text-right text-sm tabular-nums"
                      />
                      <Input
                        readOnly
                        value={
                          marketValue !== null
                            ? formatCurrency(marketValue)
                            : "-"
                        }
                        aria-label={`${entry.ticker || "Holding"} market value`}
                        className="px-2 text-right text-sm tabular-nums"
                      />
                      <Input
                        readOnly
                        value={
                          dayChange
                            ? `${formatSignedCurrency(dayChange.amount)} (${formatSignedPercent(dayChange.percent)})`
                            : "-"
                        }
                        aria-label={`${entry.ticker || "Holding"} day move`}
                        className={`px-2 text-right text-sm tabular-nums ${dayChangeClass}`}
                      />
                      <Input
                        readOnly
                        value={
                          dayChange ? formatSignedCurrency(dayChange.pnl) : "-"
                        }
                        aria-label={`${entry.ticker || "Holding"} day P&L`}
                        className={`px-2 text-right text-sm tabular-nums ${dayChangeClass}`}
                      />
                      <div className="flex items-center">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeEntry(entry.id)}
                          disabled={entries.length === 1}
                          className="w-full"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              onClick={addEntry}
              className="w-full"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Position
            </Button>
          </div>

          {/* Portfolio Summary */}
          <div className="rounded-lg bg-muted p-4">
            <div className="mt-1 flex justify-between text-sm font-bold">
              <span>Total Quantity</span>
              <span>{totalQuantity.toLocaleString()}</span>
            </div>
            <div className="mt-1 flex justify-between text-lg font-bold">
              <span className="flex items-center gap-1">
                Estimated Position Value
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="size-3.5 cursor-help text-muted-foreground" />
                  </TooltipTrigger>
                  <TooltipContent>
                    Estimated in USD from loaded current prices.
                  </TooltipContent>
                </Tooltip>
              </span>
              <span>{formatCurrency(estimatedPortfolioValue)}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="font-heading text-2xl font-semibold">Analyses</h2>
            <p className="text-sm text-muted-foreground">
              Tune the inputs on the left and review each matching output on the
              right.
            </p>
          </div>
          <Button type="submit" disabled={isAnyAnalysisLoading}>
            {isAnyAnalysisLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Updating Analyses...
              </>
            ) : (
              <>
                <TrendingUp className="mr-2 h-4 w-4" />
                Run All Analyses
              </>
            )}
          </Button>
        </div>

        {/* Error Display */}
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="h-5 w-5" />
                <p>{error}</p>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(260px,0.42fr)_minmax(0,1.58fr)] xl:items-start">
          <Card className="bg-card/88">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-chart-1" />
                VaR Settings
              </CardTitle>
              <CardDescription>
                Configure the loss horizon and simulation count.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-3 xl:grid-cols-1">
              <div className="space-y-2">
                <Label htmlFor="confidence">Confidence Level</Label>
                <Select
                  value={normalizeConfidenceLevel(confidenceLevel).toString()}
                  onValueChange={(v) =>
                    setConfidenceLevel(
                      normalizeConfidenceLevel(parseInt(v, 10)),
                    )
                  }
                >
                  <SelectTrigger id="confidence" className="w-full">
                    <SelectValue placeholder="Select confidence" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="90">90%</SelectItem>
                    <SelectItem value="95">95%</SelectItem>
                    <SelectItem value="99">99%</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="horizon">Time Horizon</Label>
                <Select
                  value={horizon.toString()}
                  onValueChange={(v) => setHorizon(parseInt(v))}
                >
                  <SelectTrigger id="horizon" className="w-full">
                    <SelectValue placeholder="Select horizon" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 Day</SelectItem>
                    <SelectItem value="5">5 Days (1 Week)</SelectItem>
                    <SelectItem value="22">22 Days (1 Month)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="simulations">VaR Simulations</Label>
                <Select
                  value={nSimulations.toString()}
                  onValueChange={(v) => setNSimulations(parseInt(v))}
                >
                  <SelectTrigger id="simulations" className="w-full">
                    <SelectValue placeholder="Select simulations" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1000">1,000</SelectItem>
                    <SelectItem value="10000">10,000</SelectItem>
                    <SelectItem value="50000">50,000</SelectItem>
                    <SelectItem value="100000">100,000</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                type="button"
                onClick={() => void handleRunVarAnalysis()}
                disabled={isVarLoading}
                className="sm:col-span-3 xl:col-span-1"
              >
                {isVarLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <AlertTriangle className="mr-2 h-4 w-4" />
                )}
                Run VaR
              </Button>
            </CardContent>
          </Card>

          <div className="space-y-3">
            {varError && (
              <Card className="border-destructive">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 text-destructive">
                    <AlertTriangle className="h-5 w-5" />
                    <p>{varError}</p>
                  </div>
                </CardContent>
              </Card>
            )}

            {result ? (
              <Card className="border-chart-1">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-chart-1">
                    <AlertTriangle className="h-5 w-5" />
                    Value at Risk Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div className="rounded-lg bg-muted p-4">
                      <p className="text-sm text-muted-foreground">
                        Value at Risk
                      </p>
                      <p className="text-2xl font-bold text-chart-1">
                        {formatCurrency(result.var_amount)}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {result.var_percentage.toFixed(2)}% of portfolio
                      </p>
                    </div>
                    <div className="rounded-lg bg-muted p-4">
                      <p className="text-sm text-muted-foreground">
                        Expected Shortfall
                      </p>
                      <p className="text-2xl font-bold text-chart-1">
                        {formatCurrency(result.cvar_amount)}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {result.cvar_percentage.toFixed(2)}% of portfolio
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2 rounded-lg bg-secondary p-4">
                    <p className="font-semibold">What does this mean?</p>
                    <p className="text-lg">
                      You have a{" "}
                      <span className="font-bold text-chart-1">
                        {(100 - result.confidence_level).toFixed(0)}%
                      </span>{" "}
                      chance of losing at least{" "}
                      <span className="font-bold text-chart-1">
                        {formatCurrency(result.var_amount)}
                      </span>{" "}
                      over the next {getHorizonLabel(result.horizon)}, which
                      represents{" "}
                      <span className="font-bold text-chart-1">
                        {result.var_percentage.toFixed(2)}%
                      </span>{" "}
                      of your{" "}
                      <span className="font-medium">
                        {formatCurrency(result.portfolio_value)}
                      </span>{" "}
                      portfolio.
                    </p>
                    <p className="text-sm text-muted-foreground">
                      If returns land in the worst{" "}
                      {(100 - result.confidence_level).toFixed(0)}% of simulated
                      outcomes, the average loss is{" "}
                      <span className="font-medium text-foreground">
                        {formatCurrency(result.cvar_amount)}
                      </span>
                      .
                    </p>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
                    <div className="rounded-lg bg-muted p-3">
                      <p className="text-xs text-muted-foreground">
                        Expected P&L
                      </p>
                      <p className="text-lg font-semibold">
                        {formatSignedCurrency(result.mean_pnl)}
                      </p>
                    </div>
                    <div className="rounded-lg bg-muted p-3">
                      <p className="text-xs text-muted-foreground">Best Case</p>
                      <p className="text-lg font-semibold text-chart-1">
                        {formatSignedCurrency(result.best_case)}
                      </p>
                    </div>
                    <div className="rounded-lg bg-muted p-3">
                      <p className="text-xs text-muted-foreground">
                        Worst Case
                      </p>
                      <p className="text-lg font-semibold text-destructive">
                        {formatSignedCurrency(result.worst_case)}
                      </p>
                    </div>
                    <div className="rounded-lg bg-muted p-3">
                      <p className="text-xs text-muted-foreground">
                        P&L Std. Dev.
                      </p>
                      <p className="text-lg font-semibold">
                        {formatCurrency(result.std_pnl)}
                      </p>
                    </div>
                    <div className="rounded-lg bg-muted p-3">
                      <p className="text-xs text-muted-foreground">P&L Range</p>
                      <p className="text-lg font-semibold">
                        {formatSignedCurrency(result.worst_case)} to{" "}
                        {formatSignedCurrency(result.best_case)}
                      </p>
                    </div>
                  </div>

                  {result.holdings.length > 0 && (
                    <MonteCarloSimulationChart
                      holdings={result.holdings.map((holding) => ({
                        ticker: holding.ticker,
                        quantity: holding.quantity,
                      }))}
                      initialHorizon={result.horizon}
                    />
                  )}

                  <div className="text-sm text-muted-foreground">
                    <p className="mb-1 font-medium">Technical Details:</p>
                    <ul className="list-inside list-disc space-y-1">
                      <li>Confidence Level: {result.confidence_level}%</li>
                      <li>Time Horizon: {getHorizonLabel(result.horizon)}</li>
                      <li>
                        Portfolio Value:{" "}
                        {formatCurrency(result.portfolio_value)}
                      </li>
                      <li>
                        Monte Carlo Simulations:{" "}
                        {result.n_simulations.toLocaleString()}
                      </li>
                    </ul>
                  </div>

                  {result.holdings.length > 0 && (
                    <div className="text-sm">
                      <p className="mb-2 font-medium">Calculated Holdings:</p>
                      <div className="space-y-2">
                        {result.holdings.map((holding) => (
                          <div
                            key={holding.ticker}
                            className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted px-3 py-2"
                          >
                            <span className="font-medium">
                              {holding.ticker}
                            </span>
                            <span className="text-muted-foreground">
                              {holding.quantity.toLocaleString()} shares at{" "}
                              {formatCurrency(holding.latest_price)}
                            </span>
                            <span>
                              {(holding.weight * 100).toFixed(2)}% /{" "}
                              {formatCurrency(holding.market_value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <Accordion
                    type="single"
                    collapsible
                    className="rounded-lg border px-4"
                  >
                    <AccordionItem value="glossary">
                      <AccordionTrigger>Key Terms</AccordionTrigger>
                      <AccordionContent className="space-y-3 text-muted-foreground">
                        <p>
                          <span className="font-medium text-foreground">
                            Value at Risk:
                          </span>{" "}
                          A threshold loss. At {result.confidence_level}%
                          confidence, losses should be less than this amount in
                          most comparable periods.
                        </p>
                        <p>
                          <span className="font-medium text-foreground">
                            CVaR / Expected Shortfall:
                          </span>{" "}
                          The average loss in the worst simulated tail outcomes.
                        </p>
                        <p>
                          <span className="font-medium text-foreground">
                            Monte Carlo Simulation:
                          </span>{" "}
                          A method that runs many possible portfolio outcomes
                          using historical return behavior and random shocks.
                        </p>
                        <p>
                          <span className="font-medium text-foreground">
                            Portfolio Value:
                          </span>{" "}
                          The current market value of your holdings, calculated
                          from latest prices and quantities.
                        </p>
                        <Button asChild variant="outline" size="sm">
                          <Link href="/glossary">Open full glossary</Link>
                        </Button>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                </CardContent>
              </Card>
            ) : (
              <AnalysisPlaceholderCard
                title="Value at Risk Analysis"
                isActive={isVarLoading}
                description={
                  isVarLoading
                    ? "Updating VaR analysis..."
                    : "No VaR analysis yet. Run all analyses to populate this panel."
                }
              />
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(260px,0.42fr)_minmax(0,1.58fr)] xl:items-start">
          <Card className="bg-card/88">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Gauge className="size-5 text-primary" />
                Stress Scenario
              </CardTitle>
              <CardDescription>
                Apply holding-level price shocks and a portfolio volatility
                multiplier.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setStressPriceShocks({})
                    setStressVolatilityPercent(100)
                  }}
                >
                  Reset
                </Button>
              </div>

              <div className="space-y-4">
                {stressHoldings.length > 0 ? (
                  stressHoldings.map((holding) => {
                    const shockValue = stressPriceShocks[holding.ticker] ?? 0

                    return (
                      <div key={holding.ticker} className="space-y-3">
                        <div className="flex items-center justify-between gap-3">
                          <Label htmlFor={`shock-${holding.ticker}`}>
                            {holding.ticker} price shock
                          </Label>
                          <span className="font-mono text-sm tabular-nums">
                            {shockValue > 0 ? "+" : ""}
                            {shockValue}%
                          </span>
                        </div>
                        <Slider
                          id={`shock-${holding.ticker}`}
                          min={-80}
                          max={80}
                          step={1}
                          value={[shockValue]}
                          onValueChange={(value) =>
                            updateStressPriceShock(
                              holding.ticker,
                              value[0] ?? 0,
                            )
                          }
                        />
                      </div>
                    )
                  })
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Add at least one ticker and quantity to run a stress test.
                  </p>
                )}
              </div>

              <div className="space-y-3 border-t pt-4">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="stress-volatility">
                    Global volatility multiplier
                  </Label>
                  <span className="font-mono text-sm tabular-nums">
                    {(stressVolatilityPercent / 100).toFixed(2)}x
                  </span>
                </div>
                <Slider
                  id="stress-volatility"
                  min={25}
                  max={500}
                  step={5}
                  value={[stressVolatilityPercent]}
                  onValueChange={(value) =>
                    setStressVolatilityPercent(value[0] ?? 100)
                  }
                />
              </div>
              <Button
                type="button"
                onClick={() => void handleRunStressTest()}
                disabled={isStressLoading}
                className="w-full"
              >
                {isStressLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Gauge className="mr-2 h-4 w-4" />
                )}
                Run Stress Test
              </Button>
            </CardContent>
          </Card>

          <div className="space-y-3">
            {stressError && (
              <Card className="border-destructive">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 text-destructive">
                    <AlertTriangle className="h-5 w-5" />
                    <p>{stressError}</p>
                  </div>
                </CardContent>
              </Card>
            )}

            <StressTestResults
              result={stressResult}
              isLoading={isStressLoading}
              isStale={isStressResultStale}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(260px,0.42fr)_minmax(0,1.58fr)] xl:items-start">
          <Card className="bg-card/88">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                Optimizer Settings
              </CardTitle>
              <CardDescription>
                Control how many random portfolios feed the efficient frontier.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="n-portfolios">Optimizer Portfolios</Label>
                <Select
                  value={nPortfolios}
                  onValueChange={(v) => setNPortfolios(v)}
                >
                  <SelectTrigger id="n-portfolios" className="w-full">
                    <SelectValue placeholder="Select portfolios" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="500">500</SelectItem>
                    <SelectItem value="1000">1,000</SelectItem>
                    <SelectItem value="5000">5,000</SelectItem>
                    <SelectItem value="10000">10,000</SelectItem>
                    <SelectItem value="50000">50,000</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <p className="text-xs text-muted-foreground">
                Optimization needs at least two distinct tickers.
              </p>
              <Button
                type="button"
                onClick={() => void handleRunOptimization()}
                disabled={isOptimizerLoading}
                className="w-full"
              >
                {isOptimizerLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <TrendingUp className="mr-2 h-4 w-4" />
                )}
                Run Optimizer
              </Button>
            </CardContent>
          </Card>

          <div className="space-y-3">
            {optimizerError && (
              <Card className="border-destructive">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 text-destructive">
                    <AlertTriangle className="h-5 w-5" />
                    <p>{optimizerError}</p>
                  </div>
                </CardContent>
              </Card>
            )}

            {optimizerResult ? (
              <OptimizerResults result={optimizerResult} />
            ) : (
              <AnalysisPlaceholderCard
                title="Efficient Frontier"
                isActive={isOptimizerLoading}
                description={
                  isOptimizerLoading
                    ? "Updating optimizer..."
                    : "No optimizer output yet. Run all analyses to populate this panel."
                }
              />
            )}
          </div>
        </div>
      </div>
    </form>
  )
}
