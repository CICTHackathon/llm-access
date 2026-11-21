import bcrypt from "bcryptjs"
import { NextResponse } from "next/server"

import { audit } from "@/lib/audit"
import { db } from "@/lib/db"
import { requireApi } from "@/lib/session"
import { issues, userCreateSchema, userSelect } from "@/lib/validations/user"

export const dynamic = "force-dynamic"

export async function GET() {
  const { error } = await requireApi("manageUsers")
  if (error) return error
  return NextResponse.json(await db.user.findMany({ select: userSelect, orderBy: { createdAt: "asc" } }))
}

export async function POST(req: Request) {
  const { user, error } = await requireApi("manageUsers")
  if (error) return error
  const parsed = userCreateSchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) return NextResponse.json({ error: issues(parsed.error) }, { status: 400 })
  const { password, ...data } = parsed.data
  if (await db.user.findUnique({ where: { email: data.email } })) {
    return NextResponse.json({ error: "An account with this email already exists" }, { status: 409 })
  }
  const created = await db.user.create({
    data: { ...data, passwordHash: await bcrypt.hash(password, 12) },
    select: userSelect,
  })
  await audit(user, "user.create", created.email, { role: created.role })
  return NextResponse.json(created, { status: 201 })
}
