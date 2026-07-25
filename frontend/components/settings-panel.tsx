"use client"

import { useEffect, useState } from "react"
import {
  Clock3,
  CloudOff,
  DatabaseZap,
  HardDrive,
  Save,
  Trash2,
} from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
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
import { Switch } from "@/components/ui/switch"
import { useSupabaseAuth } from "@/hooks/use-supabase-auth"
import { deleteAllCloudPortfolios } from "@/lib/cloud-portfolios"
import { portfolioDb } from "@/lib/portfolio-db"
import { notifyPortfolioListChanged } from "@/lib/portfolio-events"
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
  const [portfolioStatus, setPortfolioStatus] = useState<string | null>(null)
  const [isClearingLocalPortfolios, setIsClearingLocalPortfolios] =
    useState(false)
  const [isClearingCloudPortfolios, setIsClearingCloudPortfolios] =
    useState(false)
  const {
    supabase,
    user,
    isConfigured: isSupabaseConfigured,
    isLoading: isAuthLoading,
    signOut,
  } = useSupabaseAuth()

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

  const updateAutosaveEnabled = (autosaveEnabled: boolean) => {
    const nextSettings = {
      ...settings,
      autosaveEnabled,
    }

    setSettings(nextSettings)
    saveUserSettings(nextSettings)
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

  const clearLocalPortfolios = async () => {
    setIsClearingLocalPortfolios(true)
    setPortfolioStatus(null)

    try {
      await portfolioDb.savedPortfolios.clear()
      notifyPortfolioListChanged()
      setPortfolioStatus(
        "Saved portfolios were removed from this browser. Cloud copies were not changed.",
      )
    } catch (err) {
      setPortfolioStatus(
        err instanceof Error
          ? err.message
          : "Failed to clear browser portfolios.",
      )
    } finally {
      setIsClearingLocalPortfolios(false)
    }
  }

  const clearCloudPortfolios = async () => {
    if (!supabase || !user) {
      setPortfolioStatus("Sign in before clearing cloud portfolios.")
      return
    }

    setIsClearingCloudPortfolios(true)
    setPortfolioStatus(null)

    try {
      await deleteAllCloudPortfolios(supabase, user.id)
      const signOutError = await signOut()

      setPortfolioStatus(
        signOutError
          ? `Cloud portfolios were deleted, but sign-out failed: ${signOutError}`
          : "Cloud portfolios were deleted and you were signed out. Browser copies were not changed.",
      )
    } catch (err) {
      setPortfolioStatus(
        err instanceof Error
          ? err.message
          : "Failed to clear cloud portfolios.",
      )
    } finally {
      setIsClearingCloudPortfolios(false)
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

      <Card className="bg-card/88">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2">
            <Badge variant="secondary" className="font-mono">
              PORTFOLIO
            </Badge>
          </div>
          <CardTitle className="flex items-center gap-2 font-heading text-2xl">
            <Save className="size-5 text-primary" />
            Save Behavior
          </CardTitle>
          <CardDescription>
            Choose whether portfolio edits are saved automatically in this
            browser.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 rounded-md border bg-background/70 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <Label htmlFor="portfolio-autosave">Portfolio autosave</Label>
              <p className="max-w-2xl text-sm text-muted-foreground">
                When enabled, changes are saved after a short delay. You can
                still use the Save button when autosave is disabled.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">
                {settings.autosaveEnabled ? "Enabled" : "Disabled"}
              </span>
              <Switch
                id="portfolio-autosave"
                checked={settings.autosaveEnabled}
                onCheckedChange={updateAutosaveEnabled}
                aria-label="Enable portfolio autosave"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/35 bg-card/88">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2">
            <Badge variant="destructive" className="font-mono">
              DANGER ZONE
            </Badge>
          </div>
          <CardTitle className="flex items-center gap-2 font-heading text-2xl">
            <Trash2 className="size-5 text-destructive" />
            Saved Portfolios
          </CardTitle>
          <CardDescription>
            Permanently remove saved portfolios from this browser or your
            signed-in cloud account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-4 rounded-md border bg-background/70 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="flex items-center gap-2 text-sm font-medium">
                <HardDrive className="size-4 text-muted-foreground" />
                Browser portfolio cache
              </p>
              <p className="max-w-2xl text-sm text-muted-foreground">
                Deletes every portfolio stored in IndexedDB on this browser.
                Cloud copies remain and can sync back after sign-in.
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  type="button"
                  variant="destructive"
                  disabled={isClearingLocalPortfolios}
                  className="sm:w-52"
                >
                  <Trash2 className="size-4" />
                  {isClearingLocalPortfolios
                    ? "Clearing..."
                    : "Wipe browser portfolios"}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Wipe browser portfolios?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This permanently deletes every portfolio saved in this
                    browser. Cloud copies are not affected and may sync back
                    when you sign in.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-destructive text-white hover:bg-destructive/90"
                    onClick={() => void clearLocalPortfolios()}
                  >
                    Wipe browser portfolios
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          <div className="flex flex-col gap-4 rounded-md border bg-background/70 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="flex items-center gap-2 text-sm font-medium">
                <CloudOff className="size-4 text-muted-foreground" />
                Cloud portfolios
              </p>
              <p className="max-w-2xl text-sm text-muted-foreground">
                Deletes every portfolio in your cloud account and signs you out
                to prevent browser copies from immediately syncing back.
              </p>
            </div>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  type="button"
                  variant="destructive"
                  disabled={
                    isAuthLoading ||
                    isClearingCloudPortfolios ||
                    !supabase ||
                    !user
                  }
                  className="sm:w-52"
                >
                  <CloudOff className="size-4" />
                  {isClearingCloudPortfolios
                    ? "Clearing..."
                    : "Wipe cloud portfolios"}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Wipe cloud portfolios?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This permanently deletes every portfolio saved to your cloud
                    account. Browser copies are not affected. You will be signed
                    out afterward so they cannot immediately upload again.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-destructive text-white hover:bg-destructive/90"
                    onClick={() => void clearCloudPortfolios()}
                  >
                    Wipe cloud portfolios
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          {!isAuthLoading && !user && (
            <p className="text-sm text-muted-foreground">
              {isSupabaseConfigured
                ? "Sign in from the dashboard to enable cloud portfolio deletion."
                : "Cloud portfolio deletion is unavailable because Supabase is not configured."}
            </p>
          )}

          {portfolioStatus && (
            <p className="text-sm text-muted-foreground" role="status">
              {portfolioStatus}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
