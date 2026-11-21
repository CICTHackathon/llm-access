import { NextResponse } from "next/server"
import { z } from "zod"

import { audit } from "@/lib/audit"
import { cameraApi, gatewayApi, maskSecrets, SECRET_SETTINGS } from "@/lib/iot"
import { deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

const bodySchema = z.object({
  key: z.string().regex(/^[A-Za-z][A-Za-z0-9_]{0,31}$/),
  value: z.union([z.string().max(200), z.number(), z.boolean()]),
})

export const GET = deviceRoute(async ({ device }) => {
  const config = device.kind === "gateway" ? await gatewayApi(device).config() : await cameraApi(device).config()
  return maskSecrets(config)
})

export const POST = deviceRoute(async ({ user, device, req }) => {
  const parsed = bodySchema.safeParse(await req.json().catch(() => null))
  if (!parsed.success) return NextResponse.json({ error: "Expected {key, value}" }, { status: 400 })
  const { key, value } = parsed.data
  if (SECRET_SETTINGS.has(key)) {
    return NextResponse.json(
      { error: `${key} is a secret; provision it out of band with "llm-access provision ${device.id}"` },
      { status: 400 }
    )
  }
  if (device.kind === "gateway") await gatewayApi(device).setConfig(key, value)
  else await cameraApi(device).setConfig(key, value)
  await audit(user, "device.config", device.id, { key, value })
  return { ok: true }
})
