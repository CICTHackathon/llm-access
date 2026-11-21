import { cameraApi, gatewayApi } from "@/lib/iot"
import { deviceRoute } from "@/lib/iot/route"

export const dynamic = "force-dynamic"

export const GET = deviceRoute(async ({ device, req }) => {
  const limit = Math.min(Number(new URL(req.url).searchParams.get("limit") ?? 50), 200)
  if (device.kind === "gateway") return (await gatewayApi(device).events(limit)).events
  return (await cameraApi(device).events()).slice(0, limit)
})
