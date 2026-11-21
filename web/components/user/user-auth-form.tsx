"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { signIn } from "next-auth/react"

import { ROLE_LABEL, type Role } from "@/lib/roles"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Icons } from "@/components/icons"

type Demo = { password: string; accounts: { email: string; name: string; role: Role }[] }

export function UserAuthForm({ callbackUrl, demo }: { callbackUrl: string; demo: Demo | null }) {
  const router = useRouter()
  const [email, setEmail] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const res = await signIn("credentials", { email, password, redirect: false })
    setBusy(false)
    if (!res || res.error) {
      setError("Wrong email or password, or the account is deactivated.")
      return
    }
    router.replace(callbackUrl)
    router.refresh()
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <Button type="submit" disabled={busy}>
        {busy && <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />}
        Sign in
      </Button>
      {demo && (
        <div className="rounded-md border border-dashed p-3 text-sm">
          <p className="mb-2 text-muted-foreground">
            Demo accounts (password <code className="rounded bg-muted px-1">{demo.password}</code>):
          </p>
          <div className="grid gap-2">
            {demo.accounts.map((a) => (
              <Button
                key={a.email}
                type="button"
                variant="outline"
                size="sm"
                className="justify-between"
                onClick={() => {
                  setEmail(a.email)
                  setPassword(demo.password)
                }}
              >
                <span>{ROLE_LABEL[a.role]}</span>
                <span className="text-xs text-muted-foreground">{a.email}</span>
              </Button>
            ))}
          </div>
        </div>
      )}
    </form>
  )
}
