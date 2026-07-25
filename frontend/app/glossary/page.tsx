import type { Metadata } from "next"

import { AppShell } from "@/components/app-shell"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export const metadata: Metadata = {
  title: "Glossary - Riskfolio",
  description:
    "Plain-English definitions for portfolio risk and optimization terms used in Riskfolio.",
}

const terms = [
  {
    term: "Efficient Frontier",
    fullName: "Best return for each risk level",
    summary:
      "The curve of portfolios that offer the highest expected return for a given level of volatility.",
    context:
      "Riskfolio plots the efficient frontier so you can see whether a portfolio sits near the best available risk-return tradeoff.",
  },
  {
    term: "Analytical Frontier",
    fullName: "Optimizer-calculated frontier",
    summary:
      "A frontier curve calculated directly from the portfolio optimizer rather than sampled from random portfolios.",
    context:
      "Riskfolio keeps the analytical frontier fully visible on the chart because it represents the modeled risk-return boundary.",
  },
  {
    term: "Expected Annual Return",
    fullName: "Projected yearly return",
    summary: "The portfolio return estimate expressed as an annual percentage.",
    context:
      "Riskfolio uses expected annual return on the efficient-frontier chart's vertical axis.",
  },
  {
    term: "Annual Volatility",
    fullName: "Yearly return variability",
    summary:
      "A measure of how much portfolio returns are expected to fluctuate over a year.",
    context:
      "Riskfolio uses annual volatility on the efficient-frontier chart's horizontal axis as the main measure of risk.",
  },
  {
    term: "Sharpe Ratio",
    fullName: "Return per unit of risk",
    summary:
      "A risk-adjusted return metric that compares excess return with volatility.",
    context:
      "Riskfolio uses Sharpe ratio to identify the allocation with the strongest return per unit of volatility.",
  },
  {
    term: "Max Sharpe Portfolio",
    fullName: "Highest Sharpe allocation",
    summary:
      "The portfolio allocation with the highest Sharpe ratio among the optimizer's candidates.",
    context:
      "Riskfolio marks this point on the efficient-frontier chart as the modeled allocation with the best risk-adjusted return.",
  },
  {
    term: "Min Volatility Portfolio",
    fullName: "Lowest-risk allocation",
    summary:
      "The portfolio allocation with the lowest modeled volatility among the optimizer's candidates.",
    context:
      "Riskfolio marks this point so you can compare the lowest-risk allocation against the current and max-Sharpe portfolios.",
  },
  {
    term: "Simulated Portfolio Cloud",
    fullName: "Random allocation scatter plot",
    summary:
      "A scatter of randomly generated portfolios used to visualize possible risk-return combinations.",
    context:
      "Riskfolio shows thousands of simulated portfolios behind the analytical frontier to reveal the shape and density of the opportunity set.",
  },
  {
    term: "Percentile Clipping",
    fullName: "Robust chart scaling",
    summary:
      "A chart-scaling method that ignores the most extreme random scatter points when choosing axis limits.",
    context:
      "Riskfolio clips only the simulated portfolio cloud for axis scaling, while still fully including the analytical frontier, Max Sharpe, Min Volatility, and Your Portfolio markers.",
  },
  {
    term: "VaR",
    fullName: "Value at Risk",
    summary:
      "A threshold loss estimate for a chosen confidence level and time horizon.",
    context:
      "In Riskfolio, a 95% one-month VaR of $1,000 means the simulation estimates a 5% chance of losing at least $1,000 over the next month.",
  },
  {
    term: "CVaR",
    fullName: "Conditional Value at Risk / Expected Shortfall",
    summary:
      "The average loss among the worst simulated outcomes beyond the VaR cutoff.",
    context:
      "Riskfolio uses CVaR to show how severe losses may be when the portfolio lands in the tail of the simulated distribution.",
  },
  {
    term: "Monte Carlo Simulation",
    fullName: "Repeated random scenario simulation",
    summary:
      "A method that runs many possible future outcomes using random draws based on historical return behavior.",
    context:
      "Riskfolio simulates thousands of portfolio P&L outcomes, then reads VaR, CVaR, best case, and worst case from that distribution.",
  },
  {
    term: "Confidence Level",
    fullName: "Probability threshold",
    summary:
      "The percentage of simulated outcomes expected to stay above the VaR loss threshold.",
    context:
      "At 95% confidence, Riskfolio focuses on the worst 5% of simulated outcomes. At 99%, it focuses on the worst 1%.",
  },
  {
    term: "Portfolio Value",
    fullName: "Current market value",
    summary:
      "The current dollar value of all holdings, using latest prices multiplied by share quantities.",
    context:
      "Riskfolio treats portfolio value as today’s USD market value, not your original purchase cost.",
  },
  {
    term: "Geometric Brownian Motion",
    fullName: "GBM",
    summary:
      "A common model for simulating price changes with drift and volatility, where returns compound over time.",
    context:
      "Riskfolio uses GBM-style log-return simulation so multi-day outcomes compound consistently and can preserve historical asset co-movement.",
  },
]

export default function GlossaryPage() {
  return (
    <AppShell>
      <main className="min-h-screen">
        <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-6 lg:px-8">
          <div className="mb-6 border-b pb-6">
            <Badge variant="secondary" className="mb-3 font-mono">
              REFERENCE
            </Badge>
            <h1 className="font-heading text-4xl font-semibold">
              Risk Glossary
            </h1>
            <p className="mt-3 max-w-3xl leading-7 text-muted-foreground">
              Plain-English explanations for the portfolio risk concepts used
              throughout Riskfolio.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {terms.map((item) => (
              <Card
                key={item.term}
                className="flex h-full flex-col gap-0 bg-card/88 py-0"
              >
                <CardHeader className="gap-2 px-5 pb-3 pt-5">
                  <CardTitle className="font-heading text-xl leading-tight">
                    {item.term}
                  </CardTitle>
                  <Badge
                    variant="outline"
                    className="h-auto w-fit max-w-full whitespace-normal px-2 py-0.5 text-left text-[11px] leading-4"
                  >
                    {item.fullName}
                  </Badge>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-4 px-5 pb-5 pt-0">
                  <p className="text-sm leading-6">{item.summary}</p>
                  <div className="mt-auto rounded-md border bg-muted/50 p-3.5">
                    <p className="mb-1.5 font-mono text-[11px] tracking-wide text-muted-foreground">
                      IN RISKFOLIO
                    </p>
                    <p className="text-sm leading-6 text-muted-foreground">
                      {item.context}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </main>
    </AppShell>
  )
}
