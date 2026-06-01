"use client"

import { useEffect, useState } from "react"
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
import { Trash2, Plus, TrendingUp, AlertTriangle, Loader2 } from "lucide-react"

interface PortfolioEntry {
  id: string
  ticker: string
  quantity: number
  currentPrice: number | null
  priceStatus: "idle" | "loading" | "loaded" | "error"
  priceError?: string
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
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<VaRResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const ENDPOINT = "http://localhost:8000"

  const addEntry = () => {
    setEntries([
      ...entries,
      {
        id: Date.now().toString(),
        ticker: "",
        quantity: 0,
        currentPrice: null,
        priceStatus: "idle",
      },
    ])
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
    setEntries(
      entries.map((entry) =>
        entry.id === id ? { ...entry, [field]: value } : entry,
      ),
    )
  }

  const updateTicker = (id: string, ticker: string) => {
    setEntries(
      entries.map((entry) =>
        entry.id === id
          ? {
              ...entry,
              ticker,
              currentPrice: null,
              priceStatus: ticker.trim() ? "loading" : "idle",
              priceError: undefined,
            }
          : entry,
      ),
    )
  }

  const fetchCurrentPrice = async (id: string, ticker: string) => {
    try {
      const params = new URLSearchParams({ tickers: ticker, period: "5d" })
      const response = await fetch(`${ENDPOINT}/historical-prices?${params}`)

      if (!response.ok) {
        throw new Error(await getErrorMessage(response))
      }

      const data = await response.json()
      const latestRow = data.rows?.at(-1)
      const latestPrice = latestRow?.prices?.[ticker]

      if (typeof latestPrice !== "number" || !Number.isFinite(latestPrice)) {
        throw new Error(`No current price found for ${ticker}`)
      }

      setEntries((currentEntries) =>
        currentEntries.map((entry) =>
          entry.id === id && entry.ticker.toUpperCase().trim() === ticker
            ? {
                ...entry,
                currentPrice: latestPrice,
                priceStatus: "loaded",
                priceError: undefined,
              }
            : entry,
        ),
      )
    } catch (err) {
      setEntries((currentEntries) =>
        currentEntries.map((entry) =>
          entry.id === id && entry.ticker.toUpperCase().trim() === ticker
            ? {
                ...entry,
                currentPrice: null,
                priceStatus: "error",
                priceError:
                  err instanceof Error ? err.message : "Failed to fetch price",
              }
            : entry,
        ),
      )
    }
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
          void fetchCurrentPrice(entry.id, ticker)
        }, 500)
      })
      .filter((timer): timer is number => timer !== null)

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [entries])

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

  const getErrorMessage = async (response: Response) => {
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

  const handleSubmit = async (e: React.SubmitEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)

    const holdings = buildHoldingsRequest()
    if (!holdings) {
      setError(
        "Please add at least one valid portfolio entry with a ticker and quantity.",
      )
      return
    }

    const request: PortfolioRequest = {
      holdings,
      horizon,
      confidence_level: confidenceLevel / 100,
      n_simulations: nSimulations,
    }

    setIsLoading(true)

    try {
      const response = await fetch(`${ENDPOINT}/analyze`, {
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
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to analyze portfolio.",
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

            {/* VaR Parameters */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="confidence">Confidence Level</Label>
                <Select
                  value={confidenceLevel.toString()}
                  onValueChange={(v) => setConfidenceLevel(parseInt(v))}
                >
                  <SelectTrigger id="confidence">
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
                  <SelectTrigger id="horizon">
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
                <Label htmlFor="simulations">Monte Carlo Simulations</Label>
                <Select
                  value={nSimulations.toString()}
                  onValueChange={(v) => setNSimulations(parseInt(v))}
                >
                  <SelectTrigger id="simulations">
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

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyzing Portfolio...
                </>
              ) : (
                <>
                  <TrendingUp className="h-4 w-4 mr-2" />
                  Calculate VaR
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

      {/* Results Display */}
      {result && (
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

            <div className="text-sm text-muted-foreground">
              <p className="font-medium mb-1">Technical Details:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Confidence Level: {result.confidence_level}%</li>
                <li>
                  Time Horizon: {getHorizonLabel(result.horizon)}
                </li>
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

            <Accordion type="single" collapsible className="rounded-lg border px-4">
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
    </div>
  )
}
