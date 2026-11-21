import { NextResponse } from "next/server"
import { z } from "zod"

import { audit } from "@/lib/audit"
import { gatewayApi } from "@/lib/iot"
import { deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

const bodySchema = z.discriminatedUnion("action", [
  z.object({ action: z.literal("remove"), uid: z.string().regex(/^0x[0-9a-fA-F]{4,14}$/) }),
  z.object({ action: z.literal("clear") }),
])

export const GET = deviceRoute(async ({ device }) => gatewayApi(device).acl())

/** Revokes one cached entry or clears the offline cache. Adding entries goes through a verified plan. */
export const POST = deviceRoute(async ({ user, device, req }) => {
  const parsed = bodySchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) return NextResponse.json({ error: "Expected {action: 'remove', uid} or {action: 'clear'}" }, { status: 400 })
  const api = gatewayApi(device)
  if (parsed.data.action === "remove") await api.aclRemove(parsed.data.uid)
  else await api.aclClear()
  await audit(user, `device.acl.${parsed.data.action}`, device.id, parsed.data)
  return api.acl()
})
