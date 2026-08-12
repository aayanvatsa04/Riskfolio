import { apiUrl } from "@/lib/api"

export interface TickerSearchResult {
  symbol: string
  name?: string | null
  exchange?: string | null
  quoteType?: string | null
  typeDisp?: string | null
  currency?: string | null
}

interface TickerSearchResponse {
  query: string
  results: TickerSearchResult[]
}

interface TrieNode {
  children: Map<string, TrieNode>
  symbols: Set<string>
}

function createTrieNode(): TrieNode {
  return {
    children: new Map(),
    symbols: new Set(),
  }
}

function normalizeSearchTerm(value: string) {
  return value.trim().toLocaleLowerCase()
}

function getSearchTokens(result: TickerSearchResult) {
  const values = [
    result.symbol,
    result.name ?? "",
    result.exchange ?? "",
    result.typeDisp ?? "",
    result.quoteType ?? "",
  ]
  const tokens = new Set<string>()

  values.forEach((value) => {
    const normalizedValue = normalizeSearchTerm(value)
    if (!normalizedValue) {
      return
    }

    tokens.add(normalizedValue)
    normalizedValue
      .split(/[\s,./()&-]+/)
      .map((token) => token.trim())
      .filter(Boolean)
      .forEach((token) => tokens.add(token))
  })

  return Array.from(tokens)
}

class TickerSearchTrie {
  private root = createTrieNode()
  private resultsBySymbol = new Map<string, TickerSearchResult>()

  insert(result: TickerSearchResult) {
    const symbol = result.symbol.trim().toUpperCase()

    if (!symbol) {
      return
    }

    const normalizedResult = {
      ...result,
      symbol,
    }
    this.resultsBySymbol.set(symbol, normalizedResult)

    getSearchTokens(normalizedResult).forEach((token) => {
      let currentNode = this.root

      for (const character of token) {
        const nextNode = currentNode.children.get(character) ?? createTrieNode()
        currentNode.children.set(character, nextNode)
        currentNode = nextNode
        currentNode.symbols.add(symbol)
      }
    })
  }

  search(query: string, limit: number) {
    const normalizedQuery = normalizeSearchTerm(query)
    if (!normalizedQuery) {
      return []
    }

    let currentNode = this.root
    for (const character of normalizedQuery) {
      const nextNode = currentNode.children.get(character)
      if (!nextNode) {
        return []
      }
      currentNode = nextNode
    }

    return Array.from(currentNode.symbols)
      .map((symbol) => this.resultsBySymbol.get(symbol))
      .filter((result): result is TickerSearchResult => Boolean(result))
      .sort((first, second) => {
        const firstSymbol = first.symbol.toLocaleLowerCase()
        const secondSymbol = second.symbol.toLocaleLowerCase()
        const firstName = first.name?.toLocaleLowerCase() ?? ""
        const secondName = second.name?.toLocaleLowerCase() ?? ""

        const firstExact =
          firstSymbol === normalizedQuery || firstName === normalizedQuery
        const secondExact =
          secondSymbol === normalizedQuery || secondName === normalizedQuery
        if (firstExact !== secondExact) {
          return firstExact ? -1 : 1
        }

        const firstStarts =
          firstSymbol.startsWith(normalizedQuery) ||
          firstName.startsWith(normalizedQuery)
        const secondStarts =
          secondSymbol.startsWith(normalizedQuery) ||
          secondName.startsWith(normalizedQuery)
        if (firstStarts !== secondStarts) {
          return firstStarts ? -1 : 1
        }

        return first.symbol.localeCompare(second.symbol)
      })
      .slice(0, limit)
  }
}

const tickerSearchTrie = new TickerSearchTrie()

export function searchCachedTickerResults(query: string, limit = 8) {
  return tickerSearchTrie.search(query, limit)
}

export async function fetchTickerSearchResults({
  query,
  limit = 8,
  signal,
}: {
  query: string
  limit?: number
  signal?: AbortSignal
}) {
  const normalizedQuery = query.trim()

  if (!normalizedQuery) {
    return []
  }

  const params = new URLSearchParams({
    q: normalizedQuery,
    limit: limit.toString(),
  })
  const response = await fetch(apiUrl(`ticker-search?${params}`), { signal })

  if (!response.ok) {
    const errorData = await response.json().catch(() => null)
    const message =
      typeof errorData?.detail === "string"
        ? errorData.detail
        : `Server error: ${response.status}`
    throw new Error(message)
  }

  const data = (await response.json()) as TickerSearchResponse
  data.results.forEach((result) => tickerSearchTrie.insert(result))

  return data.results
}
