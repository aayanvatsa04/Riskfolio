import type { Metadata } from "next"

import { AppShell } from "@/components/app-shell"
import { SettingsPanel } from "@/components/settings-panel"
import { Badge } from "@/components/ui/badge"

export const metadata: Metadata = {
  title: "Settings - Riskfolio",
  description: "Riskfolio market data and analysis preferences.",
}

export default function SettingsPage() {
  return (
    <AppShell>
      <main className="min-h-screen">
        <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-6 lg:px-8">
          <div className="mb-6 border-b pb-6">
            <Badge variant="secondary" className="mb-3 font-mono">
              CONTROL PANEL
            </Badge>
            <h1 className="font-heading text-4xl font-semibold">Settings</h1>
            <p className="mt-3 max-w-3xl leading-7 text-muted-foreground">
              Tune market-data freshness and decide which portfolio assumptions
              should become configurable next.
            </p>
          </div>

          <SettingsPanel />
        </div>
      </main>
    </AppShell>
  )
}
