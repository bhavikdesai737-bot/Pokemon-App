"use client"

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export type PriceHistoryPoint = {
  timestamp: string | null
  marketplace: string
  price: number | null
  currency: string | null
  listing_type?: string | null
  grading_company?: string | null
}

type ListingTab = "raw" | "psa" | "ace"

type ChartRow = {
  timestamp: string
  label: string
  [marketplace: string]: string | number
}

type PriceHistoryChartProps = {
  history: PriceHistoryPoint[]
  activeTab: ListingTab
  formatMarketplaceName: (value: string) => string
  formatPrice: (price: number | null, currency: string | null) => string
}

const lineColors = ["#67e8f9", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#f472b6"]

function matchesTab(point: PriceHistoryPoint, tab: ListingTab) {
  const gradingCompany = point.grading_company?.toUpperCase() ?? null

  if (tab === "raw") {
    return point.listing_type !== "graded" && !gradingCompany
  }

  return point.listing_type === "graded" && gradingCompany === tab.toUpperCase()
}

function formatTimestamp(timestamp: string) {
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp))
}

function buildChartData(history: PriceHistoryPoint[], activeTab: ListingTab) {
  const marketplaceSet = new Set<string>()
  const rowsByTimestamp = new Map<string, ChartRow>()

  history
    .filter((point) => point.timestamp && typeof point.price === "number" && matchesTab(point, activeTab))
    .forEach((point) => {
      const timestamp = point.timestamp as string
      const marketplace = point.marketplace
      marketplaceSet.add(marketplace)

      const row = rowsByTimestamp.get(timestamp) ?? {
        timestamp,
        label: formatTimestamp(timestamp),
      }
      const currentPrice = typeof row[marketplace] === "number" ? row[marketplace] : null

      if (currentPrice === null || (point.price as number) < currentPrice) {
        row[marketplace] = point.price as number
      }

      rowsByTimestamp.set(timestamp, row)
    })

  return {
    marketplaces: [...marketplaceSet],
    data: [...rowsByTimestamp.values()].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    ),
  }
}

export default function PriceHistoryChart({
  history,
  activeTab,
  formatMarketplaceName,
  formatPrice,
}: PriceHistoryChartProps) {
  const { marketplaces, data } = buildChartData(history, activeTab)

  return (
    <div className="border-b border-white/10 bg-slate-950/30 p-4">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-300">
            Price history
          </p>
          <h3 className="mt-2 text-xl font-black text-white">Marketplace trend</h3>
        </div>
        <p className="text-xs text-slate-500">
          {data.length ? `${data.length} saved snapshots` : "No saved history for this tab yet"}
        </p>
      </div>

      {data.length ? (
        <div className="h-72 rounded-3xl border border-white/10 bg-slate-950/70 p-3 shadow-inner shadow-black/30 sm:h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 14, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis
                dataKey="label"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                axisLine={{ stroke: "#334155" }}
                tickLine={{ stroke: "#334155" }}
              />
              <YAxis
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                axisLine={{ stroke: "#334155" }}
                tickLine={{ stroke: "#334155" }}
                tickFormatter={(value) => `¥${new Intl.NumberFormat("en-US").format(value as number)}`}
              />
              <Tooltip
                contentStyle={{
                  background: "#020617",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: "16px",
                  color: "#e2e8f0",
                }}
                formatter={(value, name) => [
                  formatPrice(typeof value === "number" ? value : null, "JPY"),
                  formatMarketplaceName(String(name)),
                ]}
                labelStyle={{ color: "#67e8f9", fontWeight: 800 }}
              />
              {marketplaces.map((marketplace, index) => (
                <Line
                  key={marketplace}
                  type="monotone"
                  dataKey={marketplace}
                  name={marketplace}
                  stroke={lineColors[index % lineColors.length]}
                  strokeWidth={3}
                  dot={{ r: 3, strokeWidth: 2 }}
                  activeDot={{ r: 6 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/50 px-5 py-8 text-center">
          <p className="text-sm font-bold text-slate-300">No price history yet.</p>
          <p className="mt-2 text-xs text-slate-500">Run a few searches over time to build a trend line.</p>
        </div>
      )}
    </div>
  )
}
