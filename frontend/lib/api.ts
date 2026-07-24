const DEFAULT_API_ORIGIN = "http://localhost:8000"
const API_VERSION_PREFIX = "/api/v1"

function joinUrl(origin: string, path: string) {
  const normalizedOrigin = origin.replace(/\/+$/, "")
  const normalizedPath = path.replace(/^\/+|\/+$/g, "")

  if (!normalizedPath) {
    return normalizedOrigin
  }

  return `${normalizedOrigin}/${normalizedPath}`
}

function normalizeRelativePath(value: string) {
  const normalizedValue = value.replace(/^\/+|\/+$/g, "")

  if (!normalizedValue) {
    return ""
  }

  return `/${normalizedValue}`
}

function isAbsoluteUrl(value: string) {
  return /^https?:\/\//i.test(value)
}

function getApiBaseUrl() {
  const origin = process.env.NEXT_PUBLIC_ORIGIN?.trim()
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? ""

  if (isAbsoluteUrl(apiBaseUrl)) {
    return apiBaseUrl.replace(/\/+$/, "")
  }

  if (apiBaseUrl) {
    return normalizeRelativePath(apiBaseUrl)
  }

  if (origin) {
    return origin.replace(/\/+$/, "")
  }

  return DEFAULT_API_ORIGIN
}

export const apiBaseUrl = getApiBaseUrl()

export function apiUrl(path: string) {
  return joinUrl(apiBaseUrl, joinUrl(API_VERSION_PREFIX, path))
}
