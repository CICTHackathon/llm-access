import type { Metadata } from "next"
import Link from "next/link"

import { db } from "@/lib/db"
import { listDecisions } from "@/lib/pdp"
import { requirePage } from "@/lib/session"
import { cn } from "@/lib/utils"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { DecisionsTable } from "@/components/decisions/decisions-table"
import { Shell } from "@/components/layout/shell"
import { DashboardHeader } from "@/components/pages/dashboard/dashboard-header"
import { SourceBanner } from "@/components/source-banner"

export const metadata: Metadata = { title: "Decisions" }

type Search = { door?: string; uid?: string; effect?: string }

export default async function DecisionsPage({ searchParams }: { searchParams: Search }) {
  await requirePage("viewDecisions")
  const door = searchParams.door?.trim() || undefined
  const uid = searchParams.uid?.trim() || undefined
  const effect = searchParams.effect === "permit" || searchParams.effect === "deny" ? searchParams.effect : undefined

  const [result, devices] = await Promise.all([
    listDecisions({ limit: 500, door, uid }),
    db.device.findMany({ where: { kind: "gateway" }, select: { door: true }, orderBy: { door: "asc" } }),
  ])
  const doors = [...new Set(devices.map((d) => d.door).filter(Boolean))] as string[]
  const rows = effect ? result.data.filter((d) => d.effect === effect) : result.data

  return (
    <Shell>
      <DashboardHeader heading="Decisions" text="Every access request the gateways sent, newest first." />
      <SourceBanner source={result.source} error={result.error} />
      <form className="flex flex-wrap items-end gap-3 px-2" method="get">
        <label className="grid gap-1 text-sm">
          Door
          <select name="door" defaultValue={door ?? ""} className="h-10 rounded-md border bg-background px-3 text-sm">
            <option value="">All doors</option>
            {doors.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          Effect
          <select name="effect" defaultValue={effect ?? ""} className="h-10 rounded-md border bg-background px-3 text-sm">
            <option value="">Permit and deny</option>
            <option value="permit">Permit</option>
            <option value="deny">Deny</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          Card UID
          <Input name="uid" defaultValue={uid ?? ""} placeholder="0xa1b2c3d4" className="w-44" />
        </label>
        <Button type="submit">Filter</Button>
        {(door || uid || effect) && (
          <Link href="/dashboard/decisions" className={cn(buttonVariants({ variant: "ghost" }))}>
            Clear
          </Link>
        )}
      </form>
      <DecisionsTable data={rows} title={`${rows.length} decisions`} />
    </Shell>
  )
}
