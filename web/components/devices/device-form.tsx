"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import type { DeviceRecord } from "@/lib/iot/types"
import { send } from "@/hooks/use-device-api"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/use-toast"
import { Icons } from "@/components/icons"

const EMPTY = { id: "", kind: "gateway", name: "", door: "", zone: "", baseUrl: "http://", streamUrl: "", tokenEnv: "", notes: "" }

/** Creates a device, or edits one when `device` is given. */
export function DeviceForm({ device }: { device?: DeviceRecord }) {
  const router = useRouter()
  const [open, setOpen] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [form, setForm] = React.useState(() =>
    device
      ? { ...EMPTY, ...Object.fromEntries(Object.entries(device).map(([k, v]) => [k, v ?? ""])) }
      : EMPTY
  )
  const set = (key: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const { id, kind, ...rest } = form
      if (device) await send(`/api/devices/${device.id}`, "PATCH", rest)
      else await send("/api/devices", "POST", { id, kind, ...rest })
      toast({ title: device ? "Device updated" : "Device added" })
      setOpen(false)
      if (device) router.refresh()
      else router.push(`/dashboard/devices/${id}`)
    } catch (err) {
      toast({ title: "Not saved", description: (err as Error).message, variant: "destructive" })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={device ? "outline" : "default"}>
          {device ? "Edit device" : (
            <>
              <Icons.add className="mr-2 h-4 w-4" /> Add device
            </>
          )}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{device ? `Edit ${device.id}` : "Add an edge node"}</DialogTitle>
          <DialogDescription>
            The API token is not stored here: name the environment variable that holds it on the web server.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          {!device && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Identifier">
                <Input required value={form.id} onChange={set("id")} placeholder="gw-3" />
              </Field>
              <Field label="Kind">
                <select value={form.kind} onChange={set("kind")} className="h-10 rounded-md border bg-background px-3 text-sm">
                  <option value="gateway">Gateway (ESP32)</option>
                  <option value="camera">Camera (ESP32-CAM)</option>
                </select>
              </Field>
            </div>
          )}
          <Field label="Name">
            <Input required value={form.name} onChange={set("name")} placeholder="Server room gateway" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Door">
              <Input value={form.door} onChange={set("door")} placeholder="door-3" />
            </Field>
            <Field label="Zone">
              <Input value={form.zone} onChange={set("zone")} placeholder="server_room" />
            </Field>
          </div>
          <Field label="Address">
            <Input required value={form.baseUrl} onChange={set("baseUrl")} placeholder="http://192.168.1.53" />
          </Field>
          {(form.kind === "camera" || device?.kind === "camera") && (
            <Field label="Live stream (port 81)">
              <Input value={form.streamUrl} onChange={set("streamUrl")} placeholder="http://192.168.1.53:81/stream" />
            </Field>
          )}
          <Field label="Token environment variable">
            <Input value={form.tokenEnv} onChange={set("tokenEnv")} placeholder="GW3_API_TOKEN" />
          </Field>
          <Field label="Notes">
            <Textarea value={form.notes} onChange={set("notes")} rows={2} />
          </Field>
          <Button type="submit" disabled={busy}>
            {busy && <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />}
            {device ? "Save" : "Add device"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  )
}
