export const USER_SETTINGS_CHANGED_EVENT = "riskfolio:user-settings-changed"

const USER_SETTINGS_STORAGE_KEY = "riskfolio:user-settings"
const DEFAULT_PRICE_REFRESH_INTERVAL_MINUTES = 15

export const PRICE_REFRESH_INTERVAL_OPTIONS = [5, 15, 30, 60, 240] as const

export type PriceRefreshIntervalMinutes =
  (typeof PRICE_REFRESH_INTERVAL_OPTIONS)[number]

export type UserSettings = {
  priceRefreshIntervalMinutes: PriceRefreshIntervalMinutes
}

export const DEFAULT_USER_SETTINGS: UserSettings = {
  priceRefreshIntervalMinutes: DEFAULT_PRICE_REFRESH_INTERVAL_MINUTES,
}

function isPriceRefreshInterval(
  value: unknown,
): value is PriceRefreshIntervalMinutes {
  return (
    typeof value === "number" &&
    PRICE_REFRESH_INTERVAL_OPTIONS.includes(
      value as PriceRefreshIntervalMinutes,
    )
  )
}

function parseStoredSettings(rawValue: string | null): UserSettings {
  if (!rawValue) {
    return DEFAULT_USER_SETTINGS
  }

  try {
    const parsed = JSON.parse(rawValue) as Partial<UserSettings>

    return {
      priceRefreshIntervalMinutes: isPriceRefreshInterval(
        parsed.priceRefreshIntervalMinutes,
      )
        ? parsed.priceRefreshIntervalMinutes
        : DEFAULT_USER_SETTINGS.priceRefreshIntervalMinutes,
    }
  } catch {
    return DEFAULT_USER_SETTINGS
  }
}

export function getUserSettings(): UserSettings {
  if (typeof window === "undefined") {
    return DEFAULT_USER_SETTINGS
  }

  return parseStoredSettings(
    window.localStorage.getItem(USER_SETTINGS_STORAGE_KEY),
  )
}

export function saveUserSettings(settings: UserSettings) {
  if (typeof window === "undefined") {
    return
  }

  window.localStorage.setItem(
    USER_SETTINGS_STORAGE_KEY,
    JSON.stringify(settings),
  )
  window.dispatchEvent(new Event(USER_SETTINGS_CHANGED_EVENT))
}

export function updateUserSettings(patch: Partial<UserSettings>) {
  saveUserSettings({
    ...getUserSettings(),
    ...patch,
  })
}

export function getPriceRefreshIntervalMs(
  settings: UserSettings = getUserSettings(),
) {
  return settings.priceRefreshIntervalMinutes * 60 * 1000
}

export function formatPriceRefreshInterval(minutes: number) {
  if (minutes < 60) {
    return `${minutes} min`
  }

  const hours = minutes / 60
  return Number.isInteger(hours) ? `${hours} hr` : `${hours.toFixed(1)} hr`
}
