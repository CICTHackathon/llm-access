import { Skeleton } from "@/components/ui/skeleton"
import { Shell } from "@/components/layout/shell"

export default function Loading() {
  return (
    <Shell>
      <Skeleton className="h-10 w-64" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-72" />
    </Shell>
  )
}
