import { NextResponse } from "next/server"

import { audit } from "@/lib/audit"
import { db } from "@/lib/db"
import { deviceRoute } from "@/lib/iot/route"
import { deviceUpdateSchema } from "@/lib/validations/device"

export const dynamic = "force-dynamic"

export const GET = deviceRoute(async ({ device }) => device)

export const PATCH = deviceRoute(async ({ user, device, req }) => {
  const parsed = deviceUpdateSchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ") }, { status: 400 })
  }
  const updated = await db.device.update({ where: { id: device.id }, data: parsed.data })
  await audit(user, "device.update", device.id, parsed.data)
  return updated
})

export const DELETE = deviceRoute(async ({ user, device }) => {
  await db.device.delete({ where: { id: device.id } })
  await audit(user, "device.delete", device.id, { kind: device.kind })
  return new NextResponse(null, { status: 204 })
})
