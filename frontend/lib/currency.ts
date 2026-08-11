type CurrencyFormatOptions = {
  maximumFractionDigits?: number
  notation?: "standard" | "scientific" | "engineering" | "compact"
}

function normalizeCurrency(currency?: string | null) {
  const normalized = currency?.trim()
  if (!normalized) {
    return "USD"
  }
  if (
    normalized === normalized.toLowerCase() ||
    normalized === normalized.toUpperCase()
  ) {
    return normalized.toUpperCase()
  }
  return normalized
}

export function formatCurrencyValue(
  value: number,
  currency?: string | null,
  options: CurrencyFormatOptions = {},
) {
  const currencyCode = normalizeCurrency(currency)
  const { maximumFractionDigits = 2, notation = "standard" } = options

  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      notation,
      maximumFractionDigits,
    }).format(value)
  } catch {
    return `${new Intl.NumberFormat("en-US", {
      notation,
      maximumFractionDigits,
    }).format(value)} ${currencyCode}`
  }
}
