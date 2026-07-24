"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
import { apiBaseUrl } from "@/lib/api"
import {
  deleteCloudPortfolio,
  mirrorLocalAndCloudPortfolios,
  upsertCloudPortfolio,
  type PortfolioSyncResult,
} from "@/lib/cloud-portfolios"
import { fetchHistoricalPricesWithCache } from "@/lib/price-cache"
import { portfolioDb, type SavedPortfolio } from "@/lib/portfolio-db"
import {
  OptimizerResults,
  type OptimizerResult,
} from "@/components/optimizer-results"
import { MonteCarloSimulationChart } from "@/components/monte-carlo-simulation-chart"
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
} from "lucide-react"

interface PortfolioEntry {
  id: string
  ticker: string
  quantity: number
  currentPrice: number | null
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

const DEFAULT_N_PORTFOLIOS = "5000"
const DEFAULT_RISK_FREE_RATE = 0.05

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

export function PortfolioForm() {
  const [entries, setEntries] = useState<PortfolioEntry[]>([
    {
      id: "1",
      ticker: "",
      quantity: 0,
      currentPrice: null,
      priceStatus: "idle",
    },
  ])
  const [confidenceLevel, setConfidenceLevel] = useState<number>(95)
  const [horizon, setHorizon] = useState<number>(22)
  const [nSimulations, setNSimulations] = useState<number>(10000)
  const [analysisMode, setAnalysisMode] = useState<"var" | "optimize">("var")
  const [nPortfolios, setNPortfolios] = useState<string>(DEFAULT_N_PORTFOLIOS)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<VaRResult | null>(null)
  const [optimizerResult, setOptimizerResult] =
    useState<OptimizerResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [savedPortfolios, setSavedPortfolios] = useState<SavedPortfolio[]>([])
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(
    null,
  )
  const [portfolioName, setPortfolioName] = useState("")
  const [saveStatus, setSaveStatus] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
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

  const ENDPOINT = apiBaseUrl

  const createBlankEntry = (): PortfolioEntry => ({
    id: Date.now().toString(),
    ticker: "",
    quantity: 0,
    currentPrice: null,
    priceStatus: "idle",
  })

  const refreshSavedPortfolios = useCallback(async () => {
    const portfolios = await portfolioDb.savedPortfolios
      .orderBy("updatedAt")
      .reverse()
      .toArray()

    setSavedPortfolios(portfolios)
  }, [])

  useEffect(() => {
    void refreshSavedPortfolios()
  }, [refreshSavedPortfolios])

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
    setEntries([...entries, createBlankEntry()])
  }

  const removeEntry = (id: string) => {
    if (entries.length > 1) {
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
    setError(null)
    setEntries(
      entries.map((entry) =>
        entry.id === id
          ? {
              ...entry,
              ticker,
              currentPrice: null,
              priceStatus: ticker.trim() ? "loading" : "idle",
              priceError: undefined,
              priceFetchedAt: undefined,
              priceSource: undefined,
            }
          : entry,
      ),
    )
  }

  useEffect(() => {
    const timers = entries
      .map((entry) => {
        const ticker = entry.ticker.toUpperCase().trim()

        if (
          !ticker ||
          entry.currentPrice !== null ||
          entry.priceStatus === "error"
        ) {
          return null
        }

        return window.setTimeout(() => {
          void (async () => {
            try {
              const priceResult = await fetchHistoricalPricesWithCache({
                apiBaseUrl: ENDPOINT,
                tickers: [ticker],
                period: "5d",
              })
              const latestRow = priceResult.data.rows?.at(-1)
              const latestPrice = latestRow?.prices?.[ticker]

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
                        currentPrice: latestPrice,
                        priceStatus: "loaded",
                        priceError: undefined,
                        priceFetchedAt: priceResult.fetchedAt,
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
                        currentPrice: null,
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
        }, 500)
      })
      .filter((timer): timer is number => timer !== null)

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [ENDPOINT, entries])

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

  const createPortfolioId = () => {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID()
    }

    return Date.now().toString()
  }

  const getDefaultPortfolioName = (holdings: PortfolioRequest["holdings"]) => {
    const tickers = holdings.map((holding) => holding.ticker).join(", ")
    return tickers ? `${tickers} Portfolio` : "Untitled Portfolio"
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
      }

      await portfolioDb.savedPortfolios.put(portfolio)
      setSelectedPortfolioId(portfolio.id)
      setPortfolioName(portfolio.name)

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

    setSelectedPortfolioId(portfolio.id)
    setPortfolioName(portfolio.name)
    setEntries(getEntriesFromPortfolio(portfolio))
    setConfidenceLevel(portfolio.confidenceLevel)
    setHorizon(portfolio.horizon)
    setNSimulations(portfolio.nSimulations)
    setResult(null)
    setOptimizerResult(null)
    setError(null)
    setSaveStatus(`Loaded ${portfolio.name}.`)
  }

  const handleDeletePortfolio = async () => {
    if (!selectedPortfolioId) {
      return
    }

    await portfolioDb.savedPortfolios.delete(selectedPortfolioId)

    if (supabase && user) {
      try {
        await deleteCloudPortfolio(supabase, selectedPortfolioId)
        setSyncStatus("Cloud copy deleted.")
      } catch (err) {
        setAuthError(
          err instanceof Error
            ? err.message
            : "Failed to delete the cloud copy.",
        )
      }
    }

    setSelectedPortfolioId(null)
    setPortfolioName("")
    setSaveStatus("Saved portfolio deleted.")
    await refreshSavedPortfolios()
  }

  const handleNewPortfolio = () => {
    setSelectedPortfolioId(null)
    setPortfolioName("")
    setEntries([createBlankEntry()])
    setResult(null)
    setOptimizerResult(null)
    setError(null)
    setSaveStatus(null)
  }

  const handleSubmit = async (e: React.SubmitEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)
    setOptimizerResult(null)

    const holdings = buildHoldingsRequest()
    if (!holdings) {
      setError(
        "Please add at least one valid portfolio entry with a ticker and quantity.",
      )
      return
    }

    if (analysisMode === "optimize" && holdings.length < 2) {
      setError("Add at least two distinct tickers to run the optimizer.")
      return
    }

    setIsLoading(true)

    try {
      if (analysisMode === "var") {
        const request: PortfolioRequest = {
          holdings,
          horizon,
          confidence_level: confidenceLevel / 100,
          n_simulations: nSimulations,
        }

        const response = await fetch(`${ENDPOINT}/api/v1/analyze`, {
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

        setResult({
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
        })
      } else {
        const response = await fetch(`${ENDPOINT}/api/v1/optimize`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            holdings,
            n_portfolios: parseInt(nPortfolios, 10),
            risk_free_rate: DEFAULT_RISK_FREE_RATE,
          }),
        })

        if (!response.ok) {
          throw new Error(await getErrorMessage(response))
        }

        const data = (await response.json()) as OptimizerResult
        setOptimizerResult(data)
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : analysisMode === "var"
            ? "Failed to analyze portfolio."
            : "Failed to optimize portfolio.",
      )
    } finally {
      setIsLoading(false)
    }
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

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Portfolio Holdings
          </CardTitle>
          <CardDescription>
            Enter your portfolio positions with ticker symbols and quantities
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4 rounded-lg border bg-muted/50 p-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="portfolio-name">Portfolio Name</Label>
                  <Input
                    id="portfolio-name"
                    placeholder="Long-term portfolio"
                    value={portfolioName}
                    onChange={(event) => setPortfolioName(event.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="saved-portfolio">Saved Portfolio</Label>
                  <Select
                    value={selectedPortfolioId ?? ""}
                    onValueChange={(value) => void handleLoadPortfolio(value)}
                    disabled={savedPortfolios.length === 0}
                  >
                    <SelectTrigger id="saved-portfolio" className="w-full">
                      <SelectValue placeholder="Choose portfolio" />
                    </SelectTrigger>
                    <SelectContent>
                      {savedPortfolios.map((portfolio) => (
                        <SelectItem key={portfolio.id} value={portfolio.id}>
                          {portfolio.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
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
                {saveStatus && (
                  <p className="text-sm text-muted-foreground" role="status">
                    {saveStatus}
                  </p>
                )}
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
                          authError
                            ? "text-destructive"
                            : "text-muted-foreground"
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

            {/* Portfolio Entries */}
            <div className="flex flex-col gap-4 w-full">
              <div className="flex gap-2 w-full text-sm font-medium text-muted-foreground">
                <div className="flex-1">Ticker</div>
                <div className="flex-1">Quantity</div>
                <div className="flex-1">Current Price</div>
                <div className="w-8" />
              </div>

              {entries.map((entry) => (
                <div key={entry.id} className="flex gap-2">
                  <div className="flex-1">
                    <Input
                      placeholder="AAPL"
                      value={entry.ticker}
                      onChange={(e) =>
                        updateTicker(entry.id, e.target.value.toUpperCase())
                      }
                      className="uppercase"
                    />
                  </div>
                  <div className="flex-1">
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
                    />
                  </div>
                  <div className="flex-1">
                    <Input
                      readOnly
                      value={
                        entry.priceStatus === "loading"
                          ? "Loading..."
                          : entry.currentPrice !== null
                            ? formatCurrency(entry.currentPrice)
                            : ""
                      }
                      placeholder="Auto-filled"
                      aria-invalid={entry.priceStatus === "error"}
                    />
                    {entry.priceStatus === "error" && entry.priceError && (
                      <p className="mt-1 text-xs text-destructive">
                        {entry.priceError}
                      </p>
                    )}
                    {entry.priceStatus === "loaded" &&
                      entry.priceFetchedAt &&
                      entry.priceSource && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          {entry.priceSource === "network"
                            ? "Updated"
                            : entry.priceSource === "cache"
                              ? "Cached"
                              : "Using cached price from"}{" "}
                          {formatCacheTimestamp(entry.priceFetchedAt)}
                        </p>
                      )}
                  </div>
                  <div className="col-span-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeEntry(entry.id)}
                      disabled={entries.length === 1}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}

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
                <span>Estimated Position Value</span>
                <span>{formatCurrency(estimatedPortfolioValue)}</span>
              </div>
            </div>

            <div className="space-y-3">
              <Label>Analysis Mode</Label>
              <Tabs
                value={analysisMode}
                onValueChange={(value) =>
                  setAnalysisMode(value === "optimize" ? "optimize" : "var")
                }
              >
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="var">Value at Risk Analysis</TabsTrigger>
                  <TabsTrigger value="optimize">Efficient frontier</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            {analysisMode === "var" ? (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="confidence">Confidence Level</Label>
                  <Select
                    value={confidenceLevel.toString()}
                    onValueChange={(v) => setConfidenceLevel(parseInt(v))}
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
                  <Label htmlFor="simulations">
                    Number of Monte Carlo Simulations
                  </Label>
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
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="n-portfolios">Simulated Portfolios</Label>
                  <Select
                    value={nPortfolios}
                    onValueChange={(v) => setNPortfolios(v)}
                  >
                    <SelectTrigger id="n-portfolios" className="w-full">
                      <SelectValue placeholder="Select simulations" />
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
                  Optimization needs at least two distinct tickers.{" "}
                </p>
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {analysisMode === "var"
                    ? "Analyzing Portfolio..."
                    : "Optimizing Portfolio..."}
                </>
              ) : (
                <>
                  <TrendingUp className="mr-2 h-4 w-4" />
                  {analysisMode === "var"
                    ? "Calculate VaR"
                    : "Run Optimization"}
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

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

      {analysisMode === "var" && result && (
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
                <p className="text-sm text-muted-foreground">Value at Risk</p>
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

            <div className="rounded-lg bg-secondary p-4 space-y-2">
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

            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <div className="rounded-lg bg-muted p-3">
                <p className="text-xs text-muted-foreground">Expected P&L</p>
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
                <p className="text-xs text-muted-foreground">Worst Case</p>
                <p className="text-lg font-semibold text-destructive">
                  {formatSignedCurrency(result.worst_case)}
                </p>
              </div>
              <div className="rounded-lg bg-muted p-3">
                <p className="text-xs text-muted-foreground">P&L Spread</p>
                <p className="text-lg font-semibold">
                  {formatCurrency(result.std_pnl)}
                </p>
              </div>
            </div>

            {result.holdings.length > 0 && (
              <MonteCarloSimulationChart
                holdings={result.holdings.map((holding) => ({
                  ticker: holding.ticker,
                  quantity: holding.quantity,
                }))}
                apiBaseUrl={ENDPOINT}
                initialHorizon={result.horizon}
              />
            )}

            <div className="text-sm text-muted-foreground">
              <p className="font-medium mb-1">Technical Details:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Confidence Level: {result.confidence_level}%</li>
                <li>Time Horizon: {getHorizonLabel(result.horizon)}</li>
                <li>
                  Portfolio Value: {formatCurrency(result.portfolio_value)}
                </li>
                <li>
                  Monte Carlo Simulations:{" "}
                  {result.n_simulations.toLocaleString()}
                </li>
              </ul>
            </div>

            {result.holdings.length > 0 && (
              <div className="text-sm">
                <p className="font-medium mb-2">Calculated Holdings:</p>
                <div className="space-y-2">
                  {result.holdings.map((holding) => (
                    <div
                      key={holding.ticker}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted px-3 py-2"
                    >
                      <span className="font-medium">{holding.ticker}</span>
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
                    A threshold loss. At {result.confidence_level}% confidence,
                    losses should be less than this amount in most comparable
                    periods.
                  </p>
                  <p>
                    <span className="font-medium text-foreground">
                      Expected Shortfall:
                    </span>{" "}
                    The average loss in the worst simulated tail outcomes.
                  </p>
                  <p>
                    <span className="font-medium text-foreground">
                      Monte Carlo Simulation:
                    </span>{" "}
                    A method that runs many possible portfolio outcomes using
                    historical return behavior and random shocks.
                  </p>
                  <p>
                    <span className="font-medium text-foreground">
                      Portfolio Value:
                    </span>{" "}
                    The current market value of your holdings, calculated from
                    latest prices and quantities.
                  </p>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      )}

      {analysisMode === "optimize" && optimizerResult && (
        <OptimizerResults result={optimizerResult} />
      )}
    </div>
  )
}
