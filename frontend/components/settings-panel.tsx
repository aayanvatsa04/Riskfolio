"use client"

import { useEffect, useState } from "react"
import { Clock3, DatabaseZap } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { portfolioDb } from "@/lib/portfolio-db"
import {
  DEFAULT_USER_SETTINGS,
  formatPriceRefreshInterval,
  getUserSettings,
  PRICE_REFRESH_INTERVAL_OPTIONS,
  saveUserSettings,
  type PriceRefreshIntervalMinutes,
  type UserSettings,
} from "@/lib/user-settings"

export function SettingsPanel() {
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_USER_SETTINGS)
  const [status, setStatus] = useState<string | null>(null)
  const [isClearingCache, setIsClearingCache] = useState(false)
  const [isClearingAnalysisCache, setIsClearingAnalysisCache] = useState(false)

  useEffect(() => {
    setSettings(getUserSettings())
  }, [])

  const updatePriceRefreshInterval = (value: string) => {
    const interval = Number(value) as PriceRefreshIntervalMinutes
    const nextSettings = {
      ...settings,
      priceRefreshIntervalMinutes: interval,
    }

    setSettings(nextSettings)
    saveUserSettings(nextSettings)
    setStatus(
      `Price refresh interval set to ${formatPriceRefreshInterval(interval)}.`,
    )
  }

  const clearPriceCache = async () => {
    setIsClearingCache(true)
    setStatus(null)

    try {
      await portfolioDb.priceResponses.clear()
      setStatus("Cached quote data cleared.")
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Failed to clear cache.")
    } finally {
      setIsClearingCache(false)
    }
  }

  const clearAnalysisCache = async () => {
    setIsClearingAnalysisCache(true)
    setStatus(null)

    try {
      await portfolioDb.analysisResponses.clear()
      setStatus("Cached analysis outputs cleared.")
    } catch (err) {
      setStatus(
        err instanceof Error ? err.message : "Failed to clear analysis cache.",
      )
    } finally {
      setIsClearingAnalysisCache(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6">
      <Card className="bg-card/88">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2">
            <Badge variant="secondary" className="font-mono">
              MARKET DATA
            </Badge>
          </div>
          <CardTitle className="flex items-center gap-2 font-heading text-2xl">
            <Clock3 className="size-5 text-primary" />
            Price Refresh
          </CardTitle>
          <CardDescription>
            Current prices are cached locally and refreshed after the selected
            interval.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[minmax(0,1fr)_13rem] md:items-end">
            <div className="space-y-2">
              <Label htmlFor="price-refresh-interval">
                Refresh cached prices every
              </Label>
              <Select
                value={settings.priceRefreshIntervalMinutes.toString()}
                onValueChange={updatePriceRefreshInterval}
              >
                <SelectTrigger id="price-refresh-interval" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PRICE_REFRESH_INTERVAL_OPTIONS.map((interval) => (
                    <SelectItem key={interval} value={interval.toString()}>
                      {formatPriceRefreshInterval(interval)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={isClearingCache}
              onClick={() => void clearPriceCache()}
            >
              <DatabaseZap className="size-4" />
              Clear price cache
            </Button>
          </div>

          <div className="flex flex-col gap-2 rounded-md border bg-background/70 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium">Analysis output cache</p>
              <p className="text-sm text-muted-foreground">
                Stored VaR, optimizer, stress, and path results are refreshed
                only when you click a run button.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={isClearingAnalysisCache}
              onClick={() => void clearAnalysisCache()}
              className="sm:w-44"
            >
              <DatabaseZap className="size-4" />
              Clear analysis cache
            </Button>
          </div>

          <Separator />

          <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
            Prices come from the historical price endpoint and are treated as
            USD quotes. The dashboard rejects confirmed non-USD tickers, but
            unavailable metadata is treated as unknown rather than blocking the
            user.
          </div>

          {status && (
            <p className="text-sm text-muted-foreground" role="status">
              {status}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
