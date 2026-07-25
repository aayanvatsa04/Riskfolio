import { Skeleton } from "@/components/ui/skeleton"

export default function Loading() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto w-full max-w-[1800px] px-4 py-6 md:px-6 lg:px-8">
        <div className="mb-6 border-b pb-6">
          <Skeleton className="mb-3 h-5 w-32" />
          <Skeleton className="h-12 w-64" />
          <Skeleton className="mt-3 h-5 w-full max-w-2xl" />
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(440px,0.95fr)_minmax(0,1.45fr)]">
          <div className="space-y-4 rounded-lg border bg-card p-6">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
          <div className="space-y-4 rounded-lg border bg-card p-6">
            <Skeleton className="h-6 w-56" />
            <Skeleton className="h-[320px] w-full" />
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
