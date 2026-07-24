"use client"

import { AppSidebar } from "@/components/app-sidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

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
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/88 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/72 md:hidden">
          <SidebarTrigger />
          <span className="font-heading text-sm">Riskfolio</span>
        </header>
        {children}
      </SidebarInset>
    </SidebarProvider>
  )
}
