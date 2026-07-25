import { AppShell } from "@/components/app-shell"
import { PortfolioForm } from "@/components/portfolio-form"
import { TrendingUp } from "lucide-react"

export default function Page() {
  return (
    <AppShell>
      <main className="min-h-screen overflow-x-hidden">
        <div className="mx-auto w-full max-w-[1800px] px-4 py-6 md:px-6 lg:px-8">
          <div className="mb-6 border-b pb-6">
            <div className="max-w-3xl">
              <div className="mb-3 flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                  <TrendingUp className="size-5" />
                </div>
                <h1 className="font-heading text-4xl font-semibold md:text-5xl">
                  Riskfolio
                </h1>
              </div>
              <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
                Portfolio risk analysis, stress testing, and efficient frontier
                optimization for USD-quoted holdings.
              </p>
            </div>
          </div>

          <PortfolioForm />

          <div className="mt-8 border-t pt-4 text-sm text-muted-foreground">
            VaR is calculated using Monte Carlo simulation. Frontier
            optimization uses historical prices to simulate random weighted
            portfolios.
          </div>
        </div>
      </main>
    </AppShell>
  )
}
