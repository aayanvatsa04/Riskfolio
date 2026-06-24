import { PortfolioForm } from "@/components/portfolio-form";
import { TrendingUp } from "lucide-react";

export default function Page() {
  return (
    <main className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <div className="p-3 rounded-xl bg-primary">
              <TrendingUp className="h-8 w-8 text-primary-foreground" />
            </div>
            <h1 className="text-4xl font-bold tracking-tight">Riskfolio</h1>
          </div>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto text-balance">
            Monte Carlo Value at Risk (VaR) analysis for your investment
            portfolio. Understand your potential downside risk with statistical
            confidence.
          </p>
        </div>

        {/* Portfolio Form */}
        <PortfolioForm />

        {/* Footer Info */}
        <div className="mt-8 text-center text-sm text-muted-foreground">
          <p>
            VaR is calculated using Monte Carlo simulation with historical
            return distributions.
          </p>
        </div>
      </div>
    </main>
  );
}
