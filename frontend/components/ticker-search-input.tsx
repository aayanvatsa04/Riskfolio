"use client"

import { useEffect, useId, useRef, useState } from "react"
import { Building2, Loader2, Search } from "lucide-react"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover"
import {
  fetchTickerSearchResults,
  searchCachedTickerResults,
  type TickerSearchResult,
} from "@/lib/ticker-search"

const SEARCH_DEBOUNCE_MS = 180
const SEARCH_LIMIT = 8

function normalizeSymbol(value: string) {
  return value.trim().toUpperCase()
}

function getResultSubtitle(result: TickerSearchResult) {
  return [result.exchange, result.typeDisp ?? result.quoteType, result.currency]
    .filter(Boolean)
    .join(" - ")
}

export function TickerSearchInput({
  value,
  companyName,
  exchange,
  quoteCurrency,
  onChange,
  onSelect,
}: {
  value: string
  companyName?: string | null
  exchange?: string | null
  quoteCurrency?: string | null
  onChange: (ticker: string) => void
  onSelect: (result: TickerSearchResult) => void
}) {
  const listboxId = useId()
  const [query, setQuery] = useState(value)
  const [isOpen, setIsOpen] = useState(false)
  const [results, setResults] = useState<TickerSearchResult[]>([])
  const [activeResultIndex, setActiveResultIndex] = useState(-1)
  const [isLoading, setIsLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const popoverContentRef = useRef<HTMLDivElement | null>(null)
  const isSelectingRef = useRef(false)

  useEffect(() => {
    setQuery(value)
  }, [value])

  useEffect(() => {
    const trimmedQuery = query.trim()

    if (!isOpen || !trimmedQuery) {
      setResults([])
      setActiveResultIndex(-1)
      setIsLoading(false)
      setSearchError(null)
      return
    }

    const cachedResults = searchCachedTickerResults(trimmedQuery, SEARCH_LIMIT)
    if (cachedResults.length > 0) {
      setResults(cachedResults)
      setActiveResultIndex(0)
    }

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setIsLoading(true)
      setSearchError(null)

      void fetchTickerSearchResults({
        query: trimmedQuery,
        limit: SEARCH_LIMIT,
        signal: controller.signal,
      })
        .then((freshResults) => {
          setResults(freshResults)
          setActiveResultIndex(freshResults.length > 0 ? 0 : -1)
        })
        .catch((error) => {
          if (controller.signal.aborted) {
            return
          }

          setSearchError(
            error instanceof Error
              ? error.message
              : "Unable to search symbols.",
          )
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsLoading(false)
          }
        })
    }, SEARCH_DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [isOpen, query])

  useEffect(() => {
    if (results.length === 0) {
      setActiveResultIndex(-1)
      return
    }

    setActiveResultIndex((currentIndex) =>
      currentIndex >= 0 && currentIndex < results.length ? currentIndex : 0,
    )
  }, [results])

  useEffect(() => {
    if (!isOpen || activeResultIndex < 0) {
      return
    }

    document
      .getElementById(`${listboxId}-option-${activeResultIndex}`)
      ?.scrollIntoView({ block: "nearest" })
  }, [activeResultIndex, isOpen, listboxId])

  const commitManualQuery = () => {
    const symbol = normalizeSymbol(query)

    setQuery(symbol)
    setIsOpen(false)
    setActiveResultIndex(-1)
    if (symbol !== normalizeSymbol(value)) {
      onChange(symbol)
    }
  }

  const handleSelect = (result: TickerSearchResult) => {
    isSelectingRef.current = true
    setQuery(result.symbol)
    setIsOpen(false)
    setActiveResultIndex(-1)
    onSelect(result)
    window.setTimeout(() => {
      isSelectingRef.current = false
    }, 0)
  }

  const showSelectedMetadata =
    Boolean(companyName) && normalizeSymbol(query) === normalizeSymbol(value)
  const activeResult =
    activeResultIndex >= 0 ? results[activeResultIndex] : undefined
  const activeDescendant = activeResult
    ? `${listboxId}-option-${activeResultIndex}`
    : undefined

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverAnchor asChild>
        <InputGroup className="w-full min-w-0 overflow-hidden">
          {showSelectedMetadata && (
            <InputGroupAddon
              align="inline-start"
              className="w-2/3 min-w-0 flex-none justify-start border-r px-2 text-left text-xs font-normal"
              title={[companyName, exchange, quoteCurrency]
                .filter(Boolean)
                .join(" - ")}
            >
              <span className="block w-full truncate text-left">
                {companyName}
              </span>
            </InputGroupAddon>
          )}
          <InputGroupInput
            role="combobox"
            aria-expanded={isOpen}
            aria-autocomplete="list"
            aria-controls={listboxId}
            aria-activedescendant={activeDescendant}
            placeholder="Search name or ticker"
            value={query}
            onFocus={() => setIsOpen(true)}
            onBlur={(event) => {
              const nextFocusedElement = event.relatedTarget
              if (
                nextFocusedElement instanceof Node &&
                popoverContentRef.current?.contains(nextFocusedElement)
              ) {
                return
              }

              window.setTimeout(() => {
                if (!isSelectingRef.current) {
                  commitManualQuery()
                }
              }, 120)
            }}
            onChange={(event) => {
              setQuery(event.target.value.toUpperCase())
              setIsOpen(true)
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault()
                setIsOpen(true)
                setActiveResultIndex((currentIndex) => {
                  if (results.length === 0) {
                    return -1
                  }

                  return currentIndex < 0
                    ? 0
                    : (currentIndex + 1) % results.length
                })
                return
              }

              if (event.key === "ArrowUp") {
                event.preventDefault()
                setIsOpen(true)
                setActiveResultIndex((currentIndex) => {
                  if (results.length === 0) {
                    return -1
                  }

                  return currentIndex <= 0
                    ? results.length - 1
                    : currentIndex - 1
                })
                return
              }

              if (event.key === "Enter") {
                event.preventDefault()
                if (isOpen && activeResult) {
                  handleSelect(activeResult)
                  return
                }

                commitManualQuery()
                return
              }

              if (event.key === "Escape") {
                event.preventDefault()
                setIsOpen(false)
                setActiveResultIndex(-1)
                setQuery(value)
              }
            }}
            className={`min-w-0 font-mono text-right uppercase md:px-2 ${
              showSelectedMetadata ? "ml-auto w-1/3 flex-none px-1.5" : "flex-1"
            }`}
          />
        </InputGroup>
      </PopoverAnchor>

      <PopoverContent
        ref={popoverContentRef}
        align="start"
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => event.preventDefault()}
        className="w-[32rem] max-w-[calc(100vw-2rem)] p-0"
      >
        <div
          id={listboxId}
          role="listbox"
          className="flex max-h-80 min-w-0 flex-col overflow-y-auto p-1"
        >
          {isLoading && results.length === 0 && (
            <div className="flex items-center gap-2 px-3 py-3 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Searching Yahoo Finance
            </div>
          )}

          {!isLoading && searchError && results.length === 0 && (
            <div className="px-3 py-3 text-sm text-destructive">
              {searchError}
            </div>
          )}

          {!isLoading &&
            !searchError &&
            query.trim() &&
            results.length === 0 && (
              <div className="flex items-center gap-2 px-3 py-3 text-sm text-muted-foreground">
                <Search className="size-4" />
                No matching symbols
              </div>
            )}

          {results.map((result, index) => {
            const subtitle = getResultSubtitle(result)
            const isActive = index === activeResultIndex

            return (
              <button
                id={`${listboxId}-option-${index}`}
                key={result.symbol}
                type="button"
                role="option"
                aria-selected={isActive}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveResultIndex(index)}
                onClick={() => handleSelect(result)}
                className={`flex min-w-0 items-center gap-3 rounded-sm px-3 py-2 text-left text-sm outline-hidden hover:bg-accent focus-visible:bg-accent ${
                  isActive ? "bg-accent text-accent-foreground" : ""
                }`}
              >
                <Building2 className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">
                    {result.name ?? result.symbol}
                  </span>
                  {subtitle && (
                    <span className="block truncate text-xs text-muted-foreground">
                      {subtitle}
                    </span>
                  )}
                </span>
                <span className="shrink-0 font-mono text-xs font-semibold">
                  {result.symbol}
                </span>
              </button>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}
