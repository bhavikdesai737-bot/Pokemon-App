import Image from "next/image"

type CardHeaderListing = {
  name: string | null
  image_url?: string | null
}

type CardHeaderProps = {
  cardHero: CardHeaderListing | undefined
  cardNumber: string
  listingsCount: number
  marketsCount: number
  cheapestPrice: number | null
  cheapestCurrency: string | null
  formatPrice: (price: number | null, currency: string | null) => string
}

export default function CardHeader({
  cardHero,
  cardNumber,
  listingsCount,
  marketsCount,
  cheapestPrice,
  cheapestCurrency,
  formatPrice,
}: CardHeaderProps) {
  return (
    <div className="grid gap-6 border-b border-white/10 bg-gradient-to-br from-white/[0.06] to-cyan-400/[0.03] p-5 md:grid-cols-[180px_1fr] md:p-6">
      <div className="mx-auto h-64 w-44 overflow-hidden rounded-3xl border border-white/10 bg-slate-950 shadow-2xl shadow-black/40 md:mx-0">
        {cardHero?.image_url ? (
          <Image
            src={cardHero.image_url}
            alt={cardHero.name ?? cardNumber}
            width={176}
            height={256}
            unoptimized
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-slate-800 to-slate-950 text-xs font-black uppercase tracking-widest text-slate-500">
            No image
          </div>
        )}
      </div>

      <div className="flex flex-col justify-between gap-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-300">
            Marketplace comparison
          </p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-white">
            {cardHero?.name ?? "Pokemon card"}
          </h2>
          <p className="mt-2 text-lg font-semibold text-slate-400">{cardNumber}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm sm:flex">
          <div className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3">
            <p className="text-slate-500">Listings</p>
            <p className="text-lg font-bold">{listingsCount}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3">
            <p className="text-slate-500">Markets</p>
            <p className="text-lg font-bold">{marketsCount}</p>
          </div>
          <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3">
            <p className="text-emerald-200/80">Best overall</p>
            <p className="text-lg font-bold text-emerald-200">
              {cheapestPrice === null ? "N/A" : formatPrice(cheapestPrice, cheapestCurrency)}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
