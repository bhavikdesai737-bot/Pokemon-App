type ConditionBadgeProps = {
  condition: string | null | undefined
}

function getConditionBadgeClass(condition: string | null | undefined) {
  if (condition?.startsWith("PSA")) {
    return "border-violet-300/30 bg-violet-400/15 text-violet-200"
  }
  if (condition?.startsWith("ACE")) {
    return "border-fuchsia-300/30 bg-fuchsia-400/15 text-fuchsia-200"
  }

  switch (condition) {
    case "A":
      return "border-emerald-300/30 bg-emerald-400/15 text-emerald-200"
    case "A-":
      return "border-lime-300/30 bg-lime-400/15 text-lime-200"
    case "B":
      return "border-amber-300/30 bg-amber-400/15 text-amber-200"
    case "B-":
      return "border-orange-300/30 bg-orange-400/15 text-orange-200"
    case "C":
      return "border-rose-300/30 bg-rose-400/15 text-rose-200"
    default:
      return "border-slate-400/20 bg-slate-400/10 text-slate-300"
  }
}

export default function ConditionBadge({ condition }: ConditionBadgeProps) {
  return (
    <span
      className={`inline-flex min-w-16 justify-center rounded-full border px-3 py-1 text-xs font-black shadow-sm ${getConditionBadgeClass(condition)}`}
    >
      {condition ?? "N/A"}
    </span>
  )
}
