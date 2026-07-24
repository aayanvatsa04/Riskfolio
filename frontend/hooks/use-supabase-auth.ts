"use client"

import { useCallback, useEffect, useMemo, useState } from "react"

import type { Session, SupabaseClient, User } from "@supabase/supabase-js"

import {
  getSupabaseBrowserClient,
  isSupabaseConfigured,
} from "@/lib/supabase/client"

type AuthState = {
  supabase: SupabaseClient | null
  session: Session | null
  user: User | null
  isConfigured: boolean
  isLoading: boolean
  signInWithGoogle: () => Promise<string | null>
  signOut: () => Promise<string | null>
}

export function useSupabaseAuth(): AuthState {
  const isConfigured = isSupabaseConfigured()
  const supabase = useMemo(() => getSupabaseBrowserClient(), [])
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(isConfigured)

  useEffect(() => {
    if (!supabase) {
      setIsLoading(false)
      return
    }

    let isMounted = true

    void supabase.auth.getSession().then(({ data }) => {
      if (!isMounted) {
        return
      }

      setSession(data.session)
      setIsLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      setIsLoading(false)
    })

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [supabase])

  const signInWithGoogle = useCallback(async () => {
    if (!supabase) {
      return "Supabase is not configured."
    }

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=/`,
      },
    })

    return error?.message ?? null
  }, [supabase])

  const signOut = useCallback(async () => {
    if (!supabase) {
      return null
    }

    const { error } = await supabase.auth.signOut()
    return error?.message ?? null
  }, [supabase])

  return {
    supabase,
    session,
    user: session?.user ?? null,
    isConfigured,
    isLoading,
    signInWithGoogle,
    signOut,
  }
}
