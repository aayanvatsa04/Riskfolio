"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BookOpen,
  Briefcase,
  Gauge,
  Plus,
  SlidersHorizontal,
  Trash2,
  TrendingUp,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { ThemeToggle } from "@/components/theme-toggle"
import { portfolioDb, type SavedPortfolio } from "@/lib/portfolio-db"
import {
  PORTFOLIO_DELETE_EVENT,
  PORTFOLIO_LIST_CHANGED_EVENT,
  PORTFOLIO_LOAD_EVENT,
  PORTFOLIO_NEW_EVENT,
} from "@/lib/portfolio-events"

const navItems = [
  {
    title: "Dashboard",
    href: "/",
    icon: Gauge,
  },
  {
    title: "Glossary",
    href: "/glossary",
    icon: BookOpen,
  },
  {
    title: "Settings",
    href: "/settings",
    icon: SlidersHorizontal,
  },
]

function portfolioSubtitle(portfolio: SavedPortfolio) {
  const tickers = portfolio.holdings.map((holding) => holding.ticker)
  const visibleTickers = tickers.slice(0, 3).join(", ")
  const overflow = tickers.length > 3 ? ` +${tickers.length - 3}` : ""

  return visibleTickers ? `${visibleTickers}${overflow}` : "No holdings"
}

function loadPortfolioFromSidebar(portfolioId: string) {
  window.dispatchEvent(
    new CustomEvent(PORTFOLIO_LOAD_EVENT, {
      detail: { portfolioId },
    }),
  )
}

function createPortfolioFromSidebar() {
  window.dispatchEvent(new Event(PORTFOLIO_NEW_EVENT))
}

function deletePortfolioFromSidebar(portfolioId: string) {
  window.dispatchEvent(
    new CustomEvent(PORTFOLIO_DELETE_EVENT, {
      detail: { portfolioId },
    }),
  )
}

export function AppSidebar() {
  const pathname = usePathname()
  const [savedPortfolios, setSavedPortfolios] = useState<SavedPortfolio[]>([])

  const refreshSavedPortfolios = useCallback(async () => {
    const portfolios = await portfolioDb.savedPortfolios
      .orderBy("lastAccessedAt")
      .reverse()
      .limit(8)
      .toArray()

    setSavedPortfolios(portfolios)
  }, [])

  useEffect(() => {
    void refreshSavedPortfolios()

    const handlePortfolioListChanged = () => {
      void refreshSavedPortfolios()
    }

    window.addEventListener(
      PORTFOLIO_LIST_CHANGED_EVENT,
      handlePortfolioListChanged,
    )

    return () => {
      window.removeEventListener(
        PORTFOLIO_LIST_CHANGED_EVENT,
        handlePortfolioListChanged,
      )
    }
  }, [refreshSavedPortfolios])

  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader className="p-2 group-data-[collapsible=icon]:p-1">
        <div className="flex items-center gap-1 group-data-[collapsible=icon]:flex-col">
          <SidebarMenu className="min-w-0 flex-1">
            <SidebarMenuItem>
              <SidebarMenuButton
                asChild
                tooltip="Riskfolio"
                size="lg"
                className="h-10 data-[slot=sidebar-menu-button]:p-1 group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:justify-center"
              >
                <Link href="/">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
                    <TrendingUp className="size-4" />
                  </span>
                  <span className="font-heading text-base group-data-[collapsible=icon]:hidden">
                    Riskfolio
                  </span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          <SidebarTrigger className="size-8 shrink-0" />
        </div>
      </SidebarHeader>

      <SidebarContent className="min-w-0">
        <SidebarGroup className="px-2 group-data-[collapsible=icon]:p-1">
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={pathname === item.href}
                    tooltip={item.title}
                  >
                    <Link href={item.href}>
                      <item.icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator className="group-data-[collapsible=icon]:hidden" />

        <SidebarGroup className="min-w-0 group-data-[collapsible=icon]:hidden">
          <SidebarGroupLabel>Saved Portfolios</SidebarGroupLabel>
          <SidebarGroupAction
            title="New portfolio"
            onClick={createPortfolioFromSidebar}
          >
            <Plus />
            <span className="sr-only">New portfolio</span>
          </SidebarGroupAction>
          <SidebarGroupContent className="min-w-0 overflow-x-hidden">
            <SidebarMenu>
              {savedPortfolios.length > 0 ? (
                savedPortfolios.map((portfolio) => (
                  <SidebarMenuItem key={portfolio.id}>
                    <SidebarMenuButton
                      asChild
                      className="h-auto min-w-0 items-start py-2"
                    >
                      <Link
                        className="min-w-0 max-w-full"
                        href={`/?portfolio=${encodeURIComponent(portfolio.id)}`}
                        onClick={() => loadPortfolioFromSidebar(portfolio.id)}
                      >
                        <Briefcase className="mt-0.5" />
                        <span className="min-w-0">
                          <span className="block truncate">
                            {portfolio.name}
                          </span>
                          <span className="block truncate text-xs font-normal text-sidebar-foreground/60">
                            {portfolioSubtitle(portfolio)}
                          </span>
                        </span>
                      </Link>
                    </SidebarMenuButton>
                    <SidebarMenuAction
                      showOnHover
                      title="Delete portfolio"
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        if (
                          window.confirm(
                            `Delete "${portfolio.name}" from saved portfolios?`,
                          )
                        ) {
                          deletePortfolioFromSidebar(portfolio.id)
                        }
                      }}
                    >
                      <Trash2 />
                      <span className="sr-only">Delete {portfolio.name}</span>
                    </SidebarMenuAction>
                  </SidebarMenuItem>
                ))
              ) : (
                <SidebarMenuItem>
                  <div className="px-2 py-1.5 text-xs text-sidebar-foreground/55">
                    No saved portfolios yet.
                  </div>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-2 group-data-[collapsible=icon]:p-1">
        <div className="flex items-center justify-between gap-2 px-1 py-1 group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
          <span className="text-xs text-sidebar-foreground/60 group-data-[collapsible=icon]:hidden">
            Theme
          </span>
          <ThemeToggle />
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
