"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Trash2, Plus, TrendingUp, AlertTriangle, Loader2 } from "lucide-react"

interface PortfolioEntry {
  id: string
  ticker: string
  buyPrice: number
  currentValue: number
  dateTransacted: string
}

interface PortfolioRequest {
  portfolio: Record<string, number>
  portfolio_value: number
  horizon: number
  confidence_level: number
  n_simulations: number
}

interface VaRResult {
  var_amount: number
  var_percentage: number
  confidence_level: number
  horizon: number
  portfolio_value: number
}

export function PortfolioForm() {
  const [entries, setEntries] = useState<PortfolioEntry[]>([
    { id: "1", ticker: "", buyPrice: 0, currentValue: 0, dateTransacted: "" },
  ])
  const [confidenceLevel, setConfidenceLevel] = useState<number>(95)
  const [horizon, setHorizon] = useState<number>(22)
  const [nSimulations, setNSimulations] = useState<number>(10000)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<VaRResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [apiEndpoint, setApiEndpoint] = useState<string>("http://localhost:8000")

  const addEntry = () => {
    setEntries([
      ...entries,
      {
        id: Date.now().toString(),
        ticker: "",
        buyPrice: 0,
        currentValue: 0,
        dateTransacted: "",
      },
    ])
  }

  const removeEntry = (id: string) => {
    if (entries.length > 1) {
      setEntries(entries.filter((entry) => entry.id !== id))
    }
  }

  const updateEntry = (id: string, field: keyof PortfolioEntry, value: string | number) => {
    setEntries(
      entries.map((entry) =>
        entry.id === id ? { ...entry, [field]: value } : entry
      )
    )
  }

  const calculateWeightsAndValue = (): { portfolio: Record<string, number>; portfolio_value: number } | null => {
    const validEntries = entries.filter(
      (e) => e.ticker.trim() !== "" && e.currentValue > 0
    )

    if (validEntries.length === 0) {
      return null
    }

    const totalValue = validEntries.reduce((sum, e) => sum + e.currentValue, 0)
    const portfolio: Record<string, number> = {}

    validEntries.forEach((entry) => {
      const ticker = entry.ticker.toUpperCase().trim()
      const weight = entry.currentValue / totalValue
      if (portfolio[ticker]) {
        portfolio[ticker] += weight
      } else {
        portfolio[ticker] = weight
      }
    })

    return { portfolio, portfolio_value: totalValue }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)

    const calculated = calculateWeightsAndValue()
    if (!calculated) {
      setError("Please add at least one valid portfolio entry with a ticker and current value.")
      return
    }

    const request: PortfolioRequest = {
      portfolio: calculated.portfolio,
      portfolio_value: calculated.portfolio_value,
      horizon,
      confidence_level: confidenceLevel / 100,
      n_simulations: nSimulations,
    }

    setIsLoading(true)

    try {
      const response = await fetch(`${apiEndpoint}/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Server error: ${response.status}`)
      }

      const data = await response.json()
      setResult({
        var_amount: data.var_amount ?? data.VaR ?? data.var ?? 0,
        var_percentage: data.var_percentage ?? ((data.var_amount ?? data.VaR ?? data.var ?? 0) / calculated.portfolio_value) * 100,
        confidence_level: confidenceLevel,
        horizon,
        portfolio_value: calculated.portfolio_value,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze portfolio. Please ensure your FastAPI server is running.")
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

  const totalPortfolioValue = entries.reduce((sum, e) => sum + (e.currentValue || 0), 0)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Portfolio Holdings
          </CardTitle>
          <CardDescription>
            Enter your portfolio positions with ticker symbols and current market values
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* API Endpoint */}
            <div className="space-y-2">
              <Label htmlFor="api-endpoint">FastAPI Server URL</Label>
              <Input
                id="api-endpoint"
                type="text"
                value={apiEndpoint}
                onChange={(e) => setApiEndpoint(e.target.value)}
                placeholder="http://localhost:8000"
              />
            </div>

            {/* Portfolio Entries */}
            <div className="space-y-4">
              <div className="grid grid-cols-12 gap-2 text-sm font-medium text-muted-foreground">
                <div className="col-span-3">Ticker</div>
                <div className="col-span-3">Buy Price ($)</div>
                <div className="col-span-3">Current Value ($)</div>
                <div className="col-span-2">Date</div>
                <div className="col-span-1"></div>
              </div>

              {entries.map((entry) => (
                <div key={entry.id} className="grid grid-cols-12 gap-2 items-center">
                  <div className="col-span-3">
                    <Input
                      placeholder="AAPL"
                      value={entry.ticker}
                      onChange={(e) => updateEntry(entry.id, "ticker", e.target.value.toUpperCase())}
                      className="uppercase"
                    />
                  </div>
                  <div className="col-span-3">
                    <Input
                      type="number"
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                      value={entry.buyPrice || ""}
                      onChange={(e) => updateEntry(entry.id, "buyPrice", parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <div className="col-span-3">
                    <Input
                      type="number"
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                      value={entry.currentValue || ""}
                      onChange={(e) => updateEntry(entry.id, "currentValue", parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <div className="col-span-2">
                    <Input
                      type="date"
                      value={entry.dateTransacted}
                      onChange={(e) => updateEntry(entry.id, "dateTransacted", e.target.value)}
                    />
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

              <Button type="button" variant="outline" onClick={addEntry} className="w-full">
                <Plus className="h-4 w-4 mr-2" />
                Add Position
              </Button>
            </div>

            {/* Total Portfolio Value */}
            <div className="rounded-lg bg-muted p-4">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Total Portfolio Value</span>
                <span className="text-lg font-bold">{formatCurrency(totalPortfolioValue)}</span>
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
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg bg-muted p-4">
                <p className="text-sm text-muted-foreground">VaR Amount</p>
                <p className="text-2xl font-bold text-chart-1">{formatCurrency(result.var_amount)}</p>
              </div>
              <div className="rounded-lg bg-muted p-4">
                <p className="text-sm text-muted-foreground">VaR Percentage</p>
                <p className="text-2xl font-bold text-chart-1">{result.var_percentage.toFixed(2)}%</p>
              </div>
            </div>

            <div className="rounded-lg bg-secondary p-4 space-y-2">
              <p className="font-semibold">What does this mean?</p>
              <p className="text-muted-foreground">
                With a <span className="font-medium text-foreground">{result.confidence_level}%</span> confidence level 
                and a <span className="font-medium text-foreground">{result.horizon}-day</span> time horizon:
              </p>
              <p className="text-lg">
                You have a <span className="font-bold text-chart-1">{(100 - result.confidence_level).toFixed(0)}%</span> chance 
                of losing at least <span className="font-bold text-chart-1">{formatCurrency(result.var_amount)}</span>, 
                which represents <span className="font-bold text-chart-1">{result.var_percentage.toFixed(2)}%</span> of 
                your <span className="font-medium">{formatCurrency(result.portfolio_value)}</span> portfolio.
              </p>
            </div>

            <div className="text-sm text-muted-foreground">
              <p className="font-medium mb-1">Technical Details:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Confidence Level: {result.confidence_level}%</li>
                <li>Time Horizon: {result.horizon} trading day{result.horizon > 1 ? "s" : ""}</li>
                <li>Portfolio Value: {formatCurrency(result.portfolio_value)}</li>
                <li>Monte Carlo Simulations: {nSimulations.toLocaleString()}</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
