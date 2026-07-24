import type { NextConfig } from "next"
import fs from "node:fs"
import path from "node:path"

function loadRootPublicEnv() {
  const envPath = path.resolve(process.cwd(), "..", ".env")

  if (!fs.existsSync(envPath)) {
    return
  }

  const lines = fs.readFileSync(envPath, "utf8").split(/\r?\n/)
  for (const line of lines) {
    const trimmed = line.trim()

    if (!trimmed || trimmed.startsWith("#")) {
      continue
    }

    const separatorIndex = trimmed.indexOf("=")
    if (separatorIndex === -1) {
      continue
    }

    const key = trimmed.slice(0, separatorIndex).trim()
    const rawValue = trimmed.slice(separatorIndex + 1).trim()

    if (!key.startsWith("NEXT_PUBLIC_") || process.env[key] !== undefined) {
      continue
    }

    process.env[key] = rawValue.replace(/^['"]|['"]$/g, "")
  }
}

loadRootPublicEnv()

const nextConfig: NextConfig = {
  async rewrites() {
    if (process.env.NODE_ENV !== "development") {
      return []
    }

    return [
      {
        source: "/backend/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ]
  },
}

export default nextConfig
