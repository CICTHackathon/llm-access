import { NextResponse } from "next/server"

import { audit } from "@/lib/audit"
import { db } from "@/lib/db"
import { requireApi } from "@/lib/session"
import { deviceSchema } from "@/lib/validations/device"

export const dynamic = "force-dynamic"

export async function GET() {
  const { error } = await requireApi("manageIot")
  if (error) return error
  return NextResponse.json(await db.device.findMany({ orderBy: { id: "asc" } }))
}

export async function POST(req: Request) {
  const { user, error } = await requireApi("manageIot")
  if (error) return error
  const parsed = deviceSchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ") }, { status: 400 })
  }
  if (await db.device.findUnique({ where: { id: parsed.data.id } })) {
    return NextResponse.json({ error: `A device called ${parsed.data.id} already exists` }, { status: 409 })
  }
  const device = await db.device.create({ data: parsed.data })
  await audit(user, "device.create", device.id, { kind: device.kind, baseUrl: device.baseUrl })
  return NextResponse.json(device, { status: 201 })
}
