"use client"

import * as React from "react"

import type { AclEntry, GatewayEvent, GatewayStatus } from "@/lib/iot/types"
import { formatDateTime, formatDuration } from "@/lib/utils"
import { send, usePoll } from "@/hooks/use-device-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { toast } from "@/components/ui/use-toast"
import { ConfigEditor } from "@/components/devices/config-editor"
import { ConfirmAction } from "@/components/devices/confirm-action"
import { Icons } from "@/components/icons"

export function GatewayConsole({ deviceId }: { deviceId: string }) {
  const status = usePoll<GatewayStatus>(`/api/devices/${deviceId}/status`, 3000)
  const events = usePoll<GatewayEvent[]>(`/api/devices/${deviceId}/events?limit=50`, 5000)

  async function action(name: "unlock" | "lock" | "reboot", reason?: string) {
    try {
      await send(`/api/devices/${deviceId}/actions`, "POST", { action: name, reason })
      toast({ title: `${name} sent to ${deviceId}` })
      status.reload()
      events.reload()
    } catch (e) {
      toast({ title: `${name} failed`, description: (e as Error).message, variant: "destructive" })
    }
  }

  const s = status.data
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Status</CardTitle>
            {status.error ? <Badge variant="destructive">offline</Badge> : s ? <Badge variant="success">online</Badge> : null}
          </CardHeader>
          <CardContent className="grid gap-1.5 text-sm">
            {status.error && <p className="text-destructive">{status.error}</p>}
            {s && (
              <>
                <Row label="Door">
                  <span className="flex items-center gap-2 font-semibold">
                    {s.door === "locked" ? <Icons.doorClosed className="h-4 w-4" /> : <Icons.doorOpen className="h-4 w-4 text-amber-600" />}
                    {s.door}
                    {s.holdMs > 0 && <span className="font-normal text-muted-foreground">({Math.ceil(s.holdMs / 1000)} s)</span>}
                  </span>
                </Row>
                <Row label="State">{s.state}</Row>
                <Row label="Door identifier">{s.doorId}</Row>
                <Row label="Transactions">
                  {s.transactions} ({s.grants} granted, {s.denials} denied, {s.degraded} degraded)
                </Row>
                <Row label="PDP">
                  {s.pdp.configured ? (
                    <>
                      HTTP {s.pdp.lastCode}, {s.pdp.lastMs} ms
                    </>
                  ) : (
                    <Badge variant="warning">not configured</Badge>
                  )}
                </Row>
                <Row label="Signed decisions">{s.signedDecisions ? "required" : <Badge variant="warning">off</Badge>}</Row>
                <Row label="Offline cache">{s.acl} entries</Row>
                <Row label="Clock">{s.clockSet ? formatDateTime(s.epoch * 1000) : <Badge variant="warning">not set</Badge>}</Row>
                <Row label="Network">
                  {s.ip}, RSSI {s.rssi} dBm
                </Row>
                <Row label="Uptime">
                  {formatDuration(s.uptime)}, heap {Math.round(s.heap / 1024)} KB
                </Row>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Operator override</CardTitle>
            <CardDescription>The gateway records these as &quot;remote&quot; in its own audit ring as well.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <ConfirmAction
              label={
                <>
                  <Icons.doorOpen className="mr-2 h-4 w-4" /> Unlock
                </>
              }
              title={`Unlock ${deviceId}?`}
              description="The latch opens for the configured hold time without a card or PIN."
              askReason
              variant="default"
              disabled={!s}
              onConfirm={(reason) => action("unlock", reason)}
            />
            <Button variant="outline" disabled={!s} onClick={() => action("lock")}>
              <Icons.doorClosed className="mr-2 h-4 w-4" /> Lock now
            </Button>
            <ConfirmAction
              label="Reboot"
              title={`Reboot ${deviceId}?`}
              description="The door stays locked while the node restarts (about 10 s)."
              variant="ghost"
              disabled={!s}
              onConfirm={() => action("reboot")}
            />
            <Enrolment deviceId={deviceId} disabled={!s} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Audit ring</CardTitle>
          <CardDescription>Newest first, as the gateway recorded them.</CardDescription>
        </CardHeader>
        <CardContent>
          {events.error && <p className="text-sm text-destructive">{events.error}</p>}
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Card</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead>Effect</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Note</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(events.data ?? []).slice(0, 25).map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>{e.id}</TableCell>
                    <TableCell>{e.epoch ? formatDateTime(e.epoch * 1000) : `up ${e.uptime}s`}</TableCell>
                    <TableCell>
                      <code className="text-xs">{e.uid || "-"}</code>
                    </TableCell>
                    <TableCell>{e.state}</TableCell>
                    <TableCell>
                      {e.effect && <Badge variant={e.effect === "permit" ? "success" : "destructive"}>{e.effect}</Badge>}
                    </TableCell>
                    <TableCell>
                      <code className="text-xs">{e.reason}</code>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{e.note}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <OfflineCache deviceId={deviceId} />
        <ConfigEditor deviceId={deviceId} />
      </div>
    </div>
  )
}

function OfflineCache({ deviceId }: { deviceId: string }) {
  const acl = usePoll<{ entries: AclEntry[]; capacity: number }>(`/api/devices/${deviceId}/acl`)
  async function change(body: { action: "remove"; uid: string } | { action: "clear" }) {
    try {
      await send(`/api/devices/${deviceId}/acl`, "POST", body)
      toast({ title: body.action === "clear" ? "Offline cache cleared" : `${body.uid} removed` })
      acl.reload()
    } catch (e) {
      toast({ title: "Not changed", description: (e as Error).message, variant: "destructive" })
    }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Offline cache</CardTitle>
        <CardDescription>
          What the gateway may grant on its own when the PDP is unreachable. New entries come only from a verified plan (ask the
          assistant to sync the cache); here you can revoke.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {acl.error && <p className="text-sm text-destructive">{acl.error}</p>}
        {acl.data && (
          <>
            <p className="text-sm text-muted-foreground">
              {acl.data.entries.length} of {acl.data.capacity} entries
            </p>
            <ul className="divide-y rounded-md border">
              {acl.data.entries.map((e) => (
                <li key={e.uid} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span>
                    <code>{e.uid}</code> {e.pin ? "card + PIN" : "card only"}, expires in {formatDuration(e.ttl)}
                  </span>
                  <Button size="sm" variant="ghost" onClick={() => change({ action: "remove", uid: e.uid })}>
                    <Icons.trash className="h-4 w-4" />
                  </Button>
                </li>
              ))}
              {acl.data.entries.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">Empty.</li>}
            </ul>
            <ConfirmAction
              label="Clear the cache"
              title="Clear the offline cache?"
              description="While the PDP is unreachable, this gateway will then deny everyone."
              variant="outline"
              disabled={acl.data.entries.length === 0}
              onConfirm={() => change({ action: "clear" })}
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}

function Enrolment({ deviceId, disabled }: { deviceId: string; disabled: boolean }) {
  const [waiting, setWaiting] = React.useState(false)
  async function start() {
    try {
      await send(`/api/devices/${deviceId}/actions`, "POST", { action: "enrol", ms: 20000 })
      setWaiting(true)
      toast({ title: "Present the new card at the reader within 20 seconds" })
      const until = Date.now() + 21000
      while (Date.now() < until) {
        await new Promise((r) => setTimeout(r, 1500))
        const res = await fetch(`/api/devices/${deviceId}/actions`, { cache: "no-store" })
        const body = await res.json()
        if (body.uid) {
          toast({ title: "Card read", description: `UID ${body.uid}. Add it to config/identities.yaml, then sync the cache.` })
          return
        }
        if (!body.armed) break
      }
      toast({ title: "No card was presented", variant: "destructive" })
    } catch (e) {
      toast({ title: "Enrolment failed", description: (e as Error).message, variant: "destructive" })
    } finally {
      setWaiting(false)
    }
  }
  return (
    <Button variant="outline" disabled={disabled || waiting} onClick={start}>
      {waiting && <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />}
      Read a new card
    </Button>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  )
}
