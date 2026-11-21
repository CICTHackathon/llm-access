import Link from "next/link"

import { ROLE_DESCRIPTION, ROLE_LABEL } from "@/lib/roles"
import { requirePage } from "@/lib/session"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import { EmptyPlaceholder } from "@/components/empty-placeholder"
import { Icons } from "@/components/icons"

export default async function Forbidden() {
  const user = await requirePage("viewDashboard")
  return (
    <EmptyPlaceholder>
      <Icons.warning className="h-10 w-10 text-muted-foreground" />
      <EmptyPlaceholder.Title>Not available to your role</EmptyPlaceholder.Title>
      <EmptyPlaceholder.Description>
        You are signed in as {ROLE_LABEL[user.role]}. {ROLE_DESCRIPTION[user.role]} Ask an administrator if you need more access.
      </EmptyPlaceholder.Description>
      <Link href="/dashboard" className={cn(buttonVariants({ variant: "outline" }))}>
        Back to the overview
      </Link>
    </EmptyPlaceholder>
  )
}
