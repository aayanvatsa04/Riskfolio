import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

import { getSupabaseServerClient } from "@/lib/supabase/server"

function getPublicOrigin(request: NextRequest, requestUrl: URL) {
  const forwardedHost = request.headers.get("x-forwarded-host")
  const forwardedProto = request.headers.get("x-forwarded-proto")

  if (forwardedHost) {
    return `${forwardedProto ?? "https"}://${forwardedHost}`
  }

  const host = request.headers.get("host")

  if (host) {
    return `${forwardedProto ?? requestUrl.protocol.replace(":", "")}://${host}`
  }

  return requestUrl.origin
}

function getSafeRedirectPath(requestUrl: URL) {
  const next = requestUrl.searchParams.get("next")

  if (!next?.startsWith("/") || next.startsWith("//")) {
    return "/"
  }

  return next
}

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get("code")
  const next = getSafeRedirectPath(requestUrl)

  if (code) {
    const supabase = await getSupabaseServerClient()
    await supabase?.auth.exchangeCodeForSession(code)
  }

  return NextResponse.redirect(
    new URL(next, getPublicOrigin(request, requestUrl)),
  )
}
