import { useState } from "react"
import ListingRow, { type ListingRowData } from "./ListingRow"

type MarketplaceColumnProps = {
  marketplace: string
  listings: ListingRowData[]
  cheapest: number | null
  cheapestPrice: number | null
  savingsDifference: number | null
  groupGradedByCompany?: boolean
  compact?: boolean
  defaultVisibleCount?: number
  formatMarketplaceName: (value: string) => string
  formatPrice: (price: number | null, currency: string | null) => string
}

function getGradingCompanyGroupLabel(listing: ListingRowData) {
  if (listing.listing_type !== "graded") {
    return "Raw listings"
  }

  const company = listing.grading_company?.toUpperCase()
  if (company) {
    return `${company} graded`
  }
  return "Graded"
}

function groupListingsByCompany(listings: ListingRowData[], groupGradedByCompany: boolean) {
  if (!groupGradedByCompany) {
    return [{ label: "Listings", listings }]
  }

  const groups = listings.reduce<Record<string, ListingRowData[]>>((acc, listing) => {
    const label = getGradingCompanyGroupLabel(listing)
    acc[label] = acc[label] ?? []
    acc[label].push(listing)
    return acc
  }, {})

  return Object.entries(groups)
    .map(([label, groupedListings]) => ({ label, listings: groupedListings }))
    .sort((a, b) => a.label.localeCompare(b.label))
}

function getConditionRank(condition: string | null | undefined) {
  if (!condition) {
    return 5
  }

  const ranks: Record<string, number> = {
    A: 0,
    "A-": 1,
    B: 2,
    "B-": 3,
    C: 4,
    "N/A": 5,
    UNKNOWN: 6,
  }

  return ranks[condition.toUpperCase()] ?? 6
}

function getBestCondition(listings: ListingRowData[]) {
  const bestListing = [...listings]
    .filter((listing) => listing.listing_type !== "graded")
    .sort((a, b) => getConditionRank(a.condition_grade) - getConditionRank(b.condition_grade))[0]

  return bestListing?.condition_grade ?? "N/A"
}

export default function MarketplaceColumn({
  marketplace,
  listings,
  cheapest,
  cheapestPrice,
  savingsDifference,
  groupGradedByCompany = false,
  compact = false,
  defaultVisibleCount = 4,
  formatMarketplaceName,
  formatPrice,
}: MarketplaceColumnProps) {
  const [expanded, setExpanded] = useState(false)
  const visibleCount = expanded ? listings.length : defaultVisibleCount
  const listingGroups = groupListingsByCompany(listings, groupGradedByCompany)
  const cheapestListing = listings.find((listing) => listing.price !== null && listing.price === cheapest)
  const bestCondition = getBestCondition(listings)

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-950/60 shadow-xl shadow-black/20">
      <div className="sticky top-0 z-10 flex items-start justify-between gap-2 border-b border-white/10 bg-slate-950/95 px-3 py-2 backdrop-blur">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-cyan-300/15 text-xs font-black text-cyan-200">
              {formatMarketplaceName(marketplace).slice(0, 2).toUpperCase()}
            </span>
            <h3 className={`${compact ? "text-base" : "text-lg"} truncate font-black text-white`}>
              {formatMarketplaceName(marketplace)}
            </h3>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            {listings.length} listing{listings.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[10px] text-slate-500">Cheapest</p>
          <p className="text-sm font-black text-emerald-200">
            {cheapest === null ? "N/A" : formatPrice(cheapest, cheapestListing?.currency ?? "JPY")}
          </p>
          <p className="mt-1 text-[10px] font-bold text-cyan-200">Best {bestCondition}</p>
        </div>
      </div>

      <div className="flex-1 divide-y divide-white/10">
        {listingGroups.map((group) => (
          <div key={group.label}>
            {groupGradedByCompany && (
              <div className="border-b border-white/10 bg-slate-900/60 px-3 py-1.5">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cyan-200">
                  {group.label}
                </p>
              </div>
            )}
            {group.listings.slice(0, visibleCount).map((listing) => (
              <ListingRow
                key={listing.id}
                listing={listing}
                marketplaceCheapest={cheapest}
                cheapestPrice={cheapestPrice}
                savingsDifference={savingsDifference}
                formatPrice={formatPrice}
                compact={compact}
              />
            ))}
          </div>
        ))}
      </div>

      {listings.length > defaultVisibleCount && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="border-t border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-black text-cyan-200 transition hover:bg-white/[0.08] hover:text-cyan-100"
        >
          {expanded ? "View Less" : `View More (${listings.length - defaultVisibleCount})`}
        </button>
      )}
    </div>
  )
}
