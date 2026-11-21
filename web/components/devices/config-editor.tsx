"use client"

import * as React from "react"

import { send, usePoll } from "@/hooks/use-device-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { toast } from "@/components/ui/use-toast"

const SECRETS = new Set(["apiToken", "pdpToken", "decisionKey"])

/** The node's settings, one row each. Secrets are shown as set / not set and cannot be edited here. */
export function ConfigEditor({ deviceId }: { deviceId: string }) {
  const { data, error, reload } = usePoll<Record<string, unknown>>(`/api/devices/${deviceId}/config`)
  const [draft, setDraft] = React.useState<Record<string, string>>({})
  const [saving, setSaving] = React.useState<string | null>(null)

  async function save(key: string, original: unknown) {
    const raw = draft[key]
    const value = typeof original === "number" ? Number(raw) : typeof original === "boolean" ? raw === "true" : raw
    if (typeof original === "number" && Number.isNaN(value)) {
      return toast({ title: `${key} must be a number`, variant: "destructive" })
    }
    setSaving(key)
    try {
      await send(`/api/devices/${deviceId}/config`, "POST", { key, value })
      toast({ title: `${key} saved` })
      setDraft(({ [key]: _, ...rest }) => rest)
      reload()
    } catch (e) {
      toast({ title: `${key} not saved`, description: (e as Error).message, variant: "destructive" })
    } finally {
      setSaving(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Settings</CardTitle>
        <CardDescription>
          Written to the node with POST /api/config and recorded in the audit log. Tokens and keys are provisioned with{" "}
          <code>llm-access provision</code>.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {data && (
          <div className="grid gap-2">
            {Object.entries(data).map(([key, value]) => {
              const secret = SECRETS.has(key)
              const current = draft[key] ?? String(value)
              const changed = draft[key] !== undefined && draft[key] !== String(value)
              return (
                <div key={key} className="grid grid-cols-[minmax(120px,180px)_1fr_auto] items-center gap-2">
                  <code className="truncate text-sm" title={key}>
                    {key}
                  </code>
                  {secret ? (
                    <Badge variant={value === "set" ? "success" : "warning"} className="w-fit">
                      {String(value)}
                    </Badge>
                  ) : typeof value === "boolean" ? (
                    <select
                      value={current}
                      onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                      className="h-9 rounded-md border bg-background px-2 text-sm"
                    >
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <Input className="h-9" value={current} onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))} />
                  )}
                  <Button size="sm" variant="outline" disabled={secret || !changed || saving === key} onClick={() => save(key, value)}>
                    Save
                  </Button>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
