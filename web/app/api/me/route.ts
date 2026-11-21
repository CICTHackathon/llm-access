import bcrypt from "bcryptjs"
import { NextResponse } from "next/server"

import { db } from "@/lib/db"
import { requireApi } from "@/lib/session"
import { issues, profileSchema } from "@/lib/validations/user"

export const dynamic = "force-dynamic"

/** Lets any signed-in user change their own name or password. */
export async function PATCH(req: Request) {
  const { user, error } = await requireApi("viewDashboard")
  if (error) return error
  const parsed = profileSchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) return NextResponse.json({ error: issues(parsed.error) }, { status: 400 })
  const { name, currentPassword, newPassword } = parsed.data

  const data: { name?: string; passwordHash?: string } = {}
  if (name) data.name = name
  if (newPassword) {
    const current = await db.user.findUniqueOrThrow({ where: { id: user.id } })
    if (!(await bcrypt.compare(currentPassword ?? "", current.passwordHash))) {
      return NextResponse.json({ error: "Your current password is not correct" }, { status: 400 })
    }
    data.passwordHash = await bcrypt.hash(newPassword, 12)
  }
  await db.user.update({ where: { id: user.id }, data })
  return NextResponse.json({ ok: true })
}
