import { NextResponse } from "next/server"
import { z } from "zod"

import { audit } from "@/lib/audit"
import { cameraApi, gatewayApi } from "@/lib/iot"
import { deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

const bodySchema = z.object({
  action: z.enum(["unlock", "lock", "enrol", "reboot"]),
  reason: z.string().trim().max(200).optional(),
  ms: z.number().int().min(5000).max(60000).optional(),
})

/** Operator overrides. The gateway audits these too, as "remote". */
export const POST = deviceRoute(async ({ user, device, req }) => {
  const parsed = bodySchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) return NextResponse.json({ error: "Unknown action" }, { status: 400 })
  const { action, reason, ms } = parsed.data

  if (device.kind === "camera") {
    if (action !== "reboot") return NextResponse.json({ error: `A camera cannot ${action}` }, { status: 400 })
    await cameraApi(device).reboot()
  } else {
    const api = gatewayApi(device)
    if (action === "unlock") await api.unlock()
    else if (action === "lock") await api.lock()
    else if (action === "enrol") await api.enrolArm(ms ?? 20000)
    else await api.reboot()
  }
  await audit(user, `device.${action}`, device.id, { reason: reason ?? null })
  return { ok: true }
})

/** Collects the UID of the card presented after "enrol", once. */
export const GET = deviceRoute(async ({ device }) => gatewayApi(device).enrolResult())
