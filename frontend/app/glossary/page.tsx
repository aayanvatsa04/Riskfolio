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

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {terms.map((item) => (
              <Card key={item.term} className="bg-card/88">
                <CardHeader>
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle className="font-heading text-2xl">
                      {item.term}
                    </CardTitle>
                    <Badge variant="outline">{item.fullName}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="leading-7">{item.summary}</p>
                  <div className="rounded-lg border bg-muted/50 p-4">
                    <p className="mb-1 font-mono text-xs text-muted-foreground">
                      IN RISKFOLIO
                    </p>
                    <p className="leading-7 text-muted-foreground">
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
