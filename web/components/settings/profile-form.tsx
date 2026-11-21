"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { send } from "@/hooks/use-device-api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "@/components/ui/use-toast"

export function ProfileForm({ name: initialName, email }: { name: string; email: string }) {
  const router = useRouter()
  const [name, setName] = React.useState(initialName)
  const [currentPassword, setCurrent] = React.useState("")
  const [newPassword, setNew] = React.useState("")
  const [busy, setBusy] = React.useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await send("/api/me", "PATCH", { name, ...(newPassword ? { currentPassword, newPassword } : {}) })
      toast({ title: newPassword ? "Profile and password saved" : "Profile saved" })
      setCurrent("")
      setNew("")
      router.refresh()
    } catch (err) {
      toast({ title: "Not saved", description: (err as Error).message, variant: "destructive" })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>Signed in as {email}. Your role is managed by an administrator.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid max-w-md gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="current">Current password</Label>
            <Input id="current" type="password" autoComplete="current-password" value={currentPassword} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="new">New password</Label>
            <Input id="new" type="password" autoComplete="new-password" minLength={8} value={newPassword} onChange={(e) => setNew(e.target.value)} />
            <p className="text-xs text-muted-foreground">Leave empty to keep your password.</p>
          </div>
          <Button type="submit" disabled={busy} className="w-fit">
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
