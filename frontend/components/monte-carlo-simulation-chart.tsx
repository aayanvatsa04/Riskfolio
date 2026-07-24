"use client"

import { useEffect, useMemo, useState } from "react"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Activity, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Skeleton } from "@/components/ui/skeleton"
import {
  getAnalysisCacheKey,
  readCachedAnalysisResponse,
  writeCachedAnalysisResponse,
} from "@/lib/analysis-cache"
import { apiUrl } from "@/lib/api"

const pathColor = "var(--muted-foreground)"
const downsideColor = "var(--chart-5)"
const upsideColor = "var(--chart-3)"
const meanColor = "var(--chart-4)"
const axisColor = "var(--muted-foreground)"
const gridColor = "var(--border)"

type HoldingRequest = {
  ticker: string
  quantity: number
}

type SimulationPoint = {
  day: number
  value: number
}

type SimulationPath = {
  path_id: number
  points: SimulationPoint[]
}

type SummaryPoint = {
  day: number
  mean: number
  p05: number
  p50: number
  p95: number
}

type SimulationResponse = {
  horizon: number
  n_paths: number
  volatility_multiplier: number
  portfolio_value: number
  summary: SummaryPoint[]
  paths: SimulationPath[]
}

type ChartRow = SummaryPoint & Record<string, number>

type TooltipPayloadItem = {
  payload: ChartRow
}

type SimulationTooltipProps = {
  active?: boolean
  payload?: TooltipPayloadItem[]
}

type MonteCarloSimulationChartProps = {
  holdings: HoldingRequest[]
  initialHorizon: number
}

type ApiErrorDetail = {
  msg?: string
  message?: string
}

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
})

const compactCurrencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
})

function formatCurrency(value: number) {
  return currencyFormatter.format(value)
}

function formatCompactCurrency(value: number) {
  return compactCurrencyFormatter.format(value)
}

async function getErrorMessage(response: Response) {
  const errorData = await response.json().catch(() => null)

  if (typeof errorData?.detail === "string") {
    return errorData.detail
  }

  if (Array.isArray(errorData?.detail)) {
    return errorData.detail
      .map(
        (item: ApiErrorDetail) => item.msg || item.message || "Invalid input",
      )
      .join(", ")
  }

  return `Server error: ${response.status}`
}

function SimulationTooltip({ active, payload }: SimulationTooltipProps) {
  if (!active || !payload?.length) {
    return null
  }

  const row = payload[0].payload

  return (
    <div className="space-y-1 rounded-lg border bg-background/95 p-2.5 text-xs shadow-lg backdrop-blur">
      <p className="border-b pb-1 font-semibold text-foreground">
        Day {row.day}
      </p>
      <p className="text-muted-foreground">
        Mean:{" "}
        <span className="font-medium text-foreground">
          {formatCurrency(row.mean)}
        </span>
      </p>
      <p className="text-muted-foreground">
        Median:{" "}
        <span className="font-medium text-foreground">
          {formatCurrency(row.p50)}
        </span>
      </p>
      <p className="text-muted-foreground">
        5%-95% range:{" "}
        <span className="font-medium text-foreground">
          {formatCurrency(row.p05)} to {formatCurrency(row.p95)}
        </span>
      </p>
    </div>
  )
}

export function MonteCarloSimulationChart({
  holdings,
  initialHorizon,
}: MonteCarloSimulationChartProps) {
  const [pathCount, setPathCount] = useState(100)
  const [volatilityPercent, setVolatilityPercent] = useState(100)
  const [horizon, setHorizon] = useState(initialHorizon)
  const [data, setData] = useState<SimulationResponse | null>(null)
  const [dataRequestKey, setDataRequestKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const holdingsKey = useMemo(() => JSON.stringify(holdings), [holdings])
  const requestHoldings = useMemo(
    () => JSON.parse(holdingsKey) as HoldingRequest[],
    [holdingsKey],
  )

  useEffect(() => {
    setHorizon(initialHorizon)
  }, [initialHorizon])

  const simulationRequest = useMemo(
    () => ({
      holdings: requestHoldings,
      horizon,
      n_paths: pathCount,
      volatility_multiplier: volatilityPercent / 100,
    }),
    [horizon, pathCount, requestHoldings, volatilityPercent],
  )
  const simulationRequestKey = useMemo(
    () => getAnalysisCacheKey("monte-carlo-paths", simulationRequest),
    [simulationRequest],
  )

  useEffect(() => {
    let cancelled = false

    void readCachedAnalysisResponse<SimulationResponse>(
      "monte-carlo-paths",
      simulationRequest,
    ).then((cached) => {
      if (cancelled) {
        return
      }

      if (cached) {
        setData(cached.response)
        setDataRequestKey(simulationRequestKey)
        setError(null)
      }
    })

    return () => {
      cancelled = true
    }
  }, [simulationRequest, simulationRequestKey])

  const runSimulation = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(apiUrl("monte-carlo-paths"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(simulationRequest),
      })

      if (!response.ok) {
        throw new Error(await getErrorMessage(response))
      }

      const nextData = (await response.json()) as SimulationResponse
      await writeCachedAnalysisResponse(
        "monte-carlo-paths",
        simulationRequest,
        nextData,
      )
      setData(nextData)
      setDataRequestKey(simulationRequestKey)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to simulate Monte Carlo paths.",
      )
    } finally {
      setIsLoading(false)
    }
  }

  const isDataStale = Boolean(data) && dataRequestKey !== simulationRequestKey

  const chartData = useMemo<ChartRow[]>(() => {
    if (!data) {
      return []
    }

    return data.summary.map((summaryPoint) => {
      const row: ChartRow = { ...summaryPoint }

      data.paths.forEach((path) => {
        const point = path.points[summaryPoint.day]
        if (point) {
          row[`path_${path.path_id}`] = point.value
        }
      })

      return row
    })
  }, [data])

  const pathKeys = useMemo(
    () => data?.paths.map((path) => `path_${path.path_id}`) ?? [],
    [data],
  )

  const yDomain = useMemo<[number, number] | undefined>(() => {
    if (!data?.summary.length) {
      return undefined
    }

    const lows = data.summary.map((point) => point.p05)
    const highs = data.summary.map((point) => point.p95)
    const min = Math.min(...lows)
    const max = Math.max(...highs)
    const padding = Math.max((max - min) * 0.08, data.portfolio_value * 0.01)

    return [min - padding, max + padding]
  }, [data])

  return (
    <div className="space-y-4 rounded-lg border p-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            <p className="font-semibold">Monte Carlo Price Paths</p>
          </div>
          {data && (
            <p className="text-sm text-muted-foreground">
              {data.n_paths.toLocaleString()} paths,{" "}
              {data.horizon.toLocaleString()} trading days,{" "}
              {data.volatility_multiplier.toFixed(2)}x historical volatility
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={isLoading}
            onClick={() => {
              setPathCount(100)
              setVolatilityPercent(100)
              setHorizon(initialHorizon)
            }}
          >
            Reset
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={isLoading}
            onClick={() => void runSimulation()}
          >
            {isLoading ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Updating
              </>
            ) : (
              "Run Paths"
            )}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="mc-paths">Paths</Label>
            <span className="text-sm font-medium tabular-nums">
              {pathCount}
            </span>
          </div>
          <Slider
            id="mc-paths"
            min={10}
            max={200}
            step={10}
            value={[pathCount]}
            onValueChange={(value) => setPathCount(value[0] ?? 100)}
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="mc-volatility">Volatility</Label>
            <span className="text-sm font-medium tabular-nums">
              {volatilityPercent}%
            </span>
          </div>
          <Slider
            id="mc-volatility"
            min={25}
            max={250}
            step={5}
            value={[volatilityPercent]}
            onValueChange={(value) => setVolatilityPercent(value[0] ?? 100)}
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="mc-horizon">Horizon</Label>
            <span className="text-sm font-medium tabular-nums">
              {horizon} days
            </span>
          </div>
          <Slider
            id="mc-horizon"
            min={1}
            max={252}
            step={1}
            value={[horizon]}
            onValueChange={(value) => setHorizon(value[0] ?? initialHorizon)}
          />
        </div>
      </div>

      {(isDataStale || (!data && !isLoading && !error)) && (
        <div className="rounded-md border bg-background/80 px-3 py-2 text-xs text-muted-foreground">
          {isDataStale
            ? "Path settings changed. Run Paths to update this cached chart."
            : "Run Paths to generate and cache the simulation chart."}
        </div>
      )}

      <div className="relative h-[380px] w-full">
        {isLoading && (
          <div className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded-md border bg-background/90 px-2 py-1 text-xs shadow-sm">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Simulating
          </div>
        )}

        {error ? (
          <div className="flex h-full items-center justify-center rounded-md bg-muted p-4 text-center text-sm text-destructive">
            {error}
          </div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 16, right: 24, bottom: 40, left: 64 }}
            >
              <CartesianGrid
                stroke={gridColor}
                strokeDasharray="3 3"
                opacity={0.55}
              />
              <XAxis
                dataKey="day"
                axisLine={{ stroke: gridColor }}
                tickLine={{ stroke: gridColor }}
                tick={{ fontSize: 11, fill: axisColor }}
                label={{
                  value: "Trading Day",
                  position: "insideBottom",
                  offset: -24,
                  style: {
                    fontSize: 12,
                    fill: axisColor,
                  },
                }}
              />
              <YAxis
                domain={yDomain}
                tickFormatter={(value) => formatCompactCurrency(Number(value))}
                axisLine={{ stroke: gridColor }}
                tickLine={{ stroke: gridColor }}
                tick={{ fontSize: 11, fill: axisColor }}
                width={58}
                label={{
                  value: "Portfolio Value",
                  angle: -90,
                  position: "insideLeft",
                  offset: -48,
                  style: {
                    fontSize: 12,
                    fill: axisColor,
                  },
                }}
              />
              <Tooltip
                cursor={{ stroke: "var(--ring)", strokeDasharray: "3 3" }}
                content={<SimulationTooltip />}
              />
              {pathKeys.map((key) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={pathColor}
                  strokeWidth={1}
                  opacity={0.2}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
              <Line
                type="monotone"
                dataKey="p05"
                name="5th percentile"
                stroke={downsideColor}
                strokeWidth={1.75}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="p95"
                name="95th percentile"
                stroke={upsideColor}
                strokeWidth={1.75}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="mean"
                name="Mean"
                stroke={meanColor}
                strokeWidth={2.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="grid h-full grid-rows-[1fr_auto] gap-4 rounded-md bg-muted/50 p-4">
            <Skeleton className="h-full w-full" />
            <div className="grid grid-cols-3 gap-3">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
