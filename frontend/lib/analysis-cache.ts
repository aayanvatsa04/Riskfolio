import {
  portfolioDb,
  type AnalysisCacheType,
  type CachedAnalysisResponse,
} from "@/lib/portfolio-db"

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`
  }

  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>

    return `{${Object.keys(value)
      .sort()
      .filter((key) => record[key] !== undefined)
      .map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`)
      .join(",")}}`
  }

  return JSON.stringify(value)
}

export function getAnalysisCacheKey(
  analysisType: AnalysisCacheType,
  request: unknown,
) {
  return `${analysisType}:${stableStringify(request)}`
}

export async function readCachedAnalysisResponse<T>(
  analysisType: AnalysisCacheType,
  request: unknown,
): Promise<(CachedAnalysisResponse & { response: T }) | null> {
  const cacheKey = getAnalysisCacheKey(analysisType, request)
  const cached = await portfolioDb.analysisResponses.get(cacheKey)

  if (!cached || cached.analysisType !== analysisType) {
    return null
  }

  return cached as CachedAnalysisResponse & { response: T }
}

export async function writeCachedAnalysisResponse(
  analysisType: AnalysisCacheType,
  request: unknown,
  response: unknown,
) {
  const cacheKey = getAnalysisCacheKey(analysisType, request)

  await portfolioDb.analysisResponses.put({
    cacheKey,
    analysisType,
    response,
    fetchedAt: new Date().toISOString(),
  })
}
