import type { Metadata } from "next"
import Link from "next/link"

import { db } from "@/lib/db"
import { cameraApi, gatewayApi, iotMode } from "@/lib/iot"
import { getHealth, getIntegrity, listDecisions } from "@/lib/pdp"
import { can } from "@/lib/roles"
import { requirePage } from "@/lib/session"
import { decisionStats } from "@/lib/stats"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DecisionsChart } from "@/components/charts/decisions-chart"
import { DenyCodesChart } from "@/components/charts/deny-codes-chart"
import { DecisionsTable } from "@/components/decisions/decisions-table"
import { Shell } from "@/components/layout/shell"
import { DashboardHeader } from "@/components/pages/dashboard/dashboard-header"
import { SourceBanner } from "@/components/source-banner"
import { StatCard } from "@/components/stat-card"

export const metadata: Metadata = { title: "Overview" }

async function deviceSummary() {
  const devices = await db.device.findMany({ orderBy: { id: "asc" } })
  return Promise.all(
    devices.map(async (d) => {
      try {
        const status = d.kind === "gateway" ? await gatewayApi(d).status() : await cameraApi(d).status()
        return { id: d.id, kind: d.kind, door: d.door, online: true, detail: "door" in status ? `door ${status.door}` : `${status.fps} fps` }
      } catch {
        return { id: d.id, kind: d.kind, door: d.door, online: false, detail: "unreachable" }
      }
    })
  )
}

export default async function Overview() {
  const user = await requirePage("viewDashboard")
  const isAdmin = can(user.role, "manageIot")
  const [decisions, health, integrity, devices] = await Promise.all([
    listDecisions({ limit: 500 }),
    getHealth(),
    getIntegrity(),
    isAdmin ? deviceSummary() : Promise.resolve(null),
  ])
  const stats = decisionStats(decisions.data)

  return (
    <Shell>
      <DashboardHeader heading="Overview" text={`Welcome back, ${user.name}.`} />
      <SourceBanner source={decisions.source} error={decisions.error} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="Decisions" value={stats.total} hint="Most recent, up to 500" icon="decisions" />
        <StatCard title="Permitted" value={stats.permits} hint={`${100 - stats.denyRate}% of requests`} icon="permit" />
        <StatCard title="Denied" value={stats.denies} hint={`${stats.tightened} tightened by the agents`} icon="deny" />
        <StatCard title="Permit latency" value={`${stats.avgPermitLatencyMs} ms`} hint={`${stats.reviewed} reviewed by the agents`} icon="activity" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <DecisionsChart data={stats.byDay} />
        <DenyCodesChart data={stats.denyCodes} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Policy Decision Point</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Status">
              <Badge variant={health.source === "live" ? "success" : health.source === "offline" ? "destructive" : "secondary"}>
                {health.data.status}
              </Badge>
            </Row>
            {health.data.version && <Row label="Version">{health.data.version}</Row>}
            {health.data.agent_review && <Row label="Agent review">{health.data.agent_review}</Row>}
            {health.data.deploy_mode && <Row label="Deploy mode">{health.data.deploy_mode}</Row>}
            <Row label="Decision log">
              {integrity.data.ok ? (
                <Badge variant="success">chain intact, {integrity.data.records} records</Badge>
              ) : (
                <Badge variant="destructive">{integrity.source === "live" ? `broken at line ${integrity.data.broken_at_line}` : "not checked"}</Badge>
              )}
            </Row>
          </CardContent>
        </Card>

        {devices && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">Edge nodes</CardTitle>
              <Badge variant="outline">{iotMode === "live" ? "live" : "simulated"}</Badge>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {devices.map((d) => (
                <Row key={d.id} label={<Link href={`/dashboard/devices/${d.id}`} className="font-medium hover:underline">{d.id}</Link>}>
                  <span className="text-muted-foreground">{d.door ?? d.kind}</span>{" "}
                  <Badge variant={d.online ? "success" : "destructive"}>{d.online ? d.detail : "offline"}</Badge>
                </Row>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      <DecisionsTable data={decisions.data.slice(0, 50)} title="Recent decisions" />
    </Shell>
  )
}

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  )
}
