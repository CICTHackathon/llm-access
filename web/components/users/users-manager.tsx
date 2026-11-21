"use client"

import * as React from "react"

import { ROLE_DESCRIPTION, ROLE_LABEL, ROLES, type Role } from "@/lib/roles"
import { formatDateTime } from "@/lib/utils"
import { send } from "@/hooks/use-device-api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { toast } from "@/components/ui/use-toast"
import { ConfirmAction } from "@/components/devices/confirm-action"
import { Icons } from "@/components/icons"

export type UserRow = {
  id: string
  name: string
  email: string
  role: Role
  active: boolean
  lastLoginAt: string | null
  createdAt: string
}

export function UsersManager({ initialUsers, currentUserId }: { initialUsers: UserRow[]; currentUserId: string }) {
  const [users, setUsers] = React.useState(initialUsers)

  async function update(id: string, body: Partial<{ role: Role; active: boolean; password: string; name: string }>) {
    try {
      const updated = await send(`/api/users/${id}`, "PATCH", body)
      setUsers((u) => u.map((x) => (x.id === id ? updated : x)))
      toast({ title: body.password ? "Password reset" : "User updated" })
      return true
    } catch (e) {
      toast({ title: "Not updated", description: (e as Error).message, variant: "destructive" })
      return false
    }
  }

  async function remove(id: string) {
    try {
      await send(`/api/users/${id}`, "DELETE")
      setUsers((u) => u.filter((x) => x.id !== id))
      toast({ title: "User deleted" })
    } catch (e) {
      toast({ title: "Not deleted", description: (e as Error).message, variant: "destructive" })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end px-2">
        <CreateUser onCreated={(u) => setUsers((x) => [...x, u])} />
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last sign-in</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => {
              const self = u.id === currentUserId
              return (
                <TableRow key={u.id}>
                  <TableCell className="font-medium">
                    {u.name} {self && <Badge variant="outline">you</Badge>}
                  </TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>
                    <select
                      value={u.role}
                      disabled={self}
                      onChange={(e) => update(u.id, { role: e.target.value as Role })}
                      className="h-9 rounded-md border bg-background px-2 text-sm"
                      aria-label={`Role of ${u.name}`}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROLE_LABEL[r]}
                        </option>
                      ))}
                    </select>
                  </TableCell>
                  <TableCell>
                    <Badge variant={u.active ? "success" : "secondary"}>{u.active ? "active" : "deactivated"}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{u.lastLoginAt ? formatDateTime(u.lastLoginAt) : "never"}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <ResetPassword name={u.name} onReset={(password) => update(u.id, { password })} />
                      <Button size="sm" variant="ghost" disabled={self} onClick={() => update(u.id, { active: !u.active })}>
                        {u.active ? "Deactivate" : "Activate"}
                      </Button>
                      <ConfirmAction
                        label={<Icons.trash className="h-4 w-4" />}
                        title={`Delete ${u.name}?`}
                        description="The account and its assistant conversations are deleted. Audit entries keep the email."
                        variant="ghost"
                        disabled={self}
                        onConfirm={() => remove(u.id)}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
      <div className="grid gap-2 px-2 text-sm text-muted-foreground md:grid-cols-3">
        {ROLES.map((r) => (
          <p key={r}>
            <strong className="text-foreground">{ROLE_LABEL[r]}:</strong> {ROLE_DESCRIPTION[r]}
          </p>
        ))}
      </div>
    </div>
  )
}

function CreateUser({ onCreated }: { onCreated: (u: UserRow) => void }) {
  const [open, setOpen] = React.useState(false)
  const [form, setForm] = React.useState({ name: "", email: "", role: "OPERATOR" as Role, password: "" })
  const [busy, setBusy] = React.useState(false)
  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      onCreated(await send("/api/users", "POST", form))
      toast({ title: `${form.email} created` })
      setForm({ name: "", email: "", role: "OPERATOR", password: "" })
      setOpen(false)
    } catch (err) {
      toast({ title: "Not created", description: (err as Error).message, variant: "destructive" })
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Icons.add className="mr-2 h-4 w-4" /> Add user
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a user</DialogTitle>
          <DialogDescription>Share the initial password securely; the user can change it under Settings.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label>Name</Label>
            <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid gap-1.5">
            <Label>Email</Label>
            <Input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="grid gap-1.5">
            <Label>Role</Label>
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
              className="h-10 rounded-md border bg-background px-3 text-sm"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-1.5">
            <Label>Initial password</Label>
            <Input required type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <p className="text-xs text-muted-foreground">At least 8 characters, with a letter and a digit.</p>
          </div>
          <Button type="submit" disabled={busy}>
            {busy && <Icons.spinner className="mr-2 h-4 w-4 animate-spin" />}
            Create
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ResetPassword({ name, onReset }: { name: string; onReset: (password: string) => Promise<boolean> }) {
  const [open, setOpen] = React.useState(false)
  const [password, setPassword] = React.useState("")
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost">
          Reset password
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reset the password of {name}</DialogTitle>
        </DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={async (e) => {
            e.preventDefault()
            if (await onReset(password)) {
              setPassword("")
              setOpen(false)
            }
          }}
        >
          <Input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="New password" />
          <Button type="submit">Reset</Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
