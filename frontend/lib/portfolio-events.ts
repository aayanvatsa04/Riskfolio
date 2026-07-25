"use client"

export const PORTFOLIO_LIST_CHANGED_EVENT = "riskfolio:portfolio-list-changed"
export const PORTFOLIO_LOAD_EVENT = "riskfolio:load-portfolio"
export const PORTFOLIO_NEW_EVENT = "riskfolio:new-portfolio"
export const PORTFOLIO_DELETE_EVENT = "riskfolio:delete-portfolio"

export function notifyPortfolioListChanged() {
  if (typeof window === "undefined") {
    return
  }

  window.dispatchEvent(new Event(PORTFOLIO_LIST_CHANGED_EVENT))
}
