import bcrypt from "bcryptjs"
import { NextResponse } from "next/server"

import { audit } from "@/lib/audit"
import { db } from "@/lib/db"
import { requireApi } from "@/lib/session"
import { issues, userSelect, userUpdateSchema } from "@/lib/validations/user"

export const dynamic = "force-dynamic"

type Params = { params: { userId: string } }

/** True when this change would leave no active administrator. */
async function removesLastAdmin(userId: string, next: { role?: string; active?: boolean; deleted?: boolean }) {
  const target = await db.user.findUnique({ where: { id: userId } })
  if (!target || target.role !== "ADMIN" || !target.active) return false
  const staysAdmin = !next.deleted && (next.role ?? target.role) === "ADMIN" && (next.active ?? target.active)
  if (staysAdmin) return false
  const others = await db.user.count({ where: { role: "ADMIN", active: true, id: { not: userId } } })
  return others === 0
}

export async function PATCH(req: Request, { params }: Params) {
  const { user, error } = await requireApi("manageUsers")
  if (error) return error
  const parsed = userUpdateSchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) return NextResponse.json({ error: issues(parsed.error) }, { status: 400 })
  const { password, ...data } = parsed.data

  if (params.userId === user.id && (data.active === false || (data.role && data.role !== "ADMIN"))) {
    return NextResponse.json({ error: "You cannot deactivate or demote your own account" }, { status: 400 })
  }
  if (await removesLastAdmin(params.userId, data)) {
    return NextResponse.json({ error: "At least one active administrator must remain" }, { status: 400 })
  }
  try {
    const updated = await db.user.update({
      where: { id: params.userId },
      data: { ...data, ...(password ? { passwordHash: await bcrypt.hash(password, 12) } : {}) },
      select: userSelect,
    })
    await audit(user, "user.update", updated.email, { ...data, passwordReset: !!password })
    return NextResponse.json(updated)
  } catch {
    return NextResponse.json({ error: "No such user" }, { status: 404 })
  }
}

export async function DELETE(_req: Request, { params }: Params) {
  const { user, error } = await requireApi("manageUsers")
  if (error) return error
  if (params.userId === user.id) return NextResponse.json({ error: "You cannot delete your own account" }, { status: 400 })
  if (await removesLastAdmin(params.userId, { deleted: true })) {
    return NextResponse.json({ error: "At least one active administrator must remain" }, { status: 400 })
  }
  try {
    const deleted = await db.user.delete({ where: { id: params.userId } })
    await audit(user, "user.delete", deleted.email, { role: deleted.role })
    return new NextResponse(null, { status: 204 })
  } catch {
    return NextResponse.json({ error: "No such user" }, { status: 404 })
  }
}
