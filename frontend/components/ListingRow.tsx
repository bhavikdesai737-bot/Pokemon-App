import Image from "next/image"
import ConditionBadge from "./ConditionBadge"

export type ListingRowData = {
  id: string
  marketplace?: string
  name: string | null
  price: number | null
  currency: string | null
  condition_grade?: string | null
  listing_type?: string | null
  grading_company?: string | null
  grade?: number | null
  in_stock?: boolean | null
  stock_status?: string | null
  url: string | null
  image_url?: string | null
}

type ListingRowProps = {
  listing: ListingRowData
  marketplaceCheapest: number | null
  cheapestPrice: number | null
  savingsDifference: number | null
  formatPrice: (price: number | null, currency: string | null) => string
}

function formatStockStatus(listing: ListingRowData) {
  if (listing.in_stock === true) {
    return "In stock"
  }
  if (listing.in_stock === false) {
    return "Sold out"
  }
  if (listing.stock_status) {
    return listing.stock_status.replace(/_/g, " ")
  }
  return "Unknown"
}

function getListingConditionLabel(listing: ListingRowData) {
  if (listing.listing_type === "graded" && listing.grading_company) {
    return `${listing.grading_company}${listing.grade ?? ""}`
  }
  if (listing.listing_type === "graded" && listing.grade !== null && listing.grade !== undefined) {
    return `GRADE ${listing.grade}`
  }

  return listing.condition_grade
}

export default function ListingRow({
  listing,
  marketplaceCheapest,
  cheapestPrice,
  savingsDifference,
  formatPrice,
}: ListingRowProps) {
  const isMarketplaceBest = listing.price !== null && listing.price === marketplaceCheapest
  const isBestOverall = listing.price !== null && listing.price === cheapestPrice

  return (
    <a
      href={listing.url ?? undefined}
      target={listing.url ? "_blank" : undefined}
      rel={listing.url ? "noreferrer" : undefined}
      className={`group grid grid-cols-[56px_72px_1fr] gap-3 px-4 py-3 transition hover:bg-white/[0.06] sm:grid-cols-[60px_76px_1fr_110px] sm:items-center ${
        isMarketplaceBest ? "bg-emerald-400/10 ring-1 ring-inset ring-emerald-300/30" : ""
      }`}
    >
      <div className="h-14 w-12 overflow-hidden rounded-xl border border-white/10 bg-slate-900">
        {listing.image_url ? (
          <Image
            src={listing.image_url}
            alt={listing.name ?? "Card image"}
            width={48}
            height={56}
            unoptimized
            className="h-full w-full object-cover transition group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-[9px] font-black uppercase tracking-wider text-slate-600">
            No img
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <ConditionBadge condition={getListingConditionLabel(listing)} />
        {isBestOverall && (
          <span className="w-fit rounded-full bg-emerald-300 px-2 py-1 text-[10px] font-black text-emerald-950 shadow-lg shadow-emerald-400/20">
            BEST DEAL
          </span>
        )}
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-xl font-black text-white">{formatPrice(listing.price, listing.currency)}</p>
          {isMarketplaceBest && (
            <span className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-wide text-emerald-200">
              lowest here
            </span>
          )}
        </div>
        <p className="mt-1 line-clamp-2 text-sm font-semibold text-slate-300">
          {listing.name ?? "Unknown card"}
        </p>
        <p className="mt-1 text-xs font-bold capitalize text-slate-500">
          {listing.marketplace?.replace(/_/g, " ") ?? "Marketplace"}
        </p>
        {isBestOverall && savingsDifference !== null && savingsDifference > 0 && (
          <p className="mt-1 text-xs font-bold text-emerald-200">
            Save {formatPrice(savingsDifference, listing.currency)} vs next
          </p>
        )}
      </div>

      <span
        className={`w-fit rounded-full px-3 py-1 text-xs font-bold capitalize sm:justify-self-end ${
          listing.in_stock
            ? "bg-emerald-400/15 text-emerald-200"
            : listing.in_stock === false
              ? "bg-rose-400/15 text-rose-200"
              : "bg-slate-400/15 text-slate-300"
        }`}
      >
        {formatStockStatus(listing)}
      </span>
    </a>
  )
}
