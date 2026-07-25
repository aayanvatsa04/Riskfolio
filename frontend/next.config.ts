import type { NextConfig } from "next"
import path from "node:path"
import { loadEnvConfig } from "@next/env"

loadEnvConfig(
  path.resolve(process.cwd(), ".."),
  process.env.NODE_ENV === "development",
)

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
