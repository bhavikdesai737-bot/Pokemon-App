import ListingRow, { type ListingRowData } from "./ListingRow"

type MarketplaceColumnProps = {
  marketplace: string
  listings: ListingRowData[]
  cheapest: number | null
  cheapestPrice: number | null
  savingsDifference: number | null
  groupGradedByCompany?: boolean
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

export default function MarketplaceColumn({
  marketplace,
  listings,
  cheapest,
  cheapestPrice,
  savingsDifference,
  groupGradedByCompany = false,
  formatMarketplaceName,
  formatPrice,
}: MarketplaceColumnProps) {
  const listingGroups = groupListingsByCompany(listings, groupGradedByCompany)
  const cheapestListing = listings.find((listing) => listing.price !== null && listing.price === cheapest)

  return (
    <div className="overflow-hidden rounded-3xl border border-white/10 bg-slate-950/60 shadow-xl shadow-black/20">
      <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.04] px-4 py-3">
        <div>
          <h3 className="text-lg font-black text-white">{formatMarketplaceName(marketplace)}</h3>
          <p className="text-xs text-slate-500">
            {listings.length} listing{listings.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Cheapest</p>
          <p className="font-black text-emerald-200">
            {cheapest === null ? "N/A" : formatPrice(cheapest, cheapestListing?.currency ?? "JPY")}
          </p>
        </div>
      </div>

      <div className="divide-y divide-white/10">
        {listingGroups.map((group) => (
          <div key={group.label}>
            {groupGradedByCompany && (
              <div className="border-b border-white/10 bg-slate-900/60 px-4 py-2">
                <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-200">
                  {group.label}
                </p>
              </div>
            )}
            {group.listings.map((listing) => (
              <ListingRow
                key={listing.id}
                listing={listing}
                marketplaceCheapest={cheapest}
                cheapestPrice={cheapestPrice}
                savingsDifference={savingsDifference}
                formatPrice={formatPrice}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
