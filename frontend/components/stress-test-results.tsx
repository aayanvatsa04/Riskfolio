"use client"

import { Activity, AlertTriangle } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export type StressScenarioResult = {
  var: number
  var_positive: number
  cvar: number
  cvar_positive: number
  mean_pnl: number
  std_pnl: number
  worst_case: number
  best_case: number
  confidence_level: number
  n_simulations: number
  portfolio_value: number
  portfolio_weights: Record<string, number>
}

export type StressTestResult = {
  tickers: string[]
  baseline: StressScenarioResult
  shocked: StressScenarioResult
  shocks_applied: {
    price_shocks: Record<string, number>
    volatility_multiplier: number
  }
}

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
})

function formatCurrency(value: number) {
  return currencyFormatter.format(value)
}

function formatSignedCurrency(value: number) {
  const absoluteValue = formatCurrency(Math.abs(value))

  if (value > 0) {
    return `+${absoluteValue}`
  }

  if (value < 0) {
    return `-${absoluteValue}`
  }

  return absoluteValue
}

function pct(value: number) {
  return `${(value * 100).toFixed(2)}%`
}

function ScenarioCard({
  title,
  badge,
  scenario,
}: {
  title: string
  badge: string
  scenario: StressScenarioResult
}) {
  const weights = Object.entries(scenario.portfolio_weights).sort(
    ([, a], [, b]) => b - a,
  )

  return (
    <div className="space-y-4 rounded-lg border bg-card/80 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="font-heading text-lg font-semibold">{title}</p>
        <Badge variant="secondary">{badge}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-md bg-muted p-3">
          <p className="text-xs text-muted-foreground">Portfolio value</p>
          <p className="font-semibold tabular-nums">
            {formatCurrency(scenario.portfolio_value)}
          </p>
        </div>
        <div className="rounded-md bg-muted p-3">
          <p className="text-xs text-muted-foreground">VaR</p>
          <p className="font-semibold tabular-nums text-chart-5">
            {formatCurrency(scenario.var_positive)}
          </p>
        </div>
        <div className="rounded-md bg-muted p-3">
          <p className="text-xs text-muted-foreground">CVaR</p>
          <p className="font-semibold tabular-nums text-chart-5">
            {formatCurrency(scenario.cvar_positive)}
          </p>
        </div>
        <div className="rounded-md bg-muted p-3">
          <p className="text-xs text-muted-foreground">P&L Std. Dev.</p>
          <p className="font-semibold tabular-nums">
            {formatCurrency(scenario.std_pnl)}
          </p>
        </div>
        <div className="rounded-md bg-muted p-3">
          <p className="text-xs text-muted-foreground">Worst case</p>
          <p className="font-semibold tabular-nums text-destructive">
            {formatSignedCurrency(scenario.worst_case)}
          </p>
        </div>
        <div className="rounded-md bg-muted p-3">
          <p className="text-xs text-muted-foreground">Best case</p>
          <p className="font-semibold tabular-nums text-chart-3">
            {formatSignedCurrency(scenario.best_case)}
          </p>
        </div>
      </div>

      {weights.length > 0 && (
        <div className="space-y-2 border-t pt-3">
          <p className="text-xs font-medium text-muted-foreground">
            Scenario weights
          </p>
          {weights.map(([ticker, weight]) => (
            <div
              key={ticker}
              className="flex items-center justify-between gap-3 text-sm"
            >
              <span className="font-mono font-medium">{ticker}</span>
              <span className="tabular-nums text-muted-foreground">
                {pct(weight)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function StressTestResults({
  result,
  isLoading,
  isStale,
}: {
  result: StressTestResult | null
  isLoading: boolean
  isStale?: boolean
}) {
  const skeletonClass = isLoading ? "" : "animate-none bg-muted/70"

  if (!result) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="size-5 text-primary" />
            Stress Test
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-md border bg-background/80 px-3 py-2 text-sm text-muted-foreground">
            {isLoading
              ? "Updating stress scenario..."
              : "No stress analysis yet. Run all analyses to populate this panel."}
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Skeleton className={`h-72 w-full ${skeletonClass}`} />
            <Skeleton className={`h-72 w-full ${skeletonClass}`} />
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-primary/30">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="size-5 text-primary" />
          Stress Test
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Baseline versus shocked portfolio under{" "}
          {result.shocks_applied.volatility_multiplier.toFixed(2)}x volatility.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {(isLoading || isStale) && (
          <div className="rounded-md border bg-background/80 px-3 py-2 text-xs text-muted-foreground">
            {isLoading
              ? "Updating stress scenario..."
              : "Scenario inputs changed. Run Stress Test to update this cached output."}
          </div>
        )}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ScenarioCard
            title="Baseline"
            badge="Current"
            scenario={result.baseline}
          />
          <ScenarioCard
            title="Shocked"
            badge="Scenario"
            scenario={result.shocked}
          />
        </div>
      </CardContent>
    </Card>
  )
}
