"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { LoginForm } from "@/components/login-form"
import { useSupabaseAuth } from "@/hooks/use-supabase-auth"

export function LoginPageClient() {
  const router = useRouter()
  const { isConfigured, isLoading, signInWithGoogle, user } = useSupabaseAuth()
  const [error, setError] = useState<string | null>(null)
  const [isSigningIn, setIsSigningIn] = useState(false)

  useEffect(() => {
    if (user) {
      router.replace("/")
    }
  }, [router, user])

  const handleGoogleSignIn = async () => {
    setError(null)

    if (!isConfigured) {
      setError("Supabase is not configured for this environment.")
      return
    }

    setIsSigningIn(true)
    const nextError = await signInWithGoogle()

    if (nextError) {
      setError(nextError)
      setIsSigningIn(false)
    }
  }

  return (
    <LoginForm
      error={error}
      isLoading={isLoading || isSigningIn}
      onGoogleSignIn={handleGoogleSignIn}
    />
  )
}
