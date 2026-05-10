"use client"

import { useState } from "react"
import Image from "next/image"
import CardHeader from "@/components/CardHeader"
import MarketplaceColumn from "@/components/MarketplaceColumn"

type MarketplaceResult = {
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

type SearchResult = {
  card_number: string
  japan: Record<string, MarketplaceResult | MarketplaceResult[]>
  graded?: Record<string, MarketplaceResult | MarketplaceResult[]>
  uk?: {
    ebay?: EbayPricingResult
  }
  raw?: EbayPriceSection
  psa?: EbayPriceSection
  ace?: EbayPriceSection
  error?: string
}

type EbayListing = {
  title: string | null
  price: number | null
  currency: string | null
  condition: string | null
  item_url: string | null
  image_url: string | null
  seller_username: string | null
  buying_options: string[]
}

type EbayPriceSection = {
  count: number
  min_price: number | null
  max_price: number | null
  average_price: number | null
  listings: EbayListing[]
  error?: string
}

type EbayPricingResult = {
  raw: EbayPriceSection
  psa: EbayPriceSection
  ace: EbayPriceSection
  error?: string
}

type MarketplaceCard = MarketplaceResult & {
  marketplace: string
  id: string
}

type SortOption = "lowest" | "highest" | "condition"
type ListingTab = "raw" | "psa" | "ace"

const sortOptions: { value: SortOption; label: string }[] = [
  { value: "lowest", label: "Lowest price" },
  { value: "highest", label: "Highest price" },
  { value: "condition", label: "Best condition" },
]

const listingTabs: { value: ListingTab; label: string }[] = [
  { value: "raw", label: "Raw" },
  { value: "psa", label: "PSA" },
  { value: "ace", label: "ACE" },
]
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "")

async function apiFetch(path: string, init?: RequestInit) {
  if (!API_BASE_URL) {
    throw new Error(
      "Missing NEXT_PUBLIC_API_URL. Set it to your backend URL, for example https://pokemon-app-production-b738.up.railway.app."
    )
  }

  const url = `${API_BASE_URL}${path}`
  const method = init?.method ?? "GET"

  console.log(`[Pokemon API] ${method} ${url}`)

  try {
    const response = await fetch(url, init)
    console.log(`[Pokemon API] ${method} ${url} -> ${response.status}`)
    return response
  } catch (err) {
    console.error(`[Pokemon API] ${method} ${url} failed`, err)
    throw new Error(`Backend is offline or unreachable at ${API_BASE_URL}. Check NEXT_PUBLIC_API_URL and start the backend.`)
  }
}

async function responseBodyPreview(response: Response) {
  try {
    return await response.clone().text()
  } catch {
    return "<unable to read response body>"
  }
}

function formatMarketplaceName(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatPrice(price: number | null, currency: string | null) {
  if (price === null) {
    return "Unavailable"
  }

  if (currency === "USD") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(price / 100)
  }

  if (currency === "JPY") {
    return `¥${new Intl.NumberFormat("en-US").format(price)}`
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency ?? "USD",
    maximumFractionDigits: 2,
  }).format(price)
}

function normalizeCardNumber(value: string) {
  return value.trim().replace(/[\\/]/g, "-").replace(/\s+/g, "").toUpperCase()
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

function getGradeRank(listing: MarketplaceCard) {
  return typeof listing.grade === "number" ? 100 - listing.grade : 99
}

function getGradingCompany(listing: MarketplaceCard) {
  return listing.grading_company?.toUpperCase() ?? null
}

function matchesListingTab(listing: MarketplaceCard, tab: ListingTab) {
  const gradingCompany = getGradingCompany(listing)

  if (tab === "raw") {
    return listing.listing_type !== "graded" && !gradingCompany
  }

  if (
    tab === "psa" &&
    ["cardladder", "collectr"].includes(listing.marketplace) &&
    listing.listing_type === "graded"
  ) {
    return gradingCompany === "PSA" || !gradingCompany
  }

  return listing.listing_type === "graded" && gradingCompany === tab.toUpperCase()
}

function splitMarketplaceDataByTab(listings: MarketplaceCard[]) {
  return listingTabs.reduce<Record<ListingTab, MarketplaceCard[]>>(
    (dataByTab, tab) => {
      dataByTab[tab.value] = listings.filter((listing) => matchesListingTab(listing, tab.value))
      return dataByTab
    },
    { raw: [], psa: [], ace: [] }
  )
}

function getEbayConditionRank(condition: string | null | undefined) {
  if (!condition) {
    return 6
  }

  const normalizedCondition = condition.trim().toUpperCase()
  const conditionRanks: Record<string, number> = {
    A: 0,
    "A-": 1,
    B: 2,
    "B-": 3,
    C: 4,
    "N/A": 5,
    UNKNOWN: 6,
  }

  if (normalizedCondition in conditionRanks) {
    return conditionRanks[normalizedCondition]
  }
  if (normalizedCondition.includes("NEAR MINT") || normalizedCondition === "NM") {
    return 0
  }
  if (normalizedCondition.includes("EXCELLENT")) {
    return 1
  }
  if (normalizedCondition.includes("LIGHT")) {
    return 2
  }
  if (normalizedCondition.includes("PLAYED")) {
    return 3
  }
  if (normalizedCondition.includes("POOR") || normalizedCondition.includes("DAMAGED")) {
    return 4
  }

  return 5
}

function topEbayListings(section: EbayPriceSection, tab: ListingTab) {
  return [...(section.listings ?? [])]
    .filter((listing) => typeof listing.price === "number")
    .sort((a, b) => {
      if (tab === "raw") {
        const conditionDiff = getEbayConditionRank(a.condition) - getEbayConditionRank(b.condition)
        if (conditionDiff !== 0) {
          return conditionDiff
        }
      }

      return (a.price ?? Number.MAX_SAFE_INTEGER) - (b.price ?? Number.MAX_SAFE_INTEGER)
    })
    .slice(0, 5)
}

function getEbayPricing(result: SearchResult | null): EbayPricingResult | null {
  if (!result) {
    return null
  }

  if (result.uk?.ebay) {
    return result.uk.ebay
  }

  if (result.raw && result.psa && result.ace) {
    return {
      raw: result.raw,
      psa: result.psa,
      ace: result.ace,
      error: result.error,
    }
  }

  return null
}

type EbayMarketCardProps = {
  label: string
  tab: ListingTab
  section: EbayPriceSection
  formatPrice: (price: number | null, currency: string | null) => string
}

function EbayMarketCard({ label, tab, section, formatPrice }: EbayMarketCardProps) {
  const [expanded, setExpanded] = useState(false)
  const topListings = topEbayListings(section, tab)
  const visibleListings = expanded ? topListings : topListings.slice(0, 4)

  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-950/70 shadow-xl shadow-black/20">
      <div className="sticky top-0 z-10 border-b border-white/10 bg-slate-950/95 p-3 backdrop-blur">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white px-2 py-0.5 text-xs font-black shadow-lg shadow-black/20">
                <span className="text-[#e53238]">e</span>
                <span className="text-[#0064d2]">B</span>
                <span className="text-[#f5af02]">a</span>
                <span className="text-[#86b817]">y</span>
              </span>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">
                UK
              </p>
            </div>
            <h3 className="text-base font-black text-white">eBay UK {label}</h3>
            <p className="mt-0.5 text-[11px] text-slate-500">
              {section.count} listing{section.count === 1 ? "" : "s"}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-slate-500">Average</p>
            <p className="text-sm font-black text-indigo-200">{formatPrice(section.average_price, "GBP")}</p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-xl border border-emerald-300/20 bg-emerald-400/10 p-2">
            <p className="text-[10px] font-black uppercase tracking-widest text-emerald-200">Lowest</p>
            <p className="mt-0.5 text-sm font-black text-white">{formatPrice(section.min_price, "GBP")}</p>
          </div>
          <div className="rounded-xl border border-rose-300/20 bg-rose-400/10 p-2">
            <p className="text-[10px] font-black uppercase tracking-widest text-rose-200">Highest</p>
            <p className="mt-0.5 text-sm font-black text-white">{formatPrice(section.max_price, "GBP")}</p>
          </div>
        </div>
      </div>

      <div className="flex-1 divide-y divide-white/10">
        {section.error && (
          <div className="px-4 py-3 text-sm font-semibold text-amber-200">
            {section.error}
          </div>
        )}

        {topListings.length ? (
          visibleListings.map((listing, index) => (
            <div
              key={`${label}-${listing.item_url ?? index}`}
              className="group grid grid-cols-[44px_1fr] gap-2 px-3 py-2 transition hover:bg-white/[0.06]"
            >
              <div className="h-12 w-10 overflow-hidden rounded-xl border border-white/10 bg-slate-900">
                {listing.image_url ? (
                  <Image
                    src={listing.image_url}
                    alt={listing.title ?? "eBay listing"}
                    width={48}
                    height={56}
                    unoptimized
                    className="h-full w-full object-cover transition group-hover:scale-105"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-[9px] font-black uppercase tracking-wider text-slate-600">
                    eBay
                  </div>
                )}
              </div>
              <div className="min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-base font-black text-white">{formatPrice(listing.price, listing.currency)}</p>
                  <span className="shrink-0 rounded-full bg-indigo-400/15 px-2 py-1 text-[10px] font-black uppercase text-indigo-200">
                    #{index + 1}
                  </span>
                </div>
                <p className="mt-0.5 line-clamp-2 text-xs font-semibold text-slate-300">
                  {listing.title ?? "Untitled eBay listing"}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px] font-bold text-slate-500">
                  {listing.condition && (
                    <span className="rounded-full bg-white/5 px-2 py-1">{listing.condition}</span>
                  )}
                  {listing.seller_username && (
                    <span className="rounded-full bg-white/5 px-2 py-1">@{listing.seller_username}</span>
                  )}
                </div>
                {listing.item_url && (
                  <a
                    href={listing.item_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-flex rounded-full bg-indigo-300 px-3 py-1 text-xs font-black text-slate-950 transition hover:bg-indigo-200"
                  >
                    View Listing
                  </a>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className="px-4 py-8 text-center text-sm font-semibold text-slate-500">
            No eBay {label} listings found.
          </div>
        )}
      </div>

      {topListings.length > 4 && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="border-t border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-black text-indigo-200 transition hover:bg-white/[0.08] hover:text-indigo-100"
        >
          {expanded ? "View Less" : `View More (${topListings.length - 4})`}
        </button>
      )}
    </article>
  )
}

export default function Home() {
  const [card, setCard] = useState("155-XY-P")
  const [result, setResult] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sortOption, setSortOption] = useState<SortOption>("condition")
  const [activeTab, setActiveTab] = useState<ListingTab>("raw")

  async function search() {
    const normalizedCard = normalizeCardNumber(card)

    if (!normalizedCard) {
      setError("Enter a Pokemon card number to search.")
      setResult(null)
      return
    }

    setCard(normalizedCard)
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const healthRes = await apiFetch("/health")
      if (!healthRes.ok) {
        const body = await responseBodyPreview(healthRes)
        console.error("[Pokemon API] Backend healthcheck failed", {
          url: `${API_BASE_URL}/health`,
          status: healthRes.status,
          body,
        })
        throw new Error(`Backend healthcheck failed with status ${healthRes.status}.`)
      }

      const healthData = await healthRes.clone().json().catch(() => null)
      if (healthData?.status !== "healthy") {
        console.error("[Pokemon API] Backend healthcheck returned unexpected payload", {
          url: `${API_BASE_URL}/health`,
          status: healthRes.status,
          body: healthData,
        })
        throw new Error("Backend healthcheck returned an unexpected response.")
      }

      const res = await apiFetch(`/search/${encodeURIComponent(normalizedCard)}`)

      if (!res.ok) {
        throw new Error(`Search failed with status ${res.status}`)
      }

      const data: SearchResult = await res.json()
      console.log("Full search result", data)
      setResult(data)
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : "Something went wrong while searching.")
    } finally {
      setLoading(false)
    }
  }

  const marketplaces: MarketplaceCard[] = result
    ? Object.entries(result.japan).flatMap(([marketplace, details]) => {
        const listings = Array.isArray(details) ? details : [details]
        return listings.map((listing, index) => ({
          ...listing,
          marketplace,
          id: `${marketplace}-${listing.url ?? index}`,
        }))
      })
    : []
  const ebayPricing = getEbayPricing(result)
  const activeEbaySection = ebayPricing?.[activeTab] ?? null
  const marketplaceDataByTab = splitMarketplaceDataByTab(marketplaces)
  const activeMarketplaceData = activeTab === "raw" ? marketplaceDataByTab.raw : []
  const tabCounts = listingTabs.reduce<Record<ListingTab, number>>(
    (counts, tab) => {
      const japaneseCount = tab.value === "raw" ? marketplaceDataByTab.raw.length : 0
      counts[tab.value] = japaneseCount + (ebayPricing?.[tab.value]?.count ?? 0)
      return counts
    },
    { raw: 0, psa: 0, ace: 0 }
  )
  const cheapestPrice = activeMarketplaceData
    .map((listing) => listing.price)
    .filter((price): price is number => typeof price === "number")
    .reduce<number | null>((lowest, price) => (lowest === null || price < lowest ? price : lowest), null)
  const cheapestListing = activeMarketplaceData.find(
    (listing) => listing.price !== null && listing.price === cheapestPrice
  )
  const nextCheapestPrice =
    cheapestPrice === null
      ? null
      : [...new Set(
          activeMarketplaceData
            .map((listing) => listing.price)
            .filter((price): price is number => typeof price === "number")
        )]
          .sort((a, b) => a - b)
          .find((price) => price > cheapestPrice) ?? null
  const savingsDifference =
    cheapestPrice !== null && nextCheapestPrice !== null
      ? nextCheapestPrice - cheapestPrice
      : null
  const cardHero = marketplaces.find((listing) => listing.image_url) ?? marketplaces[0]
  const groupedMarketplaces = Object.entries(
    activeMarketplaceData.reduce<Record<string, MarketplaceCard[]>>((groups, listing) => {
      groups[listing.marketplace] = groups[listing.marketplace] ?? []
      groups[listing.marketplace].push(listing)
      return groups
    }, {})
  ).map(([marketplace, listings]) => {
    const marketplaceCheapest = listings
      .map((listing) => listing.price)
      .filter((price): price is number => typeof price === "number")
      .reduce<number | null>((lowest, price) => (lowest === null || price < lowest ? price : lowest), null)

    const sortedListings = [...listings].sort((a, b) => {
      if (sortOption === "condition") {
        if (activeTab !== "raw") {
          const gradeDiff = getGradeRank(a) - getGradeRank(b)
          if (gradeDiff !== 0) {
            return gradeDiff
          }
        }

        const conditionDiff = getConditionRank(a.condition_grade) - getConditionRank(b.condition_grade)
        if (conditionDiff !== 0) {
          return conditionDiff
        }
        return (a.price ?? Number.MAX_SAFE_INTEGER) - (b.price ?? Number.MAX_SAFE_INTEGER)
      }

      const aPrice = a.price ?? (sortOption === "lowest" ? Number.MAX_SAFE_INTEGER : -1)
      const bPrice = b.price ?? (sortOption === "lowest" ? Number.MAX_SAFE_INTEGER : -1)
      return sortOption === "lowest" ? aPrice - bPrice : bPrice - aPrice
    })

    return {
      marketplace,
      listings: sortedListings,
      cheapest: marketplaceCheapest,
    }
  })
  const visibleMarketplaceCards = groupedMarketplaces.length + (activeEbaySection ? 1 : 0)

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#1e3a8a_0,#020617_34%,#020617_100%)] px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <section className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-2xl shadow-black/40 backdrop-blur">
          <div className="border-b border-white/10 bg-gradient-to-r from-slate-900 via-slate-900 to-sky-950/60 p-6 sm:p-8">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-cyan-300">
              Pokemon Trading Dashboard
            </p>
            <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h1 className="text-4xl font-black tracking-tight sm:text-5xl">
                  Price scanner
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                  Track marketplace listings, condition grades, and live prices in one compact view.
                </p>
              </div>
              <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-3 text-sm text-cyan-100">
                {marketplaces.length ? `${marketplaces.length} live listings` : "Ready to search"}
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 p-4 sm:flex-row sm:p-6">
            <input
              className="min-h-12 flex-1 rounded-2xl border border-white/10 bg-slate-950/80 px-4 text-base font-semibold text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300 focus:ring-4 focus:ring-cyan-300/15"
              value={card}
              onChange={(e) => setCard(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  search()
                }
              }}
              placeholder="155/XY-P or 155-XY-P"
            />
            <button
              onClick={search}
              disabled={loading}
              className="min-h-12 rounded-2xl bg-gradient-to-r from-cyan-300 to-sky-400 px-7 font-bold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:-translate-y-0.5 hover:from-cyan-200 hover:to-sky-300 disabled:cursor-not-allowed disabled:from-slate-600 disabled:to-slate-600 disabled:text-slate-300"
            >
              {loading ? "Searching..." : "Search"}
            </button>
          </div>

          {error && (
            <div className="mt-4 rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}
        </section>

        {loading && (
          <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-3 shadow-xl shadow-black/30">
            {[1, 2, 3, 4, 5].map((item) => (
              <div
                key={item}
                className="mb-3 h-20 animate-pulse rounded-2xl border border-white/10 bg-gradient-to-r from-white/10 via-white/5 to-white/10 last:mb-0"
              />
            ))}
          </section>
        )}

        {!loading && result && (
          <section className="overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 shadow-2xl shadow-black/40">
            <CardHeader
              cardHero={cardHero}
              cardNumber={result.card_number}
              listingsCount={tabCounts[activeTab]}
              marketsCount={visibleMarketplaceCards}
              cheapestPrice={cheapestPrice}
              cheapestCurrency={cheapestListing?.currency ?? "JPY"}
              formatPrice={formatPrice}
            />

            <div className="flex flex-col gap-4 border-b border-white/10 p-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="grid w-full grid-cols-3 rounded-2xl border border-white/10 bg-slate-950/70 p-1 sm:w-auto">
                {listingTabs.map((tab) => (
                  <button
                    key={tab.value}
                    type="button"
                    onClick={() => setActiveTab(tab.value)}
                    className={`rounded-xl px-3 py-2 text-xs font-black transition sm:min-w-24 sm:px-4 ${
                      activeTab === tab.value
                        ? "bg-cyan-300 text-slate-950 shadow-lg shadow-cyan-500/20"
                        : "text-slate-400 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    {tab.label}
                    <span className="ml-2 text-[10px] opacity-70">{tabCounts[tab.value]}</span>
                  </button>
                ))}
              </div>

              {activeTab === "raw" && (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">
                  Sort listings
                </p>
                <div className="flex flex-wrap gap-2">
                  {sortOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setSortOption(option.value)}
                      className={`rounded-full px-4 py-2 text-xs font-bold transition hover:-translate-y-0.5 ${
                        sortOption === option.value
                          ? "bg-cyan-300 text-slate-950 shadow-lg shadow-cyan-500/20"
                          : "border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              )}
            </div>

            {visibleMarketplaceCards ? (
              <div
                className={`grid items-stretch gap-3 p-3 sm:p-4 ${
                  activeTab === "raw" ? "lg:grid-cols-3" : "lg:max-w-xl lg:grid-cols-1"
                }`}
              >
                {groupedMarketplaces.map(({ marketplace, listings, cheapest }) => (
                  <MarketplaceColumn
                    key={marketplace}
                    marketplace={marketplace}
                    listings={listings}
                    cheapest={cheapest}
                    cheapestPrice={cheapestPrice}
                    savingsDifference={savingsDifference}
                    groupGradedByCompany={activeTab !== "raw"}
                    compact
                    defaultVisibleCount={4}
                    formatMarketplaceName={formatMarketplaceName}
                    formatPrice={formatPrice}
                  />
                ))}
                {activeEbaySection && (
                  <EbayMarketCard
                    label={listingTabs.find((tab) => tab.value === activeTab)?.label ?? "Raw"}
                    tab={activeTab}
                    section={activeEbaySection}
                    formatPrice={formatPrice}
                  />
                )}
              </div>
            ) : (
              <div className="p-4">
                <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/50 px-5 py-10 text-center">
                  <p className="text-sm font-bold text-slate-300">No {activeTab.toUpperCase()} listings found.</p>
                  <p className="mt-2 text-xs text-slate-500">Try another tab or search a different card number.</p>
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  )
}
