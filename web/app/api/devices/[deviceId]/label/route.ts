import { NextResponse } from "next/server"
import { z } from "zod"

import { audit } from "@/lib/audit"
import { cameraApi } from "@/lib/iot"
import { deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

const bodySchema = z.object({ id: z.number().int().nonnegative(), label: z.union([z.literal(0), z.literal(1)]) })

/** Ground truth for one recorder event: 1 = a person passed, 0 = not a person. */
export const POST = deviceRoute(async ({ user, device, req }) => {
  const parsed = bodySchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) return NextResponse.json({ error: "Expected {id, label: 0 | 1}" }, { status: 400 })
  await cameraApi(device).label(parsed.data.id, parsed.data.label)
  await audit(user, "camera.label", device.id, parsed.data)
  return { ok: true }
})
