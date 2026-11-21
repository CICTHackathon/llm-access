import type { Metadata } from "next"

import { db } from "@/lib/db"
import { requirePage } from "@/lib/session"
import { formatDateTime } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Shell } from "@/components/layout/shell"
import { DashboardHeader } from "@/components/pages/dashboard/dashboard-header"

export const metadata: Metadata = { title: "Audit log" }

export default async function AuditPage() {
  await requirePage("viewAudit")
  const entries = await db.auditEntry.findMany({ orderBy: { createdAt: "desc" }, take: 300 })
  return (
    <Shell>
      <DashboardHeader
        heading="Audit log"
        text="Administrative actions taken in this interface. Access decisions are in the PDP's hash-chained log."
      />
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Who</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="whitespace-nowrap">{formatDateTime(e.createdAt)}</TableCell>
                <TableCell>{e.actorEmail}</TableCell>
                <TableCell>
                  <Badge variant={e.ok ? "outline" : "destructive"}>{e.action}</Badge>
                </TableCell>
                <TableCell>
                  <code className="text-xs">{e.target}</code>
                </TableCell>
                <TableCell className="max-w-[360px] truncate text-xs text-muted-foreground" title={e.detail}>
                  {e.detail === "{}" ? "" : e.detail}
                </TableCell>
              </TableRow>
            ))}
            {entries.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  No administrative actions yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </Shell>
  )
}
