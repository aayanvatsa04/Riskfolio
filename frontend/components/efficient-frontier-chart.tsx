"use client"

import { useMemo } from "react"
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts"

export type FrontierPoint = {
  expected_return: number
  volatility: number
  sharpe: number
}

export type PortfolioPoint = FrontierPoint & {
  weights?: Record<string, number>
}

type ChartPoint = {
  x: number
  y: number
  sharpe: number
}

type ChartPointWithLabel = ChartPoint & { label?: string }

interface Props {
  frontierPoints: FrontierPoint[]
  maxSharpePortfolio: PortfolioPoint
  minVolPortfolio: PortfolioPoint
  currentPortfolio: PortfolioPoint
}

function toChartPoint(p: FrontierPoint): ChartPoint {
  return {
    x: p.volatility * 100,
    y: p.expected_return * 100,
    sharpe: p.sharpe,
  }
}

interface TooltipPayloadItem {
  payload: ChartPointWithLabel
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayloadItem[]
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border bg-background/95 p-2.5 text-xs shadow-lg backdrop-blur space-y-1">
      {d.label && (
        <p className="mb-1 border-b pb-1 font-semibold text-foreground">
          {d.label}
        </p>
      )}
      <p className="text-muted-foreground">
        Volatility:{" "}
        <span className="font-medium text-foreground">{d.x.toFixed(2)}%</span>
      </p>
      <p className="text-muted-foreground">
        Expected Return:{" "}
        <span className="font-medium text-foreground">{d.y.toFixed(2)}%</span>
      </p>
      <p className="text-muted-foreground">
        Sharpe Ratio:{" "}
        <span className="font-medium text-foreground">
          {d.sharpe.toFixed(3)}
        </span>
      </p>
    </div>
  )
}

type DotProps = { cx?: number; cy?: number; [key: string]: unknown }

const makeMarker = (color: string) =>
  function PortfolioMarker(props: unknown) {
    const { cx, cy } = props as DotProps
    if (cx == null || cy == null) return <g />
    return (
      <circle
        cx={cx}
        cy={cy}
        r={9}
        fill={color}
        stroke="white"
        strokeWidth={2.5}
      />
    )
  }

const GreenMarker = makeMarker("#22c55e")
const BlueMarker = makeMarker("#3b82f6")
const AmberMarker = makeMarker("#f59e0b")

function getPaddedDomain(values: number[]): [number, number] {
  const finiteValues = values.filter(Number.isFinite)

  if (finiteValues.length === 0) {
    return [0, 1]
  }

  const min = Math.min(...finiteValues)
  const max = Math.max(...finiteValues)

  if (min === max) {
    const padding = Math.max(Math.abs(min) * 0.1, 1)
    return [min - padding, max + padding]
  }

  const padding = (max - min) * 0.08
  return [min - padding, max + padding]
}

export function EfficientFrontierChart({
  frontierPoints,
  maxSharpePortfolio,
  minVolPortfolio,
  currentPortfolio,
}: Props) {
  const frontierData = useMemo(
    () => frontierPoints.map(toChartPoint),
    [frontierPoints],
  )

  const maxSharpePoint = useMemo(
    () => ({
      ...toChartPoint(maxSharpePortfolio),
      label: "Max Sharpe (Optimal)",
    }),
    [maxSharpePortfolio],
  )
  const minVolPoint = useMemo(
    () => ({ ...toChartPoint(minVolPortfolio), label: "Min Volatility" }),
    [minVolPortfolio],
  )
  const currentPoint = useMemo(
    () => ({ ...toChartPoint(currentPortfolio), label: "Your portfolio" }),
    [currentPortfolio],
  )

  const chartDomain = useMemo(() => {
    const allPoints: ChartPointWithLabel[] = [
      ...frontierData,
      minVolPoint,
      maxSharpePoint,
      currentPoint,
    ]

    return {
      x: getPaddedDomain(allPoints.map((point) => point.x)),
      y: getPaddedDomain(allPoints.map((point) => point.y)),
    }
  }, [currentPoint, frontierData, maxSharpePoint, minVolPoint])

  return (
    <ResponsiveContainer width="100%" height={380}>
      <ScatterChart margin={{ top: 24, right: 24, bottom: 52, left: 52 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.4} />
        <XAxis
          type="number"
          dataKey="x"
          name="Volatility"
          unit="%"
          domain={chartDomain.x}
          label={{
            value: "Annual Volatility (%)",
            position: "insideBottom",
            offset: -22,
            style: { fontSize: 12, fill: "hsl(var(--muted-foreground))" },
          }}
          tickFormatter={(value) => Number(value).toFixed(1)}
          tick={{ fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name="Return"
          unit="%"
          domain={chartDomain.y}
          label={{
            value: "Expected Annual Return (%)",
            angle: -90,
            offset: -50,
            style: { fontSize: 12, fill: "hsl(var(--muted-foreground))" },
          }}
          tickFormatter={(value) => Number(value).toFixed(1)}
          tick={{ fontSize: 11 }}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={<CustomTooltip />}
        />
        <Legend verticalAlign="top" height={36} />

        <Scatter
          name="Simulated portfolios"
          data={frontierData}
          fill="#94a3b8"
          opacity={0.4}
        />

        <Scatter
          name="Min Volatility"
          data={[minVolPoint]}
          fill="#3b82f6"
          shape={BlueMarker}
        />

        <Scatter
          name="Max Sharpe"
          data={[maxSharpePoint]}
          fill="#22c55e"
          shape={GreenMarker}
        />

        <Scatter
          name="Your portfolio"
          data={[currentPoint]}
          fill="#f59e0b"
          shape={AmberMarker}
        />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
