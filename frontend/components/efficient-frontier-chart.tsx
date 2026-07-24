"use client"

import { useMemo } from "react"
import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts"

const frontierColor = "var(--muted-foreground)"
const maxSharpeColor = "var(--chart-3)"
const minVolatilityColor = "var(--chart-4)"
const currentPortfolioColor = "var(--chart-2)"
const axisColor = "var(--muted-foreground)"
const gridColor = "var(--border)"
const markerStrokeColor = "var(--background)"

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
  analyticalFrontierCurve: FrontierPoint[]
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
        stroke={markerStrokeColor}
        strokeWidth={2.5}
      />
    )
  }

const GreenMarker = makeMarker(maxSharpeColor)
const BlueMarker = makeMarker(minVolatilityColor)
const AmberMarker = makeMarker(currentPortfolioColor)

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
  analyticalFrontierCurve,
  maxSharpePortfolio,
  minVolPortfolio,
  currentPortfolio,
}: Props) {
  const frontierData = useMemo(
    () => frontierPoints.map(toChartPoint),
    [frontierPoints],
  )
  const analyticalFrontierData = useMemo(
    () =>
      analyticalFrontierCurve.map((point) => ({
        ...toChartPoint(point),
        label: "Analytical frontier",
      })),
    [analyticalFrontierCurve],
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
      ...analyticalFrontierData,
      minVolPoint,
      maxSharpePoint,
      currentPoint,
    ]

    return {
      x: getPaddedDomain(allPoints.map((point) => point.x)),
      y: getPaddedDomain(allPoints.map((point) => point.y)),
    }
  }, [
    analyticalFrontierData,
    currentPoint,
    frontierData,
    maxSharpePoint,
    minVolPoint,
  ])

  return (
    <ResponsiveContainer width="100%" height={380}>
      <ComposedChart margin={{ top: 24, right: 24, bottom: 52, left: 100 }}>
        <CartesianGrid
          stroke={gridColor}
          strokeDasharray="3 3"
          opacity={0.55}
        />
        <XAxis
          type="number"
          dataKey="x"
          name="Volatility"
          unit="%"
          domain={chartDomain.x}
          axisLine={{ stroke: gridColor }}
          tickLine={{ stroke: gridColor }}
          label={{
            value: "Annual Volatility (%)",
            position: "insideBottom",
            offset: -22,
            style: { fontSize: 12, fill: axisColor },
          }}
          tickFormatter={(value) => Number(value).toFixed(1)}
          tick={{ fontSize: 11, fill: axisColor }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name="Return"
          unit="%"
          domain={chartDomain.y}
          axisLine={{ stroke: gridColor }}
          tickLine={{ stroke: gridColor }}
          label={{
            value: "Expected Annual Return (%)",
            angle: -90,
            dx: -48,
            style: { fontSize: 12, fill: axisColor },
          }}
          tickFormatter={(value) => Number(value).toFixed(1)}
          tick={{ fontSize: 11, fill: axisColor }}
        />
        <Tooltip
          cursor={{ stroke: "var(--ring)", strokeDasharray: "3 3" }}
          content={<CustomTooltip />}
        />
        <Legend verticalAlign="top" height={36} />

        <Scatter
          name="Simulated portfolios"
          data={frontierData}
          fill={frontierColor}
          opacity={0.32}
        />

        <Line
          name="Analytical frontier"
          data={analyticalFrontierData}
          dataKey="y"
          stroke="#dc2626"
          strokeWidth={2.5}
          dot={false}
          activeDot={false}
          isAnimationActive={false}
          legendType="line"
        />

        <Scatter
          name="Min Volatility"
          data={[minVolPoint]}
          fill={minVolatilityColor}
          shape={BlueMarker}
        />

        <Scatter
          name="Max Sharpe"
          data={[maxSharpePoint]}
          fill={maxSharpeColor}
          shape={GreenMarker}
        />

        <Scatter
          name="Your portfolio"
          data={[currentPoint]}
          fill={currentPortfolioColor}
          shape={AmberMarker}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
