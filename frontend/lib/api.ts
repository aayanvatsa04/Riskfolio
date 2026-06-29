const DEFAULT_API_ORIGIN = "http://localhost:8000"

function joinUrl(origin: string, path: string) {
  const normalizedOrigin = origin.replace(/\/+$/, "")
  const normalizedPath = path.replace(/^\/+|\/+$/g, "")

  if (!normalizedPath) {
    return normalizedOrigin
  }

  return `${normalizedOrigin}/${normalizedPath}`
}

function isAbsoluteUrl(value: string) {
  return /^https?:\/\//i.test(value)
}

function getApiBaseUrl() {
  const origin = process.env.NEXT_PUBLIC_ORIGIN?.trim()
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? ""

  if (origin) {
    return joinUrl(origin, apiBaseUrl)
  }

  if (isAbsoluteUrl(apiBaseUrl)) {
    return apiBaseUrl.replace(/\/+$/, "")
  }

  return joinUrl(DEFAULT_API_ORIGIN, apiBaseUrl)
}

export const apiBaseUrl = getApiBaseUrl()
