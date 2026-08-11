"use client"

import type { ElementType } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  EfficientFrontierChart,
  type PortfolioPoint,
  type FrontierPoint,
} from "@/components/efficient-frontier-chart"
import {
  ArrowDownCircle,
  ArrowUpCircle,
  CheckCircle2,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react"

export type { PortfolioPoint, FrontierPoint }

export interface OptimizerResult {
  tickers: string[]
  frontier_points: FrontierPoint[]
  analytical_frontier_curve: FrontierPoint[]
  max_sharpe_portfolio: PortfolioPoint
  min_vol_portfolio: PortfolioPoint
  current_portfolio: PortfolioPoint
  risk_free_rate: number
  n_portfolios: number
  portfolio_value?: number
  portfolio_currency?: string | null
}

type ShareTargetAction = "buy" | "sell" | "already_correct"

type ShareTarget = {
  action: ShareTargetAction
  current_shares: number
  target_shares: number
  shares_to_trade: number
  latest_price: number
  current_weight: number
  target_weight: number
}

type ShareTargets = {
  portfolio_value: number
  portfolio_currency?: string | null
  shares: Record<string, ShareTarget>
}

type PortfolioWithTargets = PortfolioPoint & {
  share_targets?: ShareTargets | null
}

function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

function WeightBar({ ticker, weight }: { ticker: string; weight: number }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-16 text-right font-mono font-medium">{ticker}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${(weight * 100).toFixed(1)}%` }}
        />
      </div>
      <span className="w-12 text-right tabular-nums text-muted-foreground">
        {pct(weight)}
      </span>
    </div>
  )
}

function shares(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 4,
  }).format(value)
}

function ShareTargetLine({
  ticker,
  target,
}: {
  ticker: string
  target: ShareTarget
}) {
  const Icon =
    target.action === "buy"
      ? ArrowUpCircle
      : target.action === "sell"
        ? ArrowDownCircle
        : CheckCircle2
  const actionClass =
    target.action === "buy"
      ? "text-chart-3"
      : target.action === "sell"
        ? "text-chart-5"
        : "text-muted-foreground"
  const actionText =
    target.action === "buy"
      ? `Buy ${shares(target.shares_to_trade)}`
      : target.action === "sell"
        ? `Sell ${shares(target.shares_to_trade)}`
        : "Already correct"

  return (
    <div className="grid grid-cols-[1rem_1fr] gap-2 rounded-md bg-muted/60 p-2 text-xs">
      <Icon className={`mt-0.5 size-4 ${actionClass}`} />
      <div className="min-w-0 space-y-1">
        <div className="flex items-center justify-between gap-3">
          <span className={`font-medium ${actionClass}`}>
            {actionText} {ticker}
          </span>
          <span className="font-mono text-muted-foreground">
            {pct(target.target_weight)}
          </span>
        </div>
        <p className="text-muted-foreground">
          Target {shares(target.target_shares)} shares from current{" "}
          {shares(target.current_shares)}.
        </p>
      </div>
    </div>
  )
}

function PortfolioStatsCard({
  title,
  icon: Icon,
  portfolio,
  accentColor,
  badge,
}: {
  title: string
  icon: ElementType
  portfolio: PortfolioWithTargets
  accentColor: string
  badge?: string
}) {
  const sortedWeights = portfolio.weights
    ? Object.entries(portfolio.weights).sort(([, a], [, b]) => b - a)
    : []
  const targetEntries = portfolio.share_targets?.shares
    ? Object.entries(portfolio.share_targets.shares).sort(([a], [b]) =>
        a.localeCompare(b),
      )
    : []

  return (
    <div className="min-w-0 space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className={`size-4 shrink-0 ${accentColor}`} />
          <p className="min-w-0 break-words text-sm font-semibold leading-tight">
            {title}
          </p>
        </div>
        {badge && (
          <Badge
            variant="secondary"
            className="max-w-full whitespace-normal text-xs"
          >
            {badge}
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-3 gap-1 text-center">
        <div className="rounded-md bg-muted p-2">
          <p className="text-xs text-muted-foreground">Return</p>
          <p className={`text-sm font-bold tabular-nums ${accentColor}`}>
            {pct(portfolio.expected_return)}
          </p>
        </div>
        <div className="rounded-md bg-muted p-2">
          <p className="text-xs text-muted-foreground">Volatility</p>
          <p className="text-sm font-bold tabular-nums">
            {pct(portfolio.volatility)}
          </p>
        </div>
        <div className="rounded-md bg-muted p-2">
          <p className="text-xs text-muted-foreground">Sharpe</p>
          <p className="text-sm font-bold tabular-nums">
            {portfolio.sharpe.toFixed(3)}
          </p>
        </div>
      </div>

      {sortedWeights.length > 0 && (
        <div className="space-y-2 border-t pt-1">
          <p className="text-xs font-medium text-muted-foreground">
            Allocation
          </p>
          {sortedWeights.map(([ticker, weight]) => (
            <WeightBar key={ticker} ticker={ticker} weight={weight} />
          ))}
        </div>
      )}

      {targetEntries.length > 0 && (
        <div className="space-y-2 border-t pt-3">
          <p className="text-xs font-medium text-muted-foreground">
            Rebalance Plan
          </p>
          {targetEntries.map(([ticker, target]) => (
            <ShareTargetLine key={ticker} ticker={ticker} target={target} />
          ))}
        </div>
      )}
    </div>
  )
}

export function OptimizerResults({ result }: { result: OptimizerResult }) {
  const tickerList = result.tickers.join(", ")

  return (
    <Card className="border-primary/30">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          Portfolio Optimisation - Efficient Frontier
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {result.n_portfolios.toLocaleString()} random portfolios simulated
          across {tickerList}. Grey dots are sampled allocations; the red line
          is the analytical frontier from the optimizer model.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <EfficientFrontierChart
          frontierPoints={result.frontier_points}
          analyticalFrontierCurve={result.analytical_frontier_curve ?? []}
          maxSharpePortfolio={result.max_sharpe_portfolio}
          minVolPortfolio={result.min_vol_portfolio}
          currentPortfolio={result.current_portfolio}
        />

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-3">
          <PortfolioStatsCard
            title="Max Sharpe (Optimal)"
            icon={TrendingUp}
            portfolio={result.max_sharpe_portfolio}
            accentColor="text-green-500"
            badge="Best risk-return"
          />
          <PortfolioStatsCard
            title="Min Volatility"
            icon={TrendingDown}
            portfolio={result.min_vol_portfolio}
            accentColor="text-yellow-500"
            badge="Most stable"
          />
          <PortfolioStatsCard
            title="Your Portfolio"
            icon={Target}
            portfolio={result.current_portfolio}
            accentColor="text-blue-500"
          />
        </div>

        <div className="space-y-2 rounded-lg bg-secondary p-4 text-sm">
          <p className="font-semibold">How to read this</p>
          <p className="leading-relaxed text-muted-foreground">
            Further right on the chart means more volatile. Higher up means
            better expected return. The{" "}
            <span className="font-medium text-green-600">green dot</span> is the
            allocation with the highest Sharpe ratio - the most return per unit
            of risk achievable from{" "}
            <span className="font-medium text-foreground">{tickerList}</span>.
            The <span className="font-medium text-yellow-600">yellow dot</span>{" "}
            is the least volatile allocation. The{" "}
            <span className="font-medium text-red-600">red line</span> traces
            the analytical Markowitz frontier. Your current weighting is shown
            in <span className="font-medium text-blue-600">blue</span> - if it
            sits inside the frontier cloud, rebalancing could improve your
            risk-return profile without changing which stocks you hold.
          </p>
          <p className="border-t pt-2 text-xs text-muted-foreground">
            Risk-free rate:{" "}
            <span className="font-medium">{pct(result.risk_free_rate)}</span>{" "}
            annualised. Returns and volatilities are annualised from 5 years of
            historical daily data.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
