import Link from "next/link"

import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import { EmptyPlaceholder } from "@/components/empty-placeholder"
import { Icons } from "@/components/icons"

export default function NotFound() {
  return (
    <main className="container flex flex-1 items-center justify-center py-16">
      <EmptyPlaceholder className="w-full max-w-xl">
        <Icons.warning className="h-10 w-10 text-muted-foreground" />
        <EmptyPlaceholder.Title>Not found</EmptyPlaceholder.Title>
        <EmptyPlaceholder.Description>This page or device does not exist.</EmptyPlaceholder.Description>
        <Link href="/dashboard" className={cn(buttonVariants({ variant: "outline" }))}>
          Back to the dashboard
        </Link>
      </EmptyPlaceholder>
    </main>
  )
}
