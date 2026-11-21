"use client"

import * as React from "react"

import type { CameraEvent, CameraStatus, DavEntry } from "@/lib/iot/types"
import { formatBytes, formatDateTime, formatDuration } from "@/lib/utils"
import { send, usePoll } from "@/hooks/use-device-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { toast } from "@/components/ui/use-toast"
import { ConfigEditor } from "@/components/devices/config-editor"
import { ConfirmAction } from "@/components/devices/confirm-action"
import { Icons } from "@/components/icons"

export function CameraConsole({ deviceId, streamUrl }: { deviceId: string; streamUrl: string | null }) {
  const status = usePoll<CameraStatus>(`/api/devices/${deviceId}/status`, 4000)
  const s = status.data
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <LiveView deviceId={deviceId} streamUrl={streamUrl} online={!!s} />
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Status</CardTitle>
            {status.error ? <Badge variant="destructive">offline</Badge> : s ? <Badge variant="success">online</Badge> : null}
          </CardHeader>
          <CardContent className="grid gap-1.5 text-sm">
            {status.error && <p className="text-destructive">{status.error}</p>}
            {s && (
              <>
                <Row label="Frame rate">{s.fps.toFixed(1)} fps</Row>
                <Row label="Events">
                  {s.events}
                  {s.eventOpen && <Badge variant="warning" className="ml-2">recording</Badge>}
                </Row>
                <Row label="Motion area">{(s.area * 100).toFixed(2)}%</Row>
                <Row label="Scores">
                  stage 1 {s.s1.toFixed(2)}, stage 2 {s.s2.toFixed(2)}
                </Row>
                <Row label="Timings">
                  decode {s.decodeMs} ms, analyse {s.analyseMs} ms, model {s.mlMs} ms
                </Row>
                <Row label="Storage">
                  {s.store}, {formatBytes(s.storeUsed)} of {formatBytes(s.storeTotal)}
                </Row>
                <Row label="Clock">{s.clockSet ? formatDateTime(s.epoch * 1000) : <Badge variant="warning">not set</Badge>}</Row>
                <Row label="Uptime">
                  {formatDuration(s.uptime)}, {s.ip}
                </Row>
              </>
            )}
            <div className="pt-2">
              <ConfirmAction
                label="Reboot"
                title={`Reboot ${deviceId}?`}
                description="Recording pauses while the recorder restarts."
                variant="ghost"
                disabled={!s}
                onConfirm={async () => {
                  try {
                    await send(`/api/devices/${deviceId}/actions`, "POST", { action: "reboot" })
                    toast({ title: `Reboot sent to ${deviceId}` })
                  } catch (e) {
                    toast({ title: "Reboot failed", description: (e as Error).message, variant: "destructive" })
                  }
                }}
              />
            </div>
          </CardContent>
        </Card>
      </div>
      <Events deviceId={deviceId} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Recordings deviceId={deviceId} />
        <ConfigEditor deviceId={deviceId} />
      </div>
    </div>
  )
}

function LiveView({ deviceId, streamUrl, online }: { deviceId: string; streamUrl: string | null; online: boolean }) {
  const [tick, setTick] = React.useState(() => Date.now())
  const [paused, setPaused] = React.useState(false)
  React.useEffect(() => {
    if (paused) return
    const timer = setInterval(() => setTick(Date.now()), 2000)
    return () => clearInterval(timer)
  }, [paused])
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base">Live view</CardTitle>
          <CardDescription>A frame from /capture every 2 seconds, through the server.</CardDescription>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setPaused((p) => !p)}>
            {paused ? "Resume" : "Pause"}
          </Button>
          {streamUrl && (
            <a href={streamUrl} target="_blank" rel="noreferrer">
              <Button size="sm" variant="outline">
                MJPEG stream
              </Button>
            </a>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {online ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`/api/devices/${deviceId}/capture?t=${tick}`}
            alt={`Live frame from ${deviceId}`}
            className="aspect-[4/3] w-full rounded-md border bg-muted object-contain"
          />
        ) : (
          <div className="flex aspect-[4/3] items-center justify-center rounded-md border bg-muted text-sm text-muted-foreground">
            No frame: the recorder is offline.
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Events({ deviceId }: { deviceId: string }) {
  const events = usePoll<CameraEvent[]>(`/api/devices/${deviceId}/events?limit=50`, 8000)
  const [view, setView] = React.useState<string | null>(null)
  async function label(id: number, value: 0 | 1) {
    try {
      await send(`/api/devices/${deviceId}/label`, "POST", { id, label: value })
      events.reload()
    } catch (e) {
      toast({ title: "Label not saved", description: (e as Error).message, variant: "destructive" })
    }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Movement events</CardTitle>
        <CardDescription>Label events to build the training set for the on-device classifier.</CardDescription>
      </CardHeader>
      <CardContent>
        {events.error && <p className="text-sm text-destructive">{events.error}</p>}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Verdict</TableHead>
                <TableHead>Scores</TableHead>
                <TableHead>Frames</TableHead>
                <TableHead>Label</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(events.data ?? []).slice(0, 20).map((e) => (
                <TableRow key={e.id}>
                  <TableCell>{e.id}</TableCell>
                  <TableCell>{e.epoch ? formatDateTime(e.epoch * 1000) : e.time}</TableCell>
                  <TableCell>
                    <Badge variant={e.verdict === "person" ? "success" : "secondary"}>{e.verdict}</Badge>
                  </TableCell>
                  <TableCell className="text-xs">
                    {e.s1.toFixed(2)} / {e.s2.toFixed(2)}
                  </TableCell>
                  <TableCell>{e.frames}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button size="sm" variant={e.label === 1 ? "default" : "outline"} onClick={() => label(e.id, 1)}>
                        person
                      </Button>
                      <Button size="sm" variant={e.label === 0 ? "default" : "outline"} onClick={() => label(e.id, 0)}>
                        not
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell>
                    {e.path && (
                      <Button size="sm" variant="ghost" onClick={() => setView(e.path.replace(/^\/dav/, ""))}>
                        <Icons.image className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <Viewer deviceId={deviceId} path={view} onClose={() => setView(null)} />
      </CardContent>
    </Card>
  )
}

function Recordings({ deviceId }: { deviceId: string }) {
  const [folder, setFolder] = React.useState("/events")
  const listing = usePoll<{ path: string; entries: DavEntry[] }>(`/api/devices/${deviceId}/recordings?path=${encodeURIComponent(folder)}`)
  const [view, setView] = React.useState<string | null>(null)
  const crumbs = folder.split("/").filter(Boolean)

  async function remove(path: string) {
    try {
      await send(`/api/devices/${deviceId}/recordings?path=${encodeURIComponent(path)}`, "DELETE")
      toast({ title: `Deleted ${path}` })
      listing.reload()
    } catch (e) {
      toast({ title: "Not deleted", description: (e as Error).message, variant: "destructive" })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recordings (WebDAV)</CardTitle>
        <CardDescription>
          The recorder&apos;s <code>/dav</code> share, browsed through the server. Each event is a JPEG with a JSON sidecar.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap items-center gap-1 text-sm">
          {crumbs.map((c, i) => {
            const path = `/${crumbs.slice(0, i + 1).join("/")}`
            return (
              <React.Fragment key={path}>
                {i > 0 && <span className="text-muted-foreground">/</span>}
                <button className="hover:underline" onClick={() => setFolder(path)}>
                  {c}
                </button>
              </React.Fragment>
            )
          })}
          <Button size="sm" variant="ghost" className="ml-auto" onClick={() => listing.reload()} aria-label="Refresh">
            <Icons.refresh className="h-4 w-4" />
          </Button>
        </div>
        {listing.error && <p className="text-sm text-destructive">{listing.error}</p>}
        <ul className="max-h-[360px] divide-y overflow-y-auto rounded-md border">
          {(listing.data?.entries ?? []).map((e) => (
            <li key={e.path} className="flex items-center gap-2 px-3 py-1.5 text-sm">
              {e.isDir ? <Icons.folder className="h-4 w-4 text-amber-600" /> : <Icons.image className="h-4 w-4 text-muted-foreground" />}
              <button
                className="flex-1 truncate text-left hover:underline"
                onClick={() => (e.isDir ? setFolder(e.path) : setView(e.path))}
                title={e.path}
              >
                {e.name}
              </button>
              {!e.isDir && <span className="text-xs text-muted-foreground">{formatBytes(e.size)}</span>}
              {!e.isDir && (
                <a href={`/api/devices/${deviceId}/recordings/file?path=${encodeURIComponent(e.path)}&download=1`} aria-label={`Download ${e.name}`}>
                  <Icons.down className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                </a>
              )}
              <ConfirmAction
                label={<Icons.trash className="h-4 w-4" />}
                title={`Delete ${e.name}?`}
                description={e.isDir ? "Every recording of this day is removed from the card." : "The file is removed from the card."}
                variant="ghost"
                onConfirm={() => remove(e.path)}
              />
            </li>
          ))}
          {listing.data && listing.data.entries.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">Empty folder.</li>}
        </ul>
        <Viewer deviceId={deviceId} path={view} onClose={() => setView(null)} />
      </CardContent>
    </Card>
  )
}

function Viewer({ deviceId, path, onClose }: { deviceId: string; path: string | null; onClose: () => void }) {
  const isJson = path?.endsWith(".json")
  const [text, setText] = React.useState<string | null>(null)
  const url = path ? `/api/devices/${deviceId}/recordings/file?path=${encodeURIComponent(path)}` : null
  React.useEffect(() => {
    setText(null)
    if (url && isJson) fetch(url).then((r) => r.text()).then(setText)
  }, [url, isJson])
  return (
    <Dialog open={!!path} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-[720px]">
        <DialogHeader>
          <DialogTitle className="truncate text-sm">{path}</DialogTitle>
        </DialogHeader>
        {url && (isJson ? (
          <pre className="max-h-[60vh] overflow-auto rounded bg-muted p-3 text-xs">{text ?? "Loading..."}</pre>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={url} alt={path ?? ""} className="w-full rounded-md border" />
        ))}
      </DialogContent>
    </Dialog>
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
