"use client"

import { useEffect, useRef } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar"

const EXTRA_LARGE_SCREEN_MEDIA_QUERY = "(min-width: 1280px)"

function ResponsiveSidebarState() {
  const { setOpen } = useSidebar()
  const setOpenRef = useRef(setOpen)

  useEffect(() => {
    setOpenRef.current = setOpen
  }, [setOpen])

  useEffect(() => {
    const mediaQuery = window.matchMedia(EXTRA_LARGE_SCREEN_MEDIA_QUERY)
    const syncSidebarState = () => setOpenRef.current(mediaQuery.matches)

    syncSidebarState()
    mediaQuery.addEventListener("change", syncSidebarState)

    return () => mediaQuery.removeEventListener("change", syncSidebarState)
  }, [])

  return null
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "14.5rem",
          "--sidebar-width-icon": "2.75rem",
        } as React.CSSProperties
      }
    >
      <ResponsiveSidebarState />
      <AppSidebar />
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/88 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/72 md:hidden">
          <SidebarTrigger />
          <span className="font-heading text-sm">Riskfolio</span>
        </header>
        {children}
      </SidebarInset>
    </SidebarProvider>
  )
}
